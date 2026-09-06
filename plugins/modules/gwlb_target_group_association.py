#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: gwlb_target_group_association
short_description: Manage Tencent Cloud GWLB target group associations
version_added: "0.14.0"
description: Associates or disassociates a Gateway Load Balancer and target group.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  load_balancer_id: {type: str, required: true, description: GWLB ID.}
  target_group_id: {type: str, required: true, description: Target group ID.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.gwlb_target_group_association:
    load_balancer_id: gwlb-xxxxxxxx
    target_group_id: lbtg-xxxxxxxx
"""
RETURN = r"""association: {description: Effective GWLB association., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.gwlb.v20240906 import models, gwlb_client

    return models, gwlb_client


def describe_request(models, load_balancer_id):
    r = models.DescribeGatewayLoadBalancersRequest()
    r.LoadBalancerIds, r.Offset, r.Limit = [load_balancer_id], 0, 20
    return r


def association_request(models, p):
    r = models.AssociateTargetGroupsRequest()
    x = models.TargetGroupAssociation()
    x.LoadBalancerId, x.TargetGroupId = p["load_balancer_id"], p["target_group_id"]
    r.Associations = [x]
    return r


def disassociation_request(models, p):
    r = models.DisassociateTargetGroupsRequest()
    x = models.TargetGroupAssociation()
    x.LoadBalancerId, x.TargetGroupId = p["load_balancer_id"], p["target_group_id"]
    r.Associations = [x]
    return r


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeGatewayLoadBalancers, describe_request(models, p["load_balancer_id"]))
    item = next(iter(response.LoadBalancerSet or []), None)
    if not item:
        module.fail_json(msg="GWLB does not exist", load_balancer_id=p["load_balancer_id"])
    return item.TargetGroupId == p["target_group_id"]


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "load_balancer_id": {"required": True},
            "target_group_id": {"required": True},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.GwlbClient, "gwlb.tencentcloudapi.com")
    try:
        current, wanted = find(module, client, models, p), p["state"] == "present"
        value = {"LoadBalancerId": p["load_balancer_id"], "TargetGroupId": p["target_group_id"]}
        if current == wanted:
            module.exit_json(changed=False, association=value if wanted else None)
        diff = maybe_diff(module, value if current else None, value if wanted else None)
        if not module.check_mode:
            module.sdk_call(
                client.AssociateTargetGroups if wanted else client.DisassociateTargetGroups,
                association_request(models, p) if wanted else disassociation_request(models, p),
            )
        module.exit_json(changed=True, **(diff or {}), association=value if wanted else None)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
