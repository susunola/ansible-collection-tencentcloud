#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: dnspod_custom_line
short_description: Manage DNSPod domain custom lines
version_added: "0.14.0"
description: Creates, updates and deletes a domain-scoped DNSPod custom routing line.
options:
  state:
    description:
      - C(present) creates the custom line with V(CreateDomainCustomLine) when it does not exist and updates
        it with V(ModifyDomainCustomLine) when it differs. C(absent) deletes it with V(DeleteDomainCustomLine).
    type: str
    choices: [present, absent]
    default: present
  domain:
    description:
      - Domain name.
    type: str
  domain_id:
    description:
      - Domain ID, which takes precedence over domain.
    type: int
  name:
    description:
      - Custom line name and immutable identity.
    type: str
    required: true
  area:
    description:
      - Custom line IP range expression separated with hyphens.
    type: str

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
attributes:
  check_mode:
    description:
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  diff_mode:
    description:
      - Returns the difference between the observed and the requested state
        when the task runs with C(--diff).
    support: full
  idempotent:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
seealso:
  - module: susunola.tencentcloud.dnspod_custom_line_info
    description: Gather information about Tencent Cloud DNSPOD domain custom lines.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dnspod_custom_line:
    domain: example.com
    name: office-network
    area: 203.0.113.1-203.0.113.254

- name: Delete the custom line
  susunola.tencentcloud.dnspod_custom_line:
    state: absent
    domain: example.com
    name: office-network
"""
RETURN = r"""custom_line:
  description:
    - DNSPod custom line metadata.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    Name: office-network
    Area: 198.51.100.1-198.51.100.100
"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.dnspod.v20210323 import dnspod_client, models

    return models, dnspod_client


def _scope(request, p):
    request.Domain, request.DomainId = p.get("domain"), p.get("domain_id")
    return request


def describe_request(models, p):
    return _scope(models.DescribeDomainCustomLineListRequest(), p)


def create_request(models, p):
    request = _scope(models.CreateDomainCustomLineRequest(), p)
    request.Name, request.Area = p["name"], p["area"]
    return request


def update_request(models, p):
    request = _scope(models.ModifyDomainCustomLineRequest(), p)
    request.Name, request.PreName, request.Area = p["name"], p["name"], p["area"]
    return request


def delete_request(models, p):
    request = _scope(models.DeleteDomainCustomLineRequest(), p)
    request.Name = p["name"]
    return request


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeDomainCustomLineList, describe_request(models, p))
    for item in response.LineList or []:
        value = item._serialize(allow_none=True)
        if value.get("Name") == p["name"]:
            return value
    return None


def comparable(value):
    return {"Name": value.get("Name"), "Area": value.get("Area")}


def desired(p):
    return {"Name": p["name"], "Area": p["area"]}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "domain": {},
            "domain_id": {"type": "int"},
            "name": {"required": True},
            "area": {},
        },
        required_one_of=[("domain", "domain_id")],
        required_if=[("state", "present", ["area"])],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DnspodClient, "dnspod.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, custom_line=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteDomainCustomLine, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), custom_line=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, custom_line=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(
                client.ModifyDomainCustomLine if current else client.CreateDomainCustomLine, update_request(models, p) if current else create_request(models, p)
            )
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), custom_line=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
