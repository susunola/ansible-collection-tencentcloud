#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: clb_snat_ip
short_description: Manage SNAT IPs on a Tencent Cloud CLB instance
version_added: "1.1.0"
description:
  - Add or remove SNAT IP addresses on a Tencent Cloud CLB (Load Balancer).
  - SNAT IPs let backend services in a VPC reach the public network through the
    CLB. The module is idempotent on the set of requested IPs, it only creates
    the IPs that are missing and only deletes the IPs that were requested for
    removal, so other SNAT IPs on the same CLB are left untouched.
options:
  load_balancer_id:
    description: ID of the CLB instance to manage SNAT IPs for.
    type: str
    required: true
  snat_ips:
    description:
      - List of SNAT IP addresses to ensure are present (state=present) or absent
        (state=absent) on the CLB.
    type: list
    elements: str
    required: true
  state:
    description: Desired state of the SNAT IPs.
    type: str
    choices: [present, absent]
    default: present
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Ensure SNAT IPs are present on a CLB
  susunola.tencentcloud.clb_snat_ip:
    load_balancer_id: lb-xxxxxxxx
    snat_ips:
      - 10.0.0.10
      - 10.0.0.11

- name: Remove specific SNAT IPs from a CLB
  susunola.tencentcloud.clb_snat_ip:
    load_balancer_id: lb-xxxxxxxx
    snat_ips:
      - 10.0.0.10
    state: absent
'''

RETURN = r'''
load_balancer_id:
  description: CLB instance the operation targeted.
  returned: always
  type: str
snat_ips:
  description: SNAT IPs currently attached to the CLB after the operation.
  returned: always
  type: list
changed:
  description: Whether any SNAT IPs were added or removed.
  returned: always
  type: bool
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def _load_clb():
    from tencentcloud.clb.v20180317 import models, clb_client
    return models, clb_client


def _current_snat_ips(module, client, models, load_balancer_id):
    request = models.DescribeLoadBalancersRequest()
    request.LoadBalancerIds = [load_balancer_id]
    response = module.sdk_call(client.DescribeLoadBalancers, request)
    lbs = list(getattr(response, "LoadBalancerSet", None) or [])
    if not lbs:
        module.fail_json(msg="CLB %s not found" % load_balancer_id)
    raw = list(getattr(lbs[0], "SnatIps", None) or [])
    result = []
    for item in raw:
        # SnatIps is a list of strings in the SDK response.
        if isinstance(item, str):
            result.append(item)
        else:
            result.append(getattr(item, "SnatIp", str(item)))
    return result


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "load_balancer_id": {"type": "str", "required": True},
            "snat_ips": {"type": "list", "elements": "str", "required": True},
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
        },
        supports_check_mode=True,
    )
    p = module.params
    lb_id = p["load_balancer_id"]
    desired = list(p["snat_ips"])
    desired_present = p["state"] == "present"
    module.require_sdk()
    models, clb_client = _load_clb()
    client = module.create_client(clb_client.ClbClient, "clb.tencentcloudapi.com")
    try:
        current = _current_snat_ips(module, client, models, lb_id)
        current_set = set(current)
        if desired_present:
            missing = [ip for ip in desired if ip not in current_set]
            if not missing:
                module.exit_json(
                    changed=False,
                    load_balancer_id=lb_id,
                    snat_ips=current,
                    msg="All requested SNAT IPs already present on %s" % lb_id,
                )
            if module.check_mode:
                module.exit_json(
                    changed=True,
                    load_balancer_id=lb_id,
                    snat_ips=current + missing,
                    msg="Would add SNAT IPs %s to %s" % (missing, lb_id),
                )
            request = models.CreateLoadBalancerSnatIpsRequest()
            request.LoadBalancerId = lb_id
            request.SnatIps = missing
            request.Number = len(missing)
            module.sdk_call(client.CreateLoadBalancerSnatIps, request)
            final = _current_snat_ips(module, client, models, lb_id)
            module.exit_json(
                changed=True,
                load_balancer_id=lb_id,
                snat_ips=final,
                msg="Added SNAT IPs %s to %s" % (missing, lb_id),
            )
        else:
            to_remove = [ip for ip in desired if ip in current_set]
            if not to_remove:
                module.exit_json(
                    changed=False,
                    load_balancer_id=lb_id,
                    snat_ips=current,
                    msg="None of the requested SNAT IPs are present on %s" % lb_id,
                )
            if module.check_mode:
                remaining = [ip for ip in current if ip not in set(to_remove)]
                module.exit_json(
                    changed=True,
                    load_balancer_id=lb_id,
                    snat_ips=remaining,
                    msg="Would remove SNAT IPs %s from %s" % (to_remove, lb_id),
                )
            request = models.DeleteLoadBalancerSnatIpsRequest()
            request.LoadBalancerId = lb_id
            request.Ips = to_remove
            module.sdk_call(client.DeleteLoadBalancerSnatIps, request)
            final = _current_snat_ips(module, client, models, lb_id)
            module.exit_json(
                changed=True,
                load_balancer_id=lb_id,
                snat_ips=final,
                msg="Removed SNAT IPs %s from %s" % (to_remove, lb_id),
            )
    except Exception as exc:
        module.fail_sdk_error(exc, "Tencent Cloud CLB SNAT IP request failed")


def main():
    run_module()


if __name__ == "__main__":
    main()
