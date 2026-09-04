#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: teo_zone
short_description: Manage Tencent Cloud EdgeOne zones
version_added: "0.14.0"
description: Creates, updates, pauses, enables and deletes EdgeOne zones.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired zone state.}
  zone_id: {type: str, description: Existing EdgeOne zone ID; preferred for updates and deletion.}
  name: {type: str, description: "Zone name, also used for lookup."}
  zone_type: {type: str, choices: [partial, full, noDomainAccess, dnsPodAccess, ai], default: partial, description: Zone access type.}
  area: {type: str, choices: [global, mainland, overseas], default: overseas, description: Layer-seven acceleration area.}
  alias_name: {type: str, description: Optional same-name zone identifier.}
  plan_id: {type: str, description: Optional EdgeOne plan ID applied only during creation.}
  enabled: {type: bool, default: true, description: Whether the zone is enabled rather than paused.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""

EXAMPLES = r"""
- name: Create a CNAME-access EdgeOne zone
  susunola.tencentcloud.teo_zone:
    region: ap-guangzhou
    name: example.com
    zone_type: partial
    area: global
    plan_id: edgeone-plan-xxxxxxxx

- name: Pause a zone
  susunola.tencentcloud.teo_zone:
    region: ap-guangzhou
    zone_id: zone-xxxxxxxx
    name: example.com
    enabled: false
"""

RETURN = r"""zone: {description: EdgeOne zone metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.teo.v20220901 import models, teo_client

    return models, teo_client


def describe_request(models, p, offset=0):
    request = models.DescribeZonesRequest()
    request.Offset, request.Limit = offset, 100
    value = p.get("zone_id") or p.get("name")
    if value:
        item = models.AdvancedFilter()
        item.Name = "zone-id" if p.get("zone_id") else "zone-name"
        item.Values = [value]
        request.Filters = [item]
    return request


def create_request(models, p):
    request = models.CreateZoneRequest()
    request.Type, request.ZoneName, request.Area = p["zone_type"], p["name"], p["area"]
    if p.get("plan_id"):
        request.PlanId = p["plan_id"]
    if p.get("alias_name"):
        request.AliasZoneName = p["alias_name"]
    return request


def update_request(models, p, zone_id):
    request = models.ModifyZoneRequest()
    request.ZoneId, request.Type = zone_id, p["zone_type"]
    request.ZoneName, request.Area = p["name"], p["area"]
    if p.get("alias_name") is not None:
        request.AliasZoneName = p["alias_name"]
    return request


def status_request(models, zone_id, enabled):
    request = models.ModifyZoneStatusRequest()
    request.ZoneId, request.Paused = zone_id, not enabled
    return request


def delete_request(models, zone_id):
    request = models.DeleteZoneRequest()
    request.ZoneId = zone_id
    return request


def find_zone(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeZones, describe_request(models, p, offset))
        values = list(response.Zones or [])
        for value in values:
            item = value._serialize(allow_none=True)
            if p.get("zone_id") and item.get("ZoneId") == p["zone_id"]:
                matches.append(item)
            elif not p.get("zone_id") and p.get("name") and item.get("ZoneName") == p["name"]:
                matches.append(item)
        offset += len(values)
        if offset >= int(response.TotalCount or 0) or not values:
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple EdgeOne zones matched; specify zone_id")
    return matches[0] if matches else None


def desired(p):
    return {"ZoneName": p["name"], "Type": p["zone_type"], "Area": p["area"], "AliasZoneName": p.get("alias_name") or "", "Paused": not p["enabled"]}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "zone_id": {},
            "name": {},
            "zone_type": {"choices": ["partial", "full", "noDomainAccess", "dnsPodAccess", "ai"], "default": "partial"},
            "area": {"choices": ["global", "mainland", "overseas"], "default": "overseas"},
            "alias_name": {},
            "plan_id": {},
            "enabled": {"type": "bool", "default": True},
        },
        required_one_of=[("zone_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p.get("name"):
        module.fail_json(msg="name is required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TeoClient, "teo.tencentcloudapi.com")
    try:
        current = find_zone(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, zone=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteZone, delete_request(models, current["ZoneId"]))
            module.exit_json(changed=True, **(diff or {}), zone=current if module.check_mode else None)
        target = desired(p)
        before = {key: current.get(key) for key in target} if current else None
        if before:
            before["AliasZoneName"] = before["AliasZoneName"] or ""
        if before == target:
            module.exit_json(changed=False, zone=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if not current:
                p["zone_id"] = module.sdk_call(client.CreateZone, create_request(models, p)).ZoneId
                current = find_zone(module, client, models, p)
            else:
                config_changed = any(before[key] != target[key] for key in ("ZoneName", "Type", "Area", "AliasZoneName"))
                if config_changed:
                    module.sdk_call(client.ModifyZone, update_request(models, p, current["ZoneId"]))
            if bool(current and current.get("Paused")) != (not p["enabled"]):
                module.sdk_call(client.ModifyZoneStatus, status_request(models, p["zone_id"] or current["ZoneId"], p["enabled"]))
            current = find_zone(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), zone=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
