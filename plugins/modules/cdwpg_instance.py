#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cdwpg_instance
short_description: Manage Tencent Cloud CDW PostgreSQL instances
version_added: "0.14.0"
description: Creates, renames, waits for and destroys CDW PostgreSQL instances.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, description: Existing instance ID.}
  name: {type: str, description: Instance name used for lookup and rename.}
  zone: {type: str, description: Creation-time availability zone.}
  vpc_id: {type: str, description: Creation-time VPC ID.}
  subnet_id: {type: str, description: Creation-time subnet ID.}
  charge_properties: {type: dict, description: SDK ChargeProperties payload.}
  admin_password: {type: str, description: Initial administrator password.}
  resources: {type: list, elements: dict, description: SDK ResourceSpecNew payloads for the complete CN and DN topology.}
  tags: {type: dict, description: Creation-time tags.}
  product_version: {type: str, description: Creation-time product version.}
  wait: {type: bool, default: true, description: Wait for serving or absent convergence.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 10, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 1800, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cdwpg_instance:
    name: analytics-pg
    zone: ap-guangzhou-3
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    charge_properties: {ChargeType: POSTPAID_BY_HOUR}
    admin_password: "{{ vault_cdwpg_password }}"
    product_version: 6.3.0
    resources:
      - {SpecName: S_4_16_H, Count: 2, Type: cn}
      - {SpecName: S_8_32_H, Count: 3, Type: dn}
"""
RETURN = r"""instance: {description: Effective CDW PostgreSQL instance metadata., type: dict, returned: always}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state, wait_for_task


def _load():
    from tencentcloud.cdwpg.v20201230 import models, cdwpg_client

    return models, cdwpg_client


def _model(cls, value):
    if value is None:
        return None
    x = cls()
    x.from_json_string(json.dumps(value))
    return x


def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        x = models.Tag()
        x.TagKey, x.TagValue = str(key), str(value)
        result.append(x)
    return result


def describe_request(models, p, offset=0):
    r = models.DescribeInstancesRequest()
    r.SearchInstanceId = p.get("instance_id")
    r.SearchInstanceName = None if p.get("instance_id") else p.get("name")
    r.Offset, r.Limit = offset, 100
    return r


def state_request(models, instance_id):
    r = models.DescribeInstanceStateRequest()
    r.InstanceId = instance_id
    return r


def create_request(models, p):
    r = models.CreateInstanceByApiRequest()
    r.InstanceName, r.Zone, r.UserVPCId, r.UserSubnetId = p["name"], p["zone"], p["vpc_id"], p["subnet_id"]
    r.ChargeProperties = _model(models.ChargeProperties, p["charge_properties"])
    r.AdminPassword = p["admin_password"]
    r.Resources = [_model(models.ResourceSpecNew, x) for x in p["resources"]]
    r.TagItems = _tags(models, p.get("tags"))
    r.ProductVersion = p.get("product_version")
    return r


def update_request(models, instance_id, name):
    r = models.ModifyInstanceRequest()
    r.InstanceId, r.InstanceName = instance_id, name
    return r


def delete_request(models, instance_id):
    r = models.DestroyInstanceByApiRequest()
    r.InstanceId = instance_id
    return r


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeInstances, describe_request(models, p, offset))
        page = response.InstancesList or []
        for item in page:
            value = item._serialize(allow_none=True)
            item_id = value.get("InstanceId") or value.get("InstanceID")
            if (p.get("instance_id") and item_id == p["instance_id"]) or (not p.get("instance_id") and value.get("InstanceName") == p.get("name")):
                matches.append(value)
        offset += len(page)
        if not page or offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple CDW PostgreSQL instances matched; specify instance_id")
    return matches[0] if matches else None


def _id(value):
    return value.get("InstanceId") or value.get("InstanceID")


def wait_present(module, client, models, p, name):
    def poll():
        current = find(module, client, models, p)
        if not current:
            return "RUNNING", None, current
        state = module.sdk_call(client.DescribeInstanceState, state_request(models, _id(current)))
        value = state.InstanceState
        if value == "Serving" and current.get("InstanceName") == name:
            return "SUCCESS", None, current
        if value in ("CreateFailed", "Failed"):
            return "FAILED", state.FlowMsg, current
        return "RUNNING", None, current

    return wait_for_task(module, poll, timeout=p["waiter_timeout"], delay=p["waiter_delay"], success_statuses=("SUCCESS",), failure_statuses=("FAILED",))


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "instance_id": {},
        "name": {},
        "zone": {},
        "vpc_id": {},
        "subnet_id": {},
        "charge_properties": {"type": "dict"},
        "admin_password": {"no_log": True},
        "resources": {"type": "list", "elements": "dict"},
        "tags": {"type": "dict"},
        "product_version": {},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 10},
        "waiter_timeout": {"type": "int", "default": 1800},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("instance_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CdwpgClient, "cdwpg.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, instance=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                p["instance_id"] = _id(current)
                module.sdk_call(client.DestroyInstanceByApi, delete_request(models, p["instance_id"]))
                (
                    wait_for_state(
                        module,
                        lambda: "absent" if find(module, client, models, p) is None else "present",
                        {"absent"},
                        timeout=p["waiter_timeout"],
                        delay=p["waiter_delay"],
                    )
                    if p["wait"]
                    else None
                )
            module.exit_json(changed=True, **(diff or {}), instance=None)
        if not current:
            required = ("name", "zone", "vpc_id", "subnet_id", "charge_properties", "admin_password", "resources")
            missing = [x for x in required if not p.get(x)]
            if missing:
                module.fail_json(msg="creation parameters are required for a CDW PostgreSQL instance", missing=missing)
            target = {"InstanceName": p["name"], "Zone": p["zone"], "Version": p.get("product_version")}
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                response = module.sdk_call(client.CreateInstanceByApi, create_request(models, p))
                if response.ErrorMsg:
                    module.fail_json(msg=response.ErrorMsg)
                p["instance_id"] = response.InstanceId
                current = wait_present(module, client, models, p, p["name"]) if p["wait"] else find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), instance=current if not module.check_mode else target)
        name = p.get("name") or current.get("InstanceName")
        if name == current.get("InstanceName"):
            module.exit_json(changed=False, instance=current)
        diff = maybe_diff(module, {"InstanceName": current.get("InstanceName")}, {"InstanceName": name})
        if not module.check_mode:
            p["instance_id"] = _id(current)
            module.sdk_call(client.ModifyInstance, update_request(models, p["instance_id"], name))
            current = wait_present(module, client, models, p, name) if p["wait"] else find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), instance=current if not module.check_mode else {"InstanceName": name})
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
