#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: dnspod_record
short_description: Manage Tencent Cloud DNSPod DNS records
version_added: "0.12.0"
description:
  - Create, update and delete DNS records through the C(dnspod.v20210323)
    API.
  - This module is idempotent. Running it twice leaves the record unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
  - A record is identified by the combination of its domain, subdomain
    (record name), record type and record line. Updating any of
    O(value), O(ttl), O(weight), O(mx), O(remark) or O(status) on an
    existing record issues a single V(ModifyRecord) call.
options:
  state:
    description:
      - C(present) creates the record when it does not exist and updates its
        attributes when it does.
      - C(absent) deletes the record.
    type: str
    choices: [present, absent]
    default: present
  domain:
    description:
      - The domain the record belongs to, e.g. C(example.com).
      - Either O(domain) or O(domain_id) is required.
    type: str
  domain_id:
    description:
      - Numeric ID of the domain, as an alternative to O(domain).
    type: int
  subdomain:
    description:
      - Record name, e.g. C(www) or C(@) for the apex, written to
        V(CreateRecordRequest.SubDomain).
    type: str
    default: "@"
  record_type:
    description:
      - DNS record type, e.g. C(A), C(AAAA), C(CNAME), C(MX), C(TXT),
        C(SRV), C(NS), written to V(CreateRecordRequest.RecordType).
    type: str
    required: true
  record_line:
    description:
      - Record line, e.g. C(默认) or C(电信), written to
        V(CreateRecordRequest.RecordLine).
    type: str
    default: "默认"
  value:
    description:
      - Record value, e.g. an IP address for A records or a target host for
        CNAME, written to V(CreateRecordRequest.Value).
      - Required when O(state=present) and the record does not exist yet.
    type: str
  ttl:
    description:
      - Time to live in seconds, written to V(CreateRecordRequest.TTL).
    type: int
  weight:
    description:
      - Record weight for line-based load balancing, written to
        V(CreateRecordRequest.Weight).
    type: int
  mx:
    description:
      - MX priority, written to V(CreateRecordRequest.MX).
      - Only meaningful for MX records.
    type: int
  remark:
    description:
      - Free-form remark on the record, written to
        V(CreateRecordRequest.Remark).
    type: str
  status:
    description:
      - Enable or disable the record, written to V(CreateRecordRequest.Status).
    type: str
    choices: [ENABLE, DISABLE]
  retries:
    description: Number of retries for transient SDK failures.
    type: int
    default: 5
  waiter_delay:
    description: Seconds to wait between state-polling attempts.
    type: int
    default: 5
  waiter_timeout:
    description: Overall timeout in seconds for state polling.
    type: int
    default: 120
  user_agent:
    description:
      - Value appended to the SDK User-Agent header so API usage can be
        attributed to this collection.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-dnspod) package on the controller.
  - DNS propagation is asynchronous; this module does not wait for the change
    to take effect outside DNSPod.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create an A record
  susunola.tencentcloud.dnspod_record:
    region: ap-guangzhou
    state: present
    domain: example.com
    subdomain: www
    record_type: A
    value: 1.2.3.4
    ttl: 600

- name: Update its value and enable it
  susunola.tencentcloud.dnspod_record:
    region: ap-guangzhou
    state: present
    domain: example.com
    subdomain: www
    record_type: A
    record_line: 默认
    value: 5.6.7.8
    status: ENABLE

- name: Delete the record
  susunola.tencentcloud.dnspod_record:
    region: ap-guangzhou
    state: absent
    domain: example.com
    subdomain: www
    record_type: A
'''

RETURN = r'''
record:
  description: The record as reported by V(DescribeRecordList) after the
    operation.
  returned: success
  type: dict
  sample:
    RecordId: 1234567
    Name: www
    Type: A
    Value: 1.2.3.4
    Line: 默认
    TTL: 600
    Status: ENABLE
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_dnspod():
    from tencentcloud.dnspod.v20210323 import models, dnspod_client
    return models, dnspod_client


def build_describe_request(models, domain, domain_id, subdomain, record_type, record_line):
    request = models.DescribeRecordListRequest()
    request.Limit = 100
    if domain:
        request.Domain = domain
    if domain_id:
        request.DomainId = domain_id
    if subdomain:
        request.Subdomain = subdomain
    if record_type:
        request.RecordType = record_type
    if record_line and record_line != "默认":
        request.RecordLine = record_line
    return request


def find_record(module, client, models, domain, domain_id, subdomain, record_type, record_line):
    """Return the matching record dict or None."""
    request = build_describe_request(models, domain, domain_id, subdomain, record_type, record_line)
    response = module.sdk_call(client.DescribeRecordList, request)
    records = response.RecordList or []
    if record_line and record_line != "默认":
        records = [r for r in records if (r.Line or "") == record_line]
    record = records[0] if records else None
    if record is None:
        return None
    return record._serialize(allow_none=True)


