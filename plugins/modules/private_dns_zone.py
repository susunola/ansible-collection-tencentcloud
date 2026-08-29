#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: private_dns_zone
short_description: Manage a Tencent Cloud Private DNS zone
version_added: "0.13.0"
description: Creates, updates and deletes a private DNS zone and its VPC associations.
options:
  state: {description: Desired zone state., type: str, choices: [present, absent], default: present}
  zone_id: {description: Existing private zone ID., type: str}
  domain: {description: Private zone domain used to find or create the zone., type: str}
  remark: {description: Zone remark., type: str, default: ''}
  vpcs:
    description: Exact associated VPC list with C(region) and C(vpc_id).
    type: list
    elements: dict
    suboptions:
      region: {description: Tencent Cloud region containing the VPC., type: str, required: true}
      vpc_id: {description: VPC ID to associate with the zone., type: str, required: true}
  tags: {description: Tags applied when creating the zone., type: dict}
  retries: {description: Number of retries for transient SDK failures., type: int, default: 5}
  waiter_delay: {description: Seconds between state-polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent value appended to SDK requests., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.private_dns_zone:
    domain: internal.example.com
    vpcs:
      - region: ap-guangzhou
        vpc_id: vpc-abc123
'''
RETURN = r'''
zone: {description: Private DNS zone metadata, type: dict, returned: always}
'''

import json
import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found


def _load_private_dns():
    from tencentcloud.privatedns.v20201028 import models, privatedns_client

    return models, privatedns_client


def _dict(value):
    return json.loads(value.to_json_string()) if value else None


def _vpcs(value):
    return sorted(
        ({"Region": item.get("Region") or item.get("region"), "UniqVpcId": item.get("UniqVpcId") or item.get("vpc_id")} for item in (value or [])),
        key=lambda item: (item["Region"], item["UniqVpcId"]),
    )


def build_vpcs(models, values):
    result = []
    for value in values or []:
        item = models.VpcInfo()
        item.Region, item.UniqVpcId = value["region"], value["vpc_id"]
        result.append(item)
    return result


def build_create_request(models, params):
    request = models.CreatePrivateZoneRequest()
    request.Domain, request.Remark = params["domain"], params["remark"]
    request.VpcSet = build_vpcs(models, params.get("vpcs"))
    if params.get("tags"):
        request.TagSet = []
        for key, value in sorted(params["tags"].items()):
            tag = models.TagInfo()
            tag.TagKey, tag.TagValue = str(key), str(value)
            request.TagSet.append(tag)
    return request


def find_zone(module, client, models, zone_id, domain):
    if zone_id:
        request = models.DescribePrivateZoneRequest()
        request.ZoneId = zone_id
        try:
            return _dict(getattr(module.sdk_call(client.DescribePrivateZone, request), "PrivateZone", None))
        except Exception as exc:
            if is_not_found(exc):
                return None
            raise
    offset, matches = 0, []
    while domain:
        request = models.DescribePrivateZoneListRequest()
        request.Offset, request.Limit = offset, 100
        response = module.sdk_call(client.DescribePrivateZoneList, request)
        items = list(getattr(response, "PrivateZoneSet", None) or [])
        matches.extend(_dict(item) for item in items if getattr(item, "Domain", None) == domain)
        offset += len(items)
        if not items or offset >= int(getattr(response, "TotalCount", 0) or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple private zones have the requested domain", domain=domain)
    return matches[0] if matches else None


def wait_for_zone(module, client, models, zone_id, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_zone(module, client, models, zone_id, None)
        if absent and current is None:
            return None
        if not absent and current:
            remark_ok = (current.get("Remark") or "") == desired["Remark"]
            vpcs_ok = "VpcSet" not in desired or _vpcs(current.get("VpcSet")) == desired["VpcSet"]
            if remark_ok and vpcs_ok:
                return current
        if time.time() >= deadline:
            module.fail_json(
                msg="Timed out waiting for Private DNS zone convergence",
                zone=current,
                expected="absent" if absent else desired,
            )
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "zone_id": {"type": "str"},
            "domain": {"type": "str"},
            "remark": {"type": "str", "default": ""},
            "vpcs": {"type": "list", "elements": "dict", "options": {"region": {"type": "str", "required": True}, "vpc_id": {"type": "str", "required": True}}},
            "tags": {"type": "dict"},
        },
        required_one_of=[("zone_id", "domain")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p["zone_id"] and not p["domain"]:
        module.fail_json(msg="domain is required to create a private zone")
    module.require_sdk()
    models, client_module = _load_private_dns()
    client = module.create_client(client_module.PrivatednsClient, "privatedns.tencentcloudapi.com")
    try:
        current = find_zone(module, client, models, p["zone_id"], p["domain"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, zone=None, msg="Private DNS zone is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), zone=current, msg="Would delete private DNS zone")
            request = models.DeletePrivateZoneRequest()
            request.ZoneId = current["ZoneId"]
            module.sdk_call(client.DeletePrivateZone, request)
            wait_for_zone(module, client, models, current["ZoneId"], absent=True)
            module.exit_json(changed=True, **(diff or {}), zone=None, msg="Private DNS zone deleted")
        desired = {"Domain": p["domain"], "Remark": p["remark"]}
        if p["vpcs"] is not None:
            desired["VpcSet"] = _vpcs(p["vpcs"])
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), zone=None, msg="Would create private DNS zone")
            response = module.sdk_call(client.CreatePrivateZone, build_create_request(models, p))
            current = wait_for_zone(module, client, models, getattr(response, "ZoneId", None), desired)
            module.exit_json(changed=True, **(diff or {}), zone=current, msg="Private DNS zone created")
        remark_drift = (current.get("Remark") or "") != p["remark"]
        vpc_drift = p["vpcs"] is not None and _vpcs(current.get("VpcSet")) != _vpcs(p["vpcs"])
        if not remark_drift and not vpc_drift:
            module.exit_json(changed=False, zone=current, msg="Private DNS zone is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), zone=current, msg="Would update private DNS zone")
        if remark_drift:
            request = models.ModifyPrivateZoneRequest()
            request.ZoneId, request.Remark = current["ZoneId"], p["remark"]
            module.sdk_call(client.ModifyPrivateZone, request)
        if vpc_drift:
            request = models.ModifyPrivateZoneVpcRequest()
            request.ZoneId, request.VpcSet = current["ZoneId"], build_vpcs(models, p["vpcs"])
            module.sdk_call(client.ModifyPrivateZoneVpc, request)
        current = wait_for_zone(module, client, models, current["ZoneId"], desired)
        module.exit_json(changed=True, **(diff or {}), zone=current, msg="Private DNS zone updated")
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )


def main():
    run_module()


if __name__ == "__main__":
    main()
