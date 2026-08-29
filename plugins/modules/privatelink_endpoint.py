#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: privatelink_endpoint
short_description: Manage Tencent Cloud PrivateLink endpoints
version_added: "0.14.0"
description: Creates, updates and deletes consumer-side VPC endpoints connected to a PrivateLink endpoint service.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  endpoint_id: {description: Existing endpoint ID., type: str}
  name: {description: Endpoint name., type: str}
  vpc_id: {description: Consumer VPC ID., type: str}
  subnet_id: {description: Consumer subnet ID., type: str}
  endpoint_service_id: {description: Provider endpoint service ID., type: str}
  endpoint_vip: {description: Requested private endpoint IP., type: str}
  security_group_ids: {description: Exact security group ID set., type: list, elements: str}
  ip_address_type: {description: Endpoint address family., type: str, choices: [IPv4, IPv6], default: IPv4}
  tags: {description: Tags applied at creation., type: dict, default: {}}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.privatelink_endpoint:
    name: internal-api-client
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    endpoint_service_id: vpcsvc-xxxxxxxx
    security_group_ids: [sg-xxxxxxxx]
'''
RETURN = r'''
endpoint: {description: PrivateLink endpoint metadata., type: dict, returned: always}
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_vpc():
    from tencentcloud.vpc.v20170312 import models, vpc_client
    return models, vpc_client


def build_describe_request(models, endpoint_id=None, name=None, vpc_id=None, offset=0):
    request = models.DescribeVpcEndPointRequest()
    request.Offset, request.Limit = offset, 100
    if endpoint_id:
        request.EndPointId = [endpoint_id]
    else:
        filters = []
        for key, value in (("end-point-name", name), ("vpc-id", vpc_id)):
            if value:
                item = models.Filter()
                item.Name, item.Values = key, [value]
                filters.append(item)
        if filters:
            request.Filters = filters
    return request


def build_create_request(models, params):
    request = models.CreateVpcEndPointRequest()
    request.VpcId, request.SubnetId = params["vpc_id"], params["subnet_id"]
    request.EndPointName, request.EndPointServiceId = params["name"], params["endpoint_service_id"]
    if params.get("endpoint_vip"):
        request.EndPointVip = params["endpoint_vip"]
    if params.get("security_group_ids"):
        request.SecurityGroupId = params["security_group_ids"][0]
    request.IpAddressType = params["ip_address_type"]
    if params.get("tags"):
        request.Tags = []
        for key, value in sorted(params["tags"].items()):
            tag = models.Tag()
            tag.Key, tag.Value = str(key), str(value)
            request.Tags.append(tag)
    return request


def build_update_request(models, endpoint_id, params):
    request = models.ModifyVpcEndPointAttributeRequest()
    request.EndPointId, request.EndPointName = endpoint_id, params["name"]
    request.SecurityGroupIds = params.get("security_group_ids") or []
    request.IpAddressType = params["ip_address_type"]
    return request


def build_delete_request(models, endpoint_id, ip_address_type):
    request = models.DeleteVpcEndPointRequest()
    request.EndPointId, request.IpAddressType = endpoint_id, ip_address_type
    return request


def find_endpoint(module, client, models, endpoint_id, name, vpc_id):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeVpcEndPoint, build_describe_request(models, endpoint_id, name, vpc_id, offset))
        items = list(getattr(response, "EndPointSet", None) or [])
        matches.extend(item._serialize(allow_none=True) for item in items)
        offset += len(items)
        if endpoint_id or not items or offset >= int(getattr(response, "TotalCount", 0) or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple endpoints have the requested name", name=name)
    return matches[0] if matches else None


def _groups(values):
    return sorted(x if isinstance(x, str) else x.get("SecurityGroupId") for x in (values or []))


def _desired(params):
    return {"EndPointName": params["name"], "SecurityGroupIds": _groups(params.get("security_group_ids"))}


def _matches(current, desired):
    return current.get("EndPointName") == desired["EndPointName"] and _groups(current.get("GroupSet")) == desired["SecurityGroupIds"]


def wait_for_endpoint(module, client, models, endpoint_id, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_endpoint(module, client, models, endpoint_id, None, None)
        if absent and current is None:
            return None
        if not absent and current and _matches(current, desired):
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for PrivateLink endpoint convergence", endpoint=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"type": "str", "choices": ["present", "absent"], "default": "present"}, "endpoint_id": {"type": "str"}, "name": {"type": "str"}, "vpc_id": {"type": "str"}, "subnet_id": {"type": "str"}, "endpoint_service_id": {"type": "str"}, "endpoint_vip": {"type": "str"}, "security_group_ids": {"type": "list", "elements": "str"}, "ip_address_type": {"type": "str", "choices": ["IPv4", "IPv6"], "default": "IPv4"}, "tags": {"type": "dict", "default": {}}}, required_one_of=[("endpoint_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, client_module = _load_vpc()
    client = module.create_client(client_module.VpcClient, "vpc.tencentcloudapi.com")
    try:
        current = find_endpoint(module, client, models, p["endpoint_id"], p["name"], p["vpc_id"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, endpoint=None, msg="PrivateLink endpoint is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), endpoint=current, msg="Would delete PrivateLink endpoint")
            module.sdk_call(client.DeleteVpcEndPoint, build_delete_request(models, current["EndPointId"], p["ip_address_type"]))
            wait_for_endpoint(module, client, models, current["EndPointId"], absent=True)
            module.exit_json(changed=True, **(diff or {}), endpoint=None, msg="PrivateLink endpoint deleted")
        desired = _desired(p)
        if current is None:
            missing = [key for key in ("name", "vpc_id", "subnet_id", "endpoint_service_id") if not p[key]]
            if missing:
                module.fail_json(msg="Required when creating: %s" % ", ".join(missing))
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), endpoint=None, msg="Would create PrivateLink endpoint")
            response = module.sdk_call(client.CreateVpcEndPoint, build_create_request(models, p))
            current = wait_for_endpoint(module, client, models, response.EndPoint.EndPointId, desired)
            module.exit_json(changed=True, **(diff or {}), endpoint=current, msg="PrivateLink endpoint created")
        if _matches(current, desired):
            module.exit_json(changed=False, endpoint=current, msg="PrivateLink endpoint is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), endpoint=current, msg="Would update PrivateLink endpoint")
        module.sdk_call(client.ModifyVpcEndPointAttribute, build_update_request(models, current["EndPointId"], p))
        current = wait_for_endpoint(module, client, models, current["EndPointId"], desired)
        module.exit_json(changed=True, **(diff or {}), endpoint=current, msg="PrivateLink endpoint updated")
    except Exception as exc:
        module.fail_json(msg="Tencent Cloud API request failed", error=str(exc), error_code=getattr(exc, "get_code", lambda: None)(), request_id=getattr(exc, "get_request_id", lambda: None)())


def main():
    run_module()


if __name__ == "__main__":
    main()
