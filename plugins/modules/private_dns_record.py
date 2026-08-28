#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: private_dns_record
short_description: Manage a Tencent Cloud Private DNS record
version_added: "0.13.0"
description: Creates, updates and deletes records within a Tencent Cloud Private DNS zone.
options:
  state: {description: Desired record state., type: str, choices: [present, absent], default: present}
  zone_id: {description: Parent private zone ID., type: str, required: true}
  record_id: {description: Existing private record ID., type: str}
  subdomain: {description: Record owner name such as C(www) or C(@)., type: str}
  record_type: {description: DNS record type., type: str, choices: [A, AAAA, CNAME, MX, TXT, PTR, SRV]}
  value: {description: DNS record value., type: str}
  ttl: {description: Record TTL in seconds., type: int, default: 300}
  mx: {description: MX priority., type: int}
  weight: {description: Record weight., type: int}
  remark: {description: Record remark., type: str, default: ''}
  retries: {description: Number of retries for transient SDK failures., type: int, default: 5}
  waiter_delay: {description: Seconds between state-polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent value appended to SDK requests., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.private_dns_record:
    zone_id: zone-abc123
    subdomain: api
    record_type: A
    value: 10.0.0.8
'''
RETURN = r'''
record: {description: Private DNS record metadata, type: dict, returned: always}
'''

import json
import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_private_dns():
    from tencentcloud.privatedns.v20201028 import models, privatedns_client

    return models, privatedns_client


def _dict(value):
    return json.loads(value.to_json_string()) if value else None


def find_record(module, client, models, zone_id, record_id, subdomain, record_type):
    offset, matches = 0, []
    while True:
        request = models.DescribePrivateZoneRecordListRequest()
        request.ZoneId, request.Offset, request.Limit = zone_id, offset, 100
        response = module.sdk_call(client.DescribePrivateZoneRecordList, request)
        items = list(getattr(response, "RecordSet", None) or [])
        for item in items:
            value = _dict(item)
            if (record_id and value.get("RecordId") == record_id) or (
                not record_id and value.get("SubDomain") == subdomain and value.get("RecordType") == record_type
            ):
                matches.append(value)
        offset += len(items)
        if not items or offset >= int(getattr(response, "TotalCount", 0) or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple private DNS records match; specify record_id")
    return matches[0] if matches else None


def wait_for_record(module, client, models, zone_id, record_id, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_record(module, client, models, zone_id, record_id, None, None)
        if absent and current is None:
            return None
        if not absent and current and all(current.get(key) == value for key, value in desired.items()):
            return current
        if time.time() >= deadline:
            module.fail_json(
                msg="Timed out waiting for Private DNS record convergence",
                record=current, expected="absent" if absent else desired,
            )
        time.sleep(module.params["waiter_delay"])


def _apply(request, params):
    request.ZoneId, request.SubDomain = params["zone_id"], params["subdomain"]
    request.RecordType, request.RecordValue = params["record_type"], params["value"]
    request.TTL, request.Remark = params["ttl"], params["remark"]
    if params.get("mx") is not None:
        request.MX = params["mx"]
    if params.get("weight") is not None:
        request.Weight = params["weight"]
    return request


def build_create_request(models, params):
    return _apply(models.CreatePrivateZoneRecordRequest(), params)


def build_update_request(models, params, record_id):
    request = _apply(models.ModifyPrivateZoneRecordRequest(), params)
    request.RecordId = record_id
    return request


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "zone_id": {"type": "str", "required": True},
            "record_id": {"type": "str"},
            "subdomain": {"type": "str"},
            "record_type": {"type": "str", "choices": ["A", "AAAA", "CNAME", "MX", "TXT", "PTR", "SRV"]},
            "value": {"type": "str"},
            "ttl": {"type": "int", "default": 300},
            "mx": {"type": "int"},
            "weight": {"type": "int"},
            "remark": {"type": "str", "default": ""},
        },
        required_if=[("state", "present", ["subdomain", "record_type", "value"])],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "absent" and not p["record_id"] and not (p["subdomain"] and p["record_type"]):
        module.fail_json(msg="record_id or subdomain and record_type are required when state=absent")
    module.require_sdk()
    models, client_module = _load_private_dns()
    client = module.create_client(client_module.PrivatednsClient, "privatedns.tencentcloudapi.com")
    try:
        current = find_record(module, client, models, p["zone_id"], p["record_id"], p["subdomain"], p["record_type"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, record=None, msg="Private DNS record is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), record=current, msg="Would delete private DNS record")
            request = models.DeletePrivateZoneRecordRequest()
            request.ZoneId, request.RecordId = p["zone_id"], current["RecordId"]
            module.sdk_call(client.DeletePrivateZoneRecord, request)
            wait_for_record(module, client, models, p["zone_id"], current["RecordId"], absent=True)
            module.exit_json(changed=True, **(diff or {}), record=None, msg="Private DNS record deleted")
        desired = {
            "SubDomain": p["subdomain"],
            "RecordType": p["record_type"],
            "RecordValue": p["value"],
            "TTL": p["ttl"],
            "Remark": p["remark"],
        }
        if p["mx"] is not None:
            desired["MX"] = p["mx"]
        if p["weight"] is not None:
            desired["Weight"] = p["weight"]
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), record=None, msg="Would create private DNS record")
            response = module.sdk_call(client.CreatePrivateZoneRecord, build_create_request(models, p))
            current = wait_for_record(
                module, client, models, p["zone_id"], getattr(response, "RecordId", None), desired,
            )
            module.exit_json(changed=True, **(diff or {}), record=current, msg="Private DNS record created")
        changed = any(current.get(key) != value for key, value in desired.items())
        if not changed:
            module.exit_json(changed=False, record=current, msg="Private DNS record is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), record=current, msg="Would update private DNS record")
        module.sdk_call(client.ModifyPrivateZoneRecord, build_update_request(models, p, current["RecordId"]))
        current = wait_for_record(module, client, models, p["zone_id"], current["RecordId"], desired)
        module.exit_json(changed=True, **(diff or {}), record=current, msg="Private DNS record updated")
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
