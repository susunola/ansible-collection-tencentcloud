#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: havip_association
short_description: Manage Tencent Cloud HAVIP drift-scope associations
version_added: "0.14.0"
description: Associates or disassociates a CVM instance or elastic network interface with a HAVIP drift scope.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired association state.}
  havip_id: {type: str, required: true, description: HAVIP ID.}
  instance_id: {type: str, required: true, description: CVM instance or ENI ID.}
  instance_type: {type: str, choices: [CVM, ENI], required: true, description: Associated resource type.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.havip_association:
    havip_id: havip-xxxxxxxx
    instance_id: ins-xxxxxxxx
    instance_type: CVM
'''
RETURN = r'''association: {description: Effective HAVIP association., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.vpc.v20170312 import models, vpc_client
    return models, vpc_client
def describe_request(models, havip_id):
    request = models.DescribeHaVipsRequest(); request.HaVipIds = [havip_id]; return request
def _item(models, p):
    item = models.HaVipAssociation(); item.HaVipId, item.InstanceId, item.InstanceType = p["havip_id"], p["instance_id"], p["instance_type"]; return item
def associate_request(models, p):
    request = models.AssociateHaVipInstanceRequest(); request.HaVipAssociationSet = [_item(models, p)]; return request
def disassociate_request(models, p):
    request = models.DisassociateHaVipInstanceRequest(); request.HaVipAssociationSet = [_item(models, p)]; return request
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeHaVips, describe_request(models, p["havip_id"])); values = list(response.HaVipSet or [])
    if not values: module.fail_json(msg="HAVIP was not found", havip_id=p["havip_id"])
    for item in values[0].HaVipAssociationSet or []:
        value = item._serialize(allow_none=True)
        if value.get("InstanceId") == p["instance_id"] and value.get("InstanceType") == p["instance_type"]: return value
    return None


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "havip_id": {"required": True}, "instance_id": {"required": True}, "instance_type": {"choices": ["CVM", "ENI"], "required": True}}, supports_check_mode=True)
    p = module.params; target = {"HaVipId": p["havip_id"], "InstanceId": p["instance_id"], "InstanceType": p["instance_type"]}
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.VpcClient, "vpc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, association=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DisassociateHaVipInstance, disassociate_request(models, p))
            module.exit_json(changed=True, **(diff or {}), association=current if module.check_mode else None)
        if current: module.exit_json(changed=False, association=current)
        diff = maybe_diff(module, None, target)
        if not module.check_mode: module.sdk_call(client.AssociateHaVipInstance, associate_request(models, p)); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), association=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
