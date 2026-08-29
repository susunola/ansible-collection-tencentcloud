#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: teo_dns_record
short_description: Manage Tencent Cloud TEO DNS records
version_added: "0.14.0"
description: Creates, updates and deletes DNS records within an EdgeOne zone.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  zone_id: {description: EdgeOne zone ID., type: str, required: true}
  record_id: {description: Existing DNS record ID., type: str}
  name: {description: DNS record name., type: str}
  record_type: {description: DNS record type., type: str, choices: [A, AAAA, CNAME, TXT, NS, CAA, SRV, MX]}
  content: {description: DNS record content., type: str}
  location: {description: DNS routing location., type: str, default: Default}
  ttl: {description: Cache duration in seconds., type: int, default: 300}
  weight: {description: DNS response weight., type: int, default: -1}
  priority: {description: MX priority., type: int, default: 0}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.teo_dns_record:
    zone_id: zone-xxxxxxxx
    name: api.example.com
    record_type: A
    content: 203.0.113.10
    ttl: 300
'''
RETURN = r'''
record: {description: EdgeOne DNS record metadata., type: dict, returned: always}
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_teo():
    from tencentcloud.teo.v20220901 import models, teo_client
    return models, teo_client


def build_describe_request(models, zone_id, record_id=None, name=None):
    request = models.DescribeDnsRecordsRequest()
    request.ZoneId, request.Offset, request.Limit = zone_id, 0, 1000
    filters = []
    for key, value in (("id", record_id), ("name", name)):
        if value:
            item = models.AdvancedFilter()
            item.Name, item.Values = key, [value]
            filters.append(item)
    request.Filters, request.Match = filters, "all"
    return request


def _apply(record, params):
    record.Name, record.Type, record.Content = params["name"], params["record_type"], params["content"]
    record.Location, record.TTL = params["location"], params["ttl"]
    record.Weight, record.Priority = params["weight"], params["priority"]
    return record


def build_create_request(models, params):
    request = models.CreateDnsRecordRequest()
    request.ZoneId = params["zone_id"]
    return _apply(request, params)


def build_update_request(models, record_id, params):
    request = models.ModifyDnsRecordsRequest()
    request.ZoneId = params["zone_id"]
    record = _apply(models.DnsRecord(), params)
    record.RecordId = record_id
    request.DnsRecords = [record]
    return request


def build_delete_request(models, zone_id, record_id):
    request = models.DeleteDnsRecordsRequest()
    request.ZoneId, request.RecordIds = zone_id, [record_id]
    return request


def find_record(module, client, models, zone_id, record_id=None, name=None):
    response = module.sdk_call(client.DescribeDnsRecords, build_describe_request(models, zone_id, record_id, name))
    matches = []
    for item in (response.DnsRecords or []):
        value = item._serialize(allow_none=True)
        if (record_id and value.get("RecordId") == record_id) or (not record_id and value.get("Name") == name):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple EdgeOne DNS records have the requested name; use record_id", name=name)
    return matches[0] if matches else None


def _desired(params):
    return {"Name": params["name"], "Type": params["record_type"], "Content": params["content"], "Location": params["location"], "TTL": params["ttl"], "Weight": params["weight"], "Priority": params["priority"]}


def _matches(current, desired):
    return all(current.get(key) == value for key, value in desired.items())


def wait_for_record(module, client, models, record_id, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_record(module, client, models, module.params["zone_id"], record_id, None)
        if absent and current is None:
            return None
        if not absent and current and _matches(current, desired):
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for EdgeOne DNS record convergence", record=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"type": "str", "choices": ["present", "absent"], "default": "present"}, "zone_id": {"type": "str", "required": True}, "record_id": {"type": "str"}, "name": {"type": "str"}, "record_type": {"type": "str", "choices": ["A", "AAAA", "CNAME", "TXT", "NS", "CAA", "SRV", "MX"]}, "content": {"type": "str"}, "location": {"type": "str", "default": "Default"}, "ttl": {"type": "int", "default": 300}, "weight": {"type": "int", "default": -1}, "priority": {"type": "int", "default": 0}}, required_one_of=[("record_id", "name")], required_if=[("state", "present", ("name", "record_type", "content"))], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, client_module = _load_teo()
    client = module.create_client(client_module.TeoClient, "teo.tencentcloudapi.com")
    try:
        current = find_record(module, client, models, p["zone_id"], p["record_id"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, record=None, msg="EdgeOne DNS record is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), record=current, msg="Would delete EdgeOne DNS record")
            module.sdk_call(client.DeleteDnsRecords, build_delete_request(models, p["zone_id"], current["RecordId"]))
            wait_for_record(module, client, models, current["RecordId"], absent=True)
            module.exit_json(changed=True, **(diff or {}), record=None, msg="EdgeOne DNS record deleted")
        desired = _desired(p)
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), record=None, msg="Would create EdgeOne DNS record")
            response = module.sdk_call(client.CreateDnsRecord, build_create_request(models, p))
            current = wait_for_record(module, client, models, response.RecordId, desired)
            module.exit_json(changed=True, **(diff or {}), record=current, msg="EdgeOne DNS record created")
        if _matches(current, desired):
            module.exit_json(changed=False, record=current, msg="EdgeOne DNS record is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), record=current, msg="Would update EdgeOne DNS record")
        module.sdk_call(client.ModifyDnsRecords, build_update_request(models, current["RecordId"], p))
        current = wait_for_record(module, client, models, current["RecordId"], desired)
        module.exit_json(changed=True, **(diff or {}), record=current, msg="EdgeOne DNS record updated")
    except Exception as exc:
        module.fail_json(msg="Tencent Cloud API request failed", error=str(exc), error_code=getattr(exc, "get_code", lambda: None)(), request_id=getattr(exc, "get_request_id", lambda: None)())


def main():
    run_module()


if __name__ == "__main__":
    main()
