#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: havip
short_description: Manage Tencent Cloud VPC high-availability virtual IPs
version_added: "0.14.0"
description: Creates, renames and deletes HAVIPs with guarded replacement of immutable network placement.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  havip_id: {type: str, description: Existing HAVIP ID.}
  name: {type: str, description: HAVIP name.}
  vpc_id: {type: str, description: VPC ID; immutable after creation.}
  subnet_id: {type: str, description: Subnet ID; immutable after creation.}
  vip: {type: str, description: Requested private virtual IP; omit for automatic allocation.}
  check_associate: {type: bool, default: false, description: Restrict HAVIP drift to its declared associations.}
  force_replace: {type: bool, default: false, description: Recreate the HAVIP when immutable placement changes.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.havip:
    name: database-vip
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    vip: 10.0.1.100
    check_associate: true
"""
RETURN = r"""havip: {description: Effective HAVIP metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.vpc.v20170312 import models, vpc_client

    return models, vpc_client


def describe_request(models, p):
    request = models.DescribeHaVipsRequest()
    request.Limit = 100
    if p.get("havip_id"):
        request.HaVipIds = [p["havip_id"]]
    elif p.get("name"):
        item = models.Filter()
        item.Name, item.Values = "havip-name", [p["name"]]
        request.Filters = [item]
    return request


def create_request(models, p):
    request = models.CreateHaVipRequest()
    request.VpcId, request.HaVipName, request.SubnetId = p["vpc_id"], p["name"], p["subnet_id"]
    request.Vip, request.CheckAssociate = p.get("vip"), p["check_associate"]
    return request


def update_request(models, havip_id, name):
    request = models.ModifyHaVipAttributeRequest()
    request.HaVipId, request.HaVipName = havip_id, name
    return request


def delete_request(models, havip_id):
    request = models.DeleteHaVipRequest()
    request.HaVipId = havip_id
    return request


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeHaVips, describe_request(models, p))
    matches = []
    for item in response.HaVipSet or []:
        value = item._serialize(allow_none=True)
        if (p.get("havip_id") and value.get("HaVipId") == p["havip_id"]) or (not p.get("havip_id") and value.get("HaVipName") == p.get("name")):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple HAVIPs matched; specify havip_id")
    return matches[0] if matches else None


def comparable(v):
    return {
        "HaVipName": v.get("HaVipName"),
        "VpcId": v.get("VpcId"),
        "SubnetId": v.get("SubnetId"),
        "Vip": v.get("Vip"),
        "CheckAssociate": bool(v.get("CheckAssociate")),
    }


def desired(p, current=None):
    return {
        "HaVipName": p["name"],
        "VpcId": p["vpc_id"],
        "SubnetId": p["subnet_id"],
        "Vip": p.get("vip") or (current or {}).get("Vip"),
        "CheckAssociate": p["check_associate"],
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "havip_id": {},
            "name": {},
            "vpc_id": {},
            "subnet_id": {},
            "vip": {},
            "check_associate": {"type": "bool", "default": False},
            "force_replace": {"type": "bool", "default": False},
        },
        required_one_of=[("havip_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and (not p.get("name") or not p.get("vpc_id") or not p.get("subnet_id")):
        module.fail_json(msg="name, vpc_id and subnet_id are required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.VpcClient, "vpc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, havip=None)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode:
                module.sdk_call(client.DeleteHaVip, delete_request(models, current["HaVipId"]))
            module.exit_json(changed=True, **(diff or {}), havip=current if module.check_mode else None)
        target = desired(p, current)
        before = comparable(current) if current else None
        replace = bool(
            current
            and (before["VpcId"], before["SubnetId"], before["Vip"], before["CheckAssociate"])
            != (target["VpcId"], target["SubnetId"], target["Vip"], target["CheckAssociate"])
        )
        if replace and not p["force_replace"]:
            module.fail_json(msg="HAVIP network placement is immutable; set force_replace=true to recreate it", current=before, desired=target)
        if before == target:
            module.exit_json(changed=False, havip=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if replace:
                module.sdk_call(client.DeleteHaVip, delete_request(models, current["HaVipId"]))
                current = None
            if current:
                module.sdk_call(client.ModifyHaVipAttribute, update_request(models, current["HaVipId"], p["name"]))
            else:
                p["havip_id"] = module.sdk_call(client.CreateHaVip, create_request(models, p)).HaVipId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), havip=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
