#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: ccn
short_description: Manage Tencent Cloud Cloud Connect Networks
version_added: "0.14.0"
description:
  - Creates, updates and deletes CCN backbone network instances.
  - Reconciles mutable name, description and routing feature flags.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  ccn_id: {description: Existing CCN ID., type: str}
  name: {description: CCN name., type: str}
  description: {description: CCN description., type: str, default: ''}
  qos_level: {description: QoS level applied at creation., type: str, default: AU}
  instance_charge_type: {description: CCN billing mode applied at creation., type: str, choices: [PREPAID, POSTPAID], default: POSTPAID}
  bandwidth_limit_type: {description: Bandwidth limit direction., type: str, choices: [OUTER_REGION_LIMIT, INTER_REGION_LIMIT]}
  route_ecmp: {description: Enable equal-cost multi-path routing., type: bool}
  route_overlap: {description: Enable overlapping route publication., type: bool}
  traffic_marking_policy: {description: Enable traffic marking policies., type: bool}
  tags: {description: Tags applied at creation., type: dict, default: {}}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- susunola.tencentcloud.ccn:
    name: global-backbone
    description: Production multi-region network
    route_ecmp: true
    tags: {env: prod}
'''

RETURN = r'''
ccn: {description: CCN metadata., type: dict, returned: always}
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_vpc():
    from tencentcloud.vpc.v20170312 import models, vpc_client
    return models, vpc_client


def build_describe_request(models, ccn_id=None, name=None, offset=0):
    request = models.DescribeCcnsRequest()
    request.Offset, request.Limit = offset, 100
    if ccn_id:
        request.CcnIds = [ccn_id]
    elif name:
        item = models.Filter()
        item.Name, item.Values = "ccn-name", [name]
        request.Filters = [item]
    return request


def build_create_request(models, params):
    request = models.CreateCcnRequest()
    request.CcnName, request.CcnDescription = params["name"], params["description"]
    request.QosLevel, request.InstanceChargeType = params["qos_level"], params["instance_charge_type"]
    if params.get("bandwidth_limit_type"):
        request.BandwidthLimitType = params["bandwidth_limit_type"]
    if params.get("tags"):
        request.Tags = []
        for key, value in sorted(params["tags"].items()):
            tag = models.Tag()
            tag.Key, tag.Value = str(key), str(value)
            request.Tags.append(tag)
    return request


def build_update_request(models, ccn_id, params):
    request = models.ModifyCcnAttributeRequest()
    request.CcnId, request.CcnName, request.CcnDescription = ccn_id, params["name"], params["description"]
    for api, key in (("RouteECMPFlag", "route_ecmp"), ("RouteOverlapFlag", "route_overlap"), ("TrafficMarkingPolicyFlag", "traffic_marking_policy")):
        if params.get(key) is not None:
            setattr(request, api, params[key])
    return request


def build_delete_request(models, ccn_id):
    request = models.DeleteCcnRequest()
    request.CcnId = ccn_id
    return request


def find_ccn(module, client, models, ccn_id, name):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeCcns, build_describe_request(models, ccn_id, name, offset))
        items = list(getattr(response, "CcnSet", None) or [])
        matches.extend(item._serialize(allow_none=True) for item in items)
        offset += len(items)
        if ccn_id or not items or offset >= int(getattr(response, "TotalCount", 0) or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple CCNs have the requested name; specify ccn_id")
    return matches[0] if matches else None


def _desired(params):
    result = {"CcnName": params["name"], "CcnDescription": params["description"]}
    for api, key in (("RouteECMPFlag", "route_ecmp"), ("RouteOverlapFlag", "route_overlap"), ("TrafficMarkingPolicyFlag", "traffic_marking_policy")):
        if params.get(key) is not None:
            result[api] = params[key]
    return result


def wait_for_ccn(module, client, models, ccn_id, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_ccn(module, client, models, ccn_id, None)
        if absent and current is None:
            return None
        if not absent and current and all(current.get(k) == v for k, v in desired.items()):
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for CCN convergence", ccn=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={
        "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
        "ccn_id": {"type": "str"}, "name": {"type": "str"}, "description": {"type": "str", "default": ""},
        "qos_level": {"type": "str", "default": "AU"}, "instance_charge_type": {"type": "str", "choices": ["PREPAID", "POSTPAID"], "default": "POSTPAID"},
        "bandwidth_limit_type": {"type": "str", "choices": ["OUTER_REGION_LIMIT", "INTER_REGION_LIMIT"]},
        "route_ecmp": {"type": "bool"}, "route_overlap": {"type": "bool"}, "traffic_marking_policy": {"type": "bool"},
        "tags": {"type": "dict", "default": {}},
    }, required_one_of=[("ccn_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, client_module = _load_vpc()
    client = module.create_client(client_module.VpcClient, "vpc.tencentcloudapi.com")
    try:
        current = find_ccn(module, client, models, p["ccn_id"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, ccn=None, msg="CCN is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), ccn=current, msg="Would delete CCN")
            module.sdk_call(client.DeleteCcn, build_delete_request(models, current["CcnId"]))
            wait_for_ccn(module, client, models, current["CcnId"], absent=True)
            module.exit_json(changed=True, **(diff or {}), ccn=None, msg="CCN deleted")
        desired = _desired(p)
        if current is None:
            if not p["name"]:
                module.fail_json(msg="name is required when creating a CCN")
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), ccn=None, msg="Would create CCN")
            response = module.sdk_call(client.CreateCcn, build_create_request(models, p))
            current = wait_for_ccn(module, client, models, response.Ccn.CcnId, desired)
            module.exit_json(changed=True, **(diff or {}), ccn=current, msg="CCN created")
        if all(current.get(k) == v for k, v in desired.items()):
            module.exit_json(changed=False, ccn=current, msg="CCN is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), ccn=current, msg="Would update CCN")
        module.sdk_call(client.ModifyCcnAttribute, build_update_request(models, current["CcnId"], p))
        current = wait_for_ccn(module, client, models, current["CcnId"], desired)
        module.exit_json(changed=True, **(diff or {}), ccn=current, msg="CCN updated")
    except Exception as exc:
        module.fail_json(msg="Tencent Cloud API request failed", error=str(exc), error_code=getattr(exc, "get_code", lambda: None)(), request_id=getattr(exc, "get_request_id", lambda: None)())


def main():
    run_module()


if __name__ == "__main__":
    main()
