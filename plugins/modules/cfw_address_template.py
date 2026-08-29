#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cfw_address_template
short_description: Manage Tencent Cloud Cloud Firewall address templates
version_added: "0.14.0"
description: Creates, updates and deletes reusable Cloud Firewall IP or domain templates.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  uuid: {description: Existing address template UUID., type: str}
  name: {description: Address template name., type: str}
  template_type: {description: Address template type., type: str, choices: [ip, domain], default: ip}
  addresses: {description: Exact set of IP networks or domain names., type: list, elements: str}
  description: {description: Address template description., type: str, default: ''}
  ip_version: {description: IP version for IP templates., type: int, choices: [0, 1], default: 0}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cfw_address_template:
    name: trusted-networks
    template_type: ip
    addresses: [10.0.0.0/8, 192.168.0.0/16]
    description: Internal networks
'''
RETURN = r'''
template: {description: Cloud Firewall address template metadata., type: dict, returned: always}
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff

TYPES = {"ip": 1, "domain": 5}


def _load_cfw():
    from tencentcloud.cfw.v20190904 import cfw_client, models

    return models, cfw_client


def build_describe_request(models, uuid=None, name=None):
    request = models.DescribeAddressTemplateListRequest()
    request.Offset, request.Limit = 0, 100
    if uuid:
        request.Uuid = uuid
    if name:
        request.SearchValue = name
    return request


def _address_string(values):
    return ",".join(sorted(set(values or [])))


def _apply(request, params):
    request.Name, request.Detail = params["name"], params["description"]
    request.IpString, request.Type = _address_string(params["addresses"]), TYPES[params["template_type"]]
    return request


def build_create_request(models, params):
    request = _apply(models.CreateAddressTemplateRequest(), params)
    request.IpVersion = params["ip_version"]
    return request


def build_update_request(models, uuid, params):
    request = _apply(models.ModifyAddressTemplateRequest(), params)
    request.Uuid = uuid
    return request


def build_delete_request(models, uuid):
    request = models.DeleteAddressTemplateRequest()
    request.Uuid = uuid
    return request


def find_template(module, client, models, uuid=None, name=None):
    response = module.sdk_call(client.DescribeAddressTemplateList, build_describe_request(models, uuid, name))
    matches = []
    for item in response.Data or []:
        value = item._serialize(allow_none=True)
        if (uuid and value.get("Uuid") == uuid) or (not uuid and value.get("Name") == name):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple Cloud Firewall address templates have the requested name", name=name)
    return matches[0] if matches else None


def _desired(params):
    return {
        "Name": params["name"],
        "Detail": params["description"],
        "IpString": _address_string(params["addresses"]),
        "Type": TYPES[params["template_type"]],
        "IpVersion": params["ip_version"],
    }


def _matches(current, desired):
    actual = dict(current)
    actual["IpString"] = _address_string((actual.get("IpString") or "").split(","))
    return all(actual.get(key) == value for key, value in desired.items())


def wait_for_template(module, client, models, uuid, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_template(module, client, models, uuid, None)
        if absent and current is None:
            return None
        if not absent and current and _matches(current, desired):
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for Cloud Firewall address template convergence", template=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "uuid": {"type": "str"},
            "name": {"type": "str"},
            "template_type": {"type": "str", "choices": ["ip", "domain"], "default": "ip"},
            "addresses": {"type": "list", "elements": "str"},
            "description": {"type": "str", "default": ""},
            "ip_version": {"type": "int", "choices": [0, 1], "default": 0},
        },
        required_one_of=[("uuid", "name")],
        required_if=[("state", "present", ("name", "addresses"))],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, client_module = _load_cfw()
    client = module.create_client(client_module.CfwClient, "cfw.tencentcloudapi.com")
    try:
        current = find_template(module, client, models, p["uuid"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, template=None, msg="Cloud Firewall address template is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), template=current, msg="Would delete Cloud Firewall address template")
            module.sdk_call(client.DeleteAddressTemplate, build_delete_request(models, current["Uuid"]))
            wait_for_template(module, client, models, current["Uuid"], absent=True)
            module.exit_json(changed=True, **(diff or {}), template=None, msg="Cloud Firewall address template deleted")
        desired = _desired(p)
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), template=None, msg="Would create Cloud Firewall address template")
            response = module.sdk_call(client.CreateAddressTemplate, build_create_request(models, p))
            current = wait_for_template(module, client, models, response.Uuid, desired)
            module.exit_json(changed=True, **(diff or {}), template=current, msg="Cloud Firewall address template created")
        if _matches(current, desired):
            module.exit_json(changed=False, template=current, msg="Cloud Firewall address template is up to date")
        if current.get("IpVersion") != desired["IpVersion"]:
            module.fail_json(
                msg="Cloud Firewall address template ip_version cannot be changed; recreate the template",
                current_ip_version=current.get("IpVersion"),
                requested_ip_version=desired["IpVersion"],
            )
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), template=current, msg="Would update Cloud Firewall address template")
        module.sdk_call(client.ModifyAddressTemplate, build_update_request(models, current["Uuid"], p))
        current = wait_for_template(module, client, models, current["Uuid"], desired)
        module.exit_json(changed=True, **(diff or {}), template=current, msg="Cloud Firewall address template updated")
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
