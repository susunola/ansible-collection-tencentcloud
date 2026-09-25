#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tcr_internal_endpoint
short_description: Manage a TCR instance's private VPC endpoint
version_added: "1.5.0"
description:
  - Creates or removes a private VPC access link for a Tencent Cloud TCR instance.
  - Reads DescribeInternalEndpoints before and after changes. A different subnet
    already connected to the same VPC is treated as a conflict, not replaced.
  - Convergence here means the VPC/subnet link is listed, not that DNS or image
    pulling is ready. Manage private DNS separately when required.
options:
  state:
    description: Desired link presence.
    type: str
    choices: [present, absent]
    default: present
  registry_id:
    description: TCR instance ID.
    type: str
    required: true
  vpc_id:
    description: VPC whose private access to the registry is managed.
    type: str
    required: true
  subnet_id:
    description: Subnet ID used for the private access link.
    type: str
    required: true
  endpoint_region_name:
    description: Optional requested region name for a replication instance.
    type: str
  endpoint_region_id:
    description: Optional requested region ID for a replication instance.
    type: int
  waiter_timeout:
    description: Seconds to wait for link presence or absence after a write.
    type: int
    default: 300
  waiter_delay:
    description: Seconds between state reads while waiting.
    type: int
    default: 5
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
  idempotent:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
seealso:
  - module: susunola.tencentcloud.tcr_internal_endpoint_info
    description: Gather TCR internal endpoint information.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Connect a TCR instance to the cluster VPC
  susunola.tencentcloud.tcr_internal_endpoint:
    region: ap-guangzhou
    registry_id: tcr-xxxxxxxx
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx

- name: Remove the private access link
  susunola.tencentcloud.tcr_internal_endpoint:
    region: ap-guangzhou
    registry_id: tcr-xxxxxxxx
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    state: absent
'''

RETURN = r'''
endpoint:
  description: Observed private VPC access link, or null when absent.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    VpcId: vpc-abc
    SubnetId: subnet-abc
    Status: Creating
    AccessIp: 10.0.0.2
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def _load_tcr():
    from tencentcloud.tcr.v20190924 import models, tcr_client
    return models, tcr_client


def describe_links(module, client, models, registry_id):
    request = models.DescribeInternalEndpointsRequest()
    request.RegistryId = registry_id
    response = module.sdk_call(client.DescribeInternalEndpoints, request)
    total = getattr(response, "TotalCount", None)
    if total is None:
        raise ValueError("DescribeInternalEndpoints did not return TotalCount")
    links = list(getattr(response, "AccessVpcSet", None) or [])
    if total != len(links):
        raise ValueError("DescribeInternalEndpoints returned an incomplete link list")
    return [item._serialize(allow_none=True) for item in links]


def find_link(links, vpc_id, subnet_id):
    for link in links:
        if link.get("VpcId") == vpc_id and link.get("SubnetId") == subnet_id:
            return link
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "registry_id": {"type": "str", "required": True},
            "vpc_id": {"type": "str", "required": True},
            "subnet_id": {"type": "str", "required": True},
            "endpoint_region_name": {"type": "str"},
            "endpoint_region_id": {"type": "int"},
            "waiter_timeout": {"type": "int", "default": 300},
            "waiter_delay": {"type": "int", "default": 5},
        },
        supports_check_mode=True,
    )
    p = module.params
    if p["waiter_timeout"] < 0 or p["waiter_delay"] < 0:
        module.fail_json(msg="waiter_timeout and waiter_delay must be non-negative")
    module.require_sdk()
    models, client_module = _load_tcr()
    client = module.create_client(client_module.TcrClient, "tcr.tencentcloudapi.com")
    try:
        links = describe_links(module, client, models, p["registry_id"])
        current = find_link(links, p["vpc_id"], p["subnet_id"])
        desired_present = p["state"] == "present"
        if desired_present and not current:
            conflicts = [item for item in links if item.get("VpcId") == p["vpc_id"]]
            if conflicts:
                module.fail_json(msg="TCR VPC is already connected through another subnet; replace it explicitly",
                                 vpc_id=p["vpc_id"], endpoints=conflicts)
        if bool(current) == desired_present:
            module.exit_json(changed=False, endpoint=current)
        if module.check_mode:
            module.exit_json(changed=True, endpoint=current)
        request = models.ManageInternalEndpointRequest()
        request.RegistryId = p["registry_id"]
        request.Operation = "Create" if desired_present else "Delete"
        request.VpcId = p["vpc_id"]
        request.SubnetId = p["subnet_id"]
        if p["endpoint_region_name"] is not None:
            request.RegionName = p["endpoint_region_name"]
        if p["endpoint_region_id"] is not None:
            request.RegionId = p["endpoint_region_id"]
        module.sdk_call(client.ManageInternalEndpoint, request)
        deadline = time.monotonic() + p["waiter_timeout"]
        while True:
            final = find_link(describe_links(module, client, models, p["registry_id"]), p["vpc_id"], p["subnet_id"])
            if bool(final) == desired_present:
                module.exit_json(changed=True, endpoint=final)
            if time.monotonic() >= deadline:
                module.fail_json(msg="TCR private endpoint did not reach the requested presence state",
                                 registry_id=p["registry_id"], vpc_id=p["vpc_id"], subnet_id=p["subnet_id"])
            time.sleep(p["waiter_delay"])
    except Exception as exc:
        module.fail_sdk_error(exc, "Tencent Cloud TCR private endpoint request failed")


def main():
    run_module()


if __name__ == "__main__":
    main()
