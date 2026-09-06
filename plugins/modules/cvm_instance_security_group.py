#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cvm_instance_security_group
short_description: Manage the security groups bound to a Tencent Cloud CVM instance
version_added: "0.14.0"
description:
  - Manage the set of security groups bound to a CVM instance through the
    C(cvm.v20170312) API, reconciling the instance's security-group set with
    C(AssociateSecurityGroups) and C(DisassociateSecurityGroups).
  - This module is idempotent. Running it twice leaves the binding unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) (default) reconciles the instance so its security-group
        set is exactly O(security_group_ids). Groups that are missing are
        bound and groups outside the desired list are unbound.
      - C(absent) unbinds the given O(security_group_ids) from the instance,
        leaving any other bound groups in place.
    type: str
    choices: [present, absent]
    default: present
  instance_id:
    description: ID of the CVM instance, e.g. C(ins-xxxxxxxx).
    type: str
    required: true
  security_group_ids:
    description:
      - Security group IDs to manage, e.g. C(sg-xxxxxxxx).
      - With C(state=present) this is the exact desired set; the platform
        limits an instance to at most five security groups.
      - With C(state=absent) these are the groups to unbind.
    type: list
    elements: str
    required: true
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
  - Requires the C(tencentcloud-sdk-python-cvm) package on the controller.
  - C(AssociateSecurityGroups) accepts a single security group per request,
    so binding N groups issues N API calls.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Bind an instance to exactly two security groups
  susunola.tencentcloud.cvm_instance_security_group:
    region: ap-guangzhou
    state: present
    instance_id: ins-xxxxxxxx
    security_group_ids:
      - sg-aaaaaaaa
      - sg-bbbbbbbb

- name: Unbind a security group, keeping the others
  susunola.tencentcloud.cvm_instance_security_group:
    region: ap-guangzhou
    state: absent
    instance_id: ins-xxxxxxxx
    security_group_ids:
      - sg-aaaaaaaa
'''

RETURN = r'''
security_group_ids:
  description: The effective security-group set after the operation.
  returned: always
  type: list
  elements: str
changed:
  description: Whether the security-group set was modified.
  returned: always
  type: bool
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load_cvm():
    from tencentcloud.cvm.v20170312 import models, cvm_client
    return models, cvm_client


def find_instance(module, client, models, instance_id):
    """Return {InstanceId, SecurityGroupIds} for the instance, or None."""
    request = models.DescribeInstancesRequest()
    request.InstanceIds = [instance_id]
    response = module.sdk_call(client.DescribeInstances, request)
    values = list(response.InstanceSet or [])
    if not values:
        return None
    value = values[0]._serialize(allow_none=True)
    return {
        "InstanceId": value.get("InstanceId") or instance_id,
        "SecurityGroupIds": sorted(value.get("SecurityGroupIds") or []),
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "instance_id": {"type": "str", "required": True},
            "security_group_ids": {"type": "list", "elements": "str", "required": True},
        },
        supports_check_mode=True,
    )
    module.require_sdk()
    p = module.params
    desired = sorted(set(p["security_group_ids"]))
    if not desired:
        module.fail_json(msg="security_group_ids must not be empty")
    if p["state"] == "present" and len(desired) > 5:
        module.fail_json(
            msg="an instance can be bound to at most five security groups; got {0}".format(len(desired))
        )

    models, cvm_client = _load_cvm()
    client = module.create_client(cvm_client.CvmClient, "cvm.tencentcloudapi.com")
    try:
        current = find_instance(module, client, models, p["instance_id"])
        if current is None:
            module.fail_json(msg="CVM instance was not found", instance_id=p["instance_id"])
        current_ids = set(current["SecurityGroupIds"])

        if p["state"] == "absent":
            to_unbind = sorted(set(desired) & current_ids)
            if not to_unbind:
                module.exit_json(changed=False, security_group_ids=sorted(current_ids), msg="Security groups already absent")
            after = sorted(current_ids - set(desired))
            diff = maybe_diff(module, {"SecurityGroupIds": sorted(current_ids)}, {"SecurityGroupIds": after})
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), security_group_ids=after, msg="Would unbind {0}".format(to_unbind))
            for group in to_unbind:
                request = models.DisassociateSecurityGroupsRequest()
                request.InstanceIds = [p["instance_id"]]
                request.SecurityGroupIds = [group]
                module.sdk_call(client.DisassociateSecurityGroups, request)
            module.exit_json(changed=True, **(diff or {}), security_group_ids=after, msg="Unbound {0}".format(to_unbind))

        to_bind = sorted(set(desired) - current_ids)
        to_unbind = sorted(current_ids - set(desired))
        after = sorted(desired)
        if not to_bind and not to_unbind:
            module.exit_json(changed=False, security_group_ids=sorted(current_ids), msg="Security group set is up to date")
        diff = maybe_diff(module, {"SecurityGroupIds": sorted(current_ids)}, {"SecurityGroupIds": after})
        if module.check_mode:
            actions = []
            if to_bind:
                actions.append("bind {0}".format(to_bind))
            if to_unbind:
                actions.append("unbind {0}".format(to_unbind))
            module.exit_json(changed=True, **(diff or {}), security_group_ids=after, msg="Would {0}".format(", ".join(actions)))
        for group in to_bind:
            request = models.AssociateSecurityGroupsRequest()
            request.InstanceIds = [p["instance_id"]]
            request.SecurityGroupIds = [group]
            module.sdk_call(client.AssociateSecurityGroups, request)
        for group in to_unbind:
            request = models.DisassociateSecurityGroupsRequest()
            request.InstanceIds = [p["instance_id"]]
            request.SecurityGroupIds = [group]
            module.sdk_call(client.DisassociateSecurityGroups, request)
        module.exit_json(changed=True, **(diff or {}), security_group_ids=after, msg="Security group set updated")
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
