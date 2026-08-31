#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: teo_origin_group
short_description: Manage Tencent Cloud EdgeOne origin groups
version_added: "0.14.0"
description: Creates, updates and deletes EdgeOne origin groups with exact origin-record convergence.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired origin-group state.}
  zone_id: {type: str, required: true, description: EdgeOne zone ID.}
  group_id: {type: str, description: Existing origin-group ID; preferred for updates and deletion.}
  name: {type: str, description: "Origin-group name, also used for lookup."}
  group_type: {type: str, choices: [GENERAL, HTTP], default: GENERAL, description: Origin-group type.}
  host_header: {type: str, description: Optional origin Host header for HTTP groups.}
  records:
    type: list
    elements: dict
    description: Exact ordered-independent set of origin records.
    suboptions:
      record: {type: str, required: true, description: "IPv4, IPv6, domain, or object-storage endpoint."}
      record_type: {type: str, choices: [IP_DOMAIN, COS, AWS_S3], default: IP_DOMAIN, description: Origin record type.}
      weight: {type: int, description: Optional traffic weight from 0 through 100.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""

EXAMPLES = r"""
- name: Manage an HTTP origin group
  susunola.tencentcloud.teo_origin_group:
    region: ap-guangzhou
    zone_id: zone-xxxxxxxx
    name: app-origins
    group_type: HTTP
    host_header: origin.example.com
    records:
      - record: 192.0.2.10
        weight: 70
      - record: 192.0.2.11
        weight: 30
"""

RETURN = r"""origin_group: {description: EdgeOne origin-group metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.teo.v20220901 import models, teo_client

    return models, teo_client


def describe_request(models, p, offset=0):
    request = models.DescribeOriginGroupRequest()
    request.ZoneId, request.Offset, request.Limit = p["zone_id"], offset, 1000
    value = p.get("group_id") or p.get("name")
    if value:
        item = models.AdvancedFilter()
        item.Name = "origin-group-id" if p.get("group_id") else "origin-group-name"
        item.Values = [value]
        request.Filters = [item]
    return request


def _records(models, values):
    result = []
    for value in values or []:
        item = models.OriginRecord()
        item.Record, item.Type = value["record"], value["record_type"]
        if value.get("weight") is not None:
            item.Weight = value["weight"]
        result.append(item)
    return result


def create_request(models, p):
    request = models.CreateOriginGroupRequest()
    request.ZoneId, request.Name, request.Type = p["zone_id"], p["name"], p["group_type"]
    request.Records = _records(models, p["records"])
    if p.get("host_header") is not None:
        request.HostHeader = p["host_header"]
    return request


def update_request(models, p, group_id):
    request = models.ModifyOriginGroupRequest()
    request.ZoneId, request.GroupId = p["zone_id"], group_id
    request.Name, request.Type, request.Records = p["name"], p["group_type"], _records(models, p["records"])
    request.HostHeader = p.get("host_header") or ""
    return request


def delete_request(models, p, group_id):
    request = models.DeleteOriginGroupRequest()
    request.ZoneId, request.GroupId = p["zone_id"], group_id
    return request


def find_group(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeOriginGroup, describe_request(models, p, offset))
        values = list(response.OriginGroups or [])
        for value in values:
            item = value._serialize(allow_none=True)
            if p.get("group_id") and item.get("GroupId") == p["group_id"]:
                matches.append(item)
            elif not p.get("group_id") and p.get("name") and item.get("Name") == p["name"]:
                matches.append(item)
        offset += len(values)
        if offset >= int(response.TotalCount or 0) or not values:
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple EdgeOne origin groups matched; specify group_id")
    return matches[0] if matches else None


def _normalized_records(values, sdk=False):
    result = []
    for value in values or []:
        item = {"Record": value.get("Record") if sdk else value["record"], "Type": value.get("Type") if sdk else value["record_type"]}
        weight = value.get("Weight") if sdk else value.get("weight")
        if weight is not None:
            item["Weight"] = weight
        result.append(item)
    return sorted(result, key=lambda item: (item["Type"], item["Record"], item.get("Weight", -1)))


def desired(p):
    return {"Name": p["name"], "Type": p["group_type"], "HostHeader": p.get("host_header") or "", "Records": _normalized_records(p["records"])}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "zone_id": {"required": True},
            "group_id": {},
            "name": {},
            "group_type": {"choices": ["GENERAL", "HTTP"], "default": "GENERAL"},
            "host_header": {},
            "records": {
                "type": "list",
                "elements": "dict",
                "options": {
                    "record": {"required": True},
                    "record_type": {"choices": ["IP_DOMAIN", "COS", "AWS_S3"], "default": "IP_DOMAIN"},
                    "weight": {"type": "int"},
                },
            },
        },
        required_one_of=[("group_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and (not p.get("name") or not p.get("records")):
        module.fail_json(msg="name and at least one record are required when state=present")
    for record in p.get("records") or []:
        if record.get("weight") is not None and not 0 <= record["weight"] <= 100:
            module.fail_json(msg="record weight must be between 0 and 100")
        if p["group_type"] == "GENERAL" and record["record_type"] != "IP_DOMAIN":
            module.fail_json(msg="GENERAL origin groups only support IP_DOMAIN records")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TeoClient, "teo.tencentcloudapi.com")
    try:
        current = find_group(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, origin_group=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteOriginGroup, delete_request(models, p, current["GroupId"]))
            module.exit_json(changed=True, **(diff or {}), origin_group=current if module.check_mode else None)
        target = desired(p)
        before = None
        if current:
            before = {
                "Name": current.get("Name"),
                "Type": current.get("Type"),
                "HostHeader": current.get("HostHeader") or "",
                "Records": _normalized_records(current.get("Records"), True),
            }
        if before == target:
            module.exit_json(changed=False, origin_group=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if not current:
                p["group_id"] = module.sdk_call(client.CreateOriginGroup, create_request(models, p)).OriginGroupId
            else:
                module.sdk_call(client.ModifyOriginGroup, update_request(models, p, current["GroupId"]))
            current = find_group(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), origin_group=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
