#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: ccn_attachment
short_description: Attach network instances to Tencent Cloud CCN
version_added: "0.14.0"
description:
  - Idempotently attaches or detaches one VPC, VPN gateway, direct-connect gateway or BM VPC from a CCN.
options:
  state: {description: Desired attachment state., type: str, choices: [present, absent], default: present}
  ccn_id: {description: CCN ID., type: str, required: true}
  instance_id: {description: Network instance ID., type: str, required: true}
  instance_region: {description: Region containing the network instance., type: str, required: true}
  instance_type: {description: Network instance type., type: str, choices: [VPC, VPNGW, DIRECTCONNECT, BMVPC], required: true}
  description: {description: Attachment description., type: str, default: ''}
  route_table_id: {description: CCN route table ID used by the attachment., type: str}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- susunola.tencentcloud.ccn_attachment:
    ccn_id: ccn-xxxxxxxx
    instance_id: vpc-xxxxxxxx
    instance_region: ap-guangzhou
    instance_type: VPC
    description: Production VPC
'''

RETURN = r'''
attachment: {description: CCN attachment metadata., type: dict, returned: always}
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_vpc():
    from tencentcloud.vpc.v20170312 import models, vpc_client
    return models, vpc_client


def build_instance(models, params):
    instance = models.CcnInstance()
    instance.InstanceId, instance.InstanceRegion = params["instance_id"], params["instance_region"]
    instance.InstanceType, instance.Description = params["instance_type"], params["description"]
    if params.get("route_table_id"):
        instance.RouteTableId = params["route_table_id"]
    return instance


def build_describe_request(models, ccn_id, offset=0):
    request = models.DescribeCcnAttachedInstancesRequest()
    request.CcnId, request.Offset, request.Limit = ccn_id, offset, 100
    return request


def build_mutation_request(models, params, operation):
    request = operation()
    request.CcnId, request.Instances = params["ccn_id"], [build_instance(models, params)]
    return request


def find_attachment(module, client, models, params):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeCcnAttachedInstances, build_describe_request(models, params["ccn_id"], offset))
        items = list(getattr(response, "InstanceSet", None) or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if value.get("InstanceId") == params["instance_id"] and value.get("InstanceRegion") == params["instance_region"] and value.get("InstanceType") == params["instance_type"]:
                return value
        offset += len(items)
        if not items or offset >= int(getattr(response, "TotalCount", 0) or 0):
            return None


def wait_for_attachment(module, client, models, params, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_attachment(module, client, models, params)
        if absent and current is None:
            return None
        if not absent and current and (current.get("Description") or "") == params["description"]:
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for CCN attachment convergence", attachment=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={
        "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
        "ccn_id": {"type": "str", "required": True}, "instance_id": {"type": "str", "required": True},
        "instance_region": {"type": "str", "required": True},
        "instance_type": {"type": "str", "choices": ["VPC", "VPNGW", "DIRECTCONNECT", "BMVPC"], "required": True},
        "description": {"type": "str", "default": ""}, "route_table_id": {"type": "str"},
    }, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, client_module = _load_vpc()
    client = module.create_client(client_module.VpcClient, "vpc.tencentcloudapi.com")
    try:
        current = find_attachment(module, client, models, p)
        desired = {"CcnId": p["ccn_id"], "InstanceId": p["instance_id"], "InstanceRegion": p["instance_region"], "InstanceType": p["instance_type"], "Description": p["description"]}
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, attachment=None, msg="CCN attachment is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), attachment=current, msg="Would detach network instance")
            request = build_mutation_request(models, p, models.DetachCcnInstancesRequest)
            module.sdk_call(client.DetachCcnInstances, request)
            wait_for_attachment(module, client, models, p, absent=True)
            module.exit_json(changed=True, **(diff or {}), attachment=None, msg="Network instance detached")
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), attachment=None, msg="Would attach network instance")
            request = build_mutation_request(models, p, models.AttachCcnInstancesRequest)
            module.sdk_call(client.AttachCcnInstances, request)
            current = wait_for_attachment(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), attachment=current, msg="Network instance attached")
        if (current.get("Description") or "") == p["description"]:
            module.exit_json(changed=False, attachment=current, msg="CCN attachment is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), attachment=current, msg="Would update CCN attachment")
        request = build_mutation_request(models, p, models.ModifyCcnAttachedInstancesAttributeRequest)
        module.sdk_call(client.ModifyCcnAttachedInstancesAttribute, request)
        current = wait_for_attachment(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), attachment=current, msg="CCN attachment updated")
    except Exception as exc:
        module.fail_json(msg="Tencent Cloud API request failed", error=str(exc), error_code=getattr(exc, "get_code", lambda: None)(), request_id=getattr(exc, "get_request_id", lambda: None)())


def main():
    run_module()


if __name__ == "__main__":
    main()