def _create(module, client, models, params):
    request = models.CreateRecordRequest()
    if params["domain"]:
        request.Domain = params["domain"]
    if params["domain_id"]:
        request.DomainId = params["domain_id"]
    request.SubDomain = params["subdomain"]
    request.RecordType = params["record_type"]
    request.RecordLine = params["record_line"]
    request.Value = params["value"]
    for key, attr in (
        ("ttl", "TTL"),
        ("weight", "Weight"),
        ("mx", "MX"),
        ("remark", "Remark"),
        ("status", "Status"),
    ):
        value = params[key]
        if value is not None:
            setattr(request, attr, value)
    response = module.sdk_call(client.CreateRecord, request)
    return response.RecordId


def _update(module, client, models, params, record_id):
    request = models.ModifyRecordRequest()
    if params["domain"]:
        request.Domain = params["domain"]
    if params["domain_id"]:
        request.DomainId = params["domain_id"]
    request.RecordId = record_id
    request.SubDomain = params["subdomain"]
    request.RecordType = params["record_type"]
    request.RecordLine = params["record_line"]
    request.Value = params["value"]
    for key, attr in (
        ("ttl", "TTL"),
        ("weight", "Weight"),
        ("mx", "MX"),
        ("remark", "Remark"),
        ("status", "Status"),
    ):
        value = params[key]
        if value is not None:
            setattr(request, attr, value)
    module.sdk_call(client.ModifyRecord, request)


def _delete(module, client, models, params, record_id):
    request = models.DeleteRecordRequest()
    if params["domain"]:
        request.Domain = params["domain"]
    if params["domain_id"]:
        request.DomainId = params["domain_id"]
    request.RecordId = record_id
    module.sdk_call(client.DeleteRecord, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "domain": {"type": "str"},
            "domain_id": {"type": "int"},
            "subdomain": {"type": "str", "default": "@"},
            "record_type": {"type": "str", "required": True},
            "record_line": {"type": "str", "default": "默认"},
            "value": {"type": "str"},
            "ttl": {"type": "int"},
            "weight": {"type": "int"},
            "mx": {"type": "int"},
            "remark": {"type": "str"},
            "status": {"type": "str", "choices": ["ENABLE", "DISABLE"]},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    domain = module.params["domain"]
    domain_id = module.params["domain_id"]
    if not domain and not domain_id:
        module.fail_json(msg="domain or domain_id is required to identify the record")

    models, dnspod_client = _load_dnspod()
    client = module.create_client(dnspod_client.DnspodClient, "dnspod.tencentcloudapi.com")

    try:
        current = find_record(
            module, client, models,
            domain, domain_id,
            module.params["subdomain"],
            module.params["record_type"],
            module.params["record_line"],
        )
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="DNS record already absent")
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete DNS record")
        _delete(module, client, models, module.params, current["RecordId"])
        module.exit_json(changed=True, **(diff or {}), record=None, msg="DNS record deleted")

    # state == present
    desired_value = module.params["value"]
    if current is None:
        if desired_value is None:
            module.fail_json(msg="value is required when creating a DNS record")
        desired = {
            "Name": module.params["subdomain"],
            "Type": module.params["record_type"],
            "Line": module.params["record_line"],
            "Value": desired_value,
            "TTL": module.params["ttl"] or 600,
        }
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create DNS record")
        record_id = _create(module, client, models, module.params)
        record = find_record(
            module, client, models,
            domain, domain_id,
            module.params["subdomain"],
            module.params["record_type"],
            module.params["record_line"],
        )
        module.exit_json(changed=True, **(diff or {}), record=record, msg="DNS record created (id %s)" % record_id)

    record_id = current["RecordId"]
    changes = []
    if desired_value is not None and current.get("Value") != desired_value:
        changes.append("value")
    ttl = module.params["ttl"]
    if ttl is not None and current.get("TTL") != ttl:
        changes.append("ttl")
    weight = module.params["weight"]
    if weight is not None and current.get("Weight") != weight:
        changes.append("weight")
    mx = module.params["mx"]
    if mx is not None and current.get("MX") != mx:
        changes.append("mx")
    remark = module.params["remark"]
    if remark is not None and current.get("Remark") != remark:
        changes.append("remark")
    status = module.params["status"]
    if status is not None and current.get("Status") != status:
        changes.append("status")

    if not changes:
        module.exit_json(changed=False, record=current, msg="DNS record is up to date")

    desired = {
        "Value": desired_value if desired_value is not None else current.get("Value"),
        "TTL": ttl if ttl is not None else current.get("TTL"),
        "Weight": weight if weight is not None else current.get("Weight"),
        "MX": mx if mx is not None else current.get("MX"),
        "Remark": remark if remark is not None else current.get("Remark"),
        "Status": status if status is not None else current.get("Status"),
    }
    diff = maybe_diff(module, current, desired)
    if module.check_mode:
        module.exit_json(changed=True, **(diff or {}), msg="Would update DNS record")

    _update(module, client, models, module.params, record_id)
    record = find_record(
        module, client, models,
        domain, domain_id,
        module.params["subdomain"],
        module.params["record_type"],
        module.params["record_line"],
    )
    module.exit_json(changed=True, **(diff or {}), record=record, msg="DNS record updated")


def main():
    run_module()


if __name__ == "__main__":
    main()
