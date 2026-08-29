#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: privatelink_endpoint_service
short_description: Manage Tencent Cloud PrivateLink endpoint services
version_added: "0.14.0"
description: Publishes and manages private endpoint services backed by a cloud service instance such as CLB.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  endpoint_service_id: {description: Existing endpoint service ID., type: str}
  name: {description: Endpoint service name., type: str}
  vpc_id: {description: Service VPC ID., type: str}
  service_instance_id: {description: Backing service instance ID such as a CLB ID., type: str}
  service_type: {description: Backing service type., type: str, default: CLB}
  auto_accept: {description: Automatically accept endpoint connections., type: bool, default: true}
  ip_address_type: {description: Service address family., type: str, choices: [IPv4, IPv6], default: IPv4}
  tags: {description: Tags applied at creation., type: dict, default: {}}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.privatelink_endpoint_service:
    name: internal-api
    vpc_id: vpc-xxxxxxxx
    service_instance_id: lb-xxxxxxxx
    auto_accept: true
'''
RETURN = r'''
endpoint_service: {description: PrivateLink endpoint service metadata., type: dict, returned: always}
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_vpc():
    from tencentcloud.vpc.v20170312 import models, vpc_client
    return models, vpc_client


def build_describe_request(models, service_id=None, name=None, offset=0):
    request = models.DescribeVpcEndPointServiceRequest()
    request.Offset, request.Limit = offset, 100
    if service_id:
        request.EndPointServiceIds = [service_id]
    elif name:
        item = models.Filter()
        item.Name, item.Values = "end-point-service-name", [name]
        request.Filters = [item]
    return request


def build_create_request(models, params):
    request = models.CreateVpcEndPointServiceRequest()
    request.VpcId, request.EndPointServiceName = params["vpc_id"], params["name"]
    request.ServiceInstanceId, request.ServiceType = params["service_instance_id"], params["service_type"]
    request.AutoAcceptFlag, request.IpAddressType = params["auto_accept"], params["ip_address_type"]
    if params.get("tags"):
        request.Tags = []
        for key, value in sorted(params["tags"].items()):
            tag = models.Tag()
            tag.Key, tag.Value = str(key), str(value)
            request.Tags.append(tag)
    return request


def build_update_request(models, service_id, params):
    request = models.ModifyVpcEndPointServiceAttributeRequest()
    request.EndPointServiceId, request.VpcId = service_id, params["vpc_id"]
    request.EndPointServiceName, request.ServiceInstanceId = params["name"], params["service_instance_id"]
    request.AutoAcceptFlag, request.IpAddressType = params["auto_accept"], params["ip_address_type"]
    return request


def build_delete_request(models, service_id, ip_address_type):
    request = models.DeleteVpcEndPointServiceRequest()
    request.EndPointServiceId, request.IpAddressType = service_id, ip_address_type
    return request


def find_service(module, client, models, service_id, name):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeVpcEndPointService, build_describe_request(models, service_id, name, offset))
        items = list(getattr(response, "EndPointServiceSet", None) or [])
        matches.extend(item._serialize(allow_none=True) for item in items)
        offset += len(items)
        if service_id or not items or offset >= int(getattr(response, "TotalCount", 0) or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple endpoint services have the requested name", name=name)
    return matches[0] if matches else None


def _desired(params):
    return {"ServiceName": params["name"], "VpcId": params["vpc_id"], "ServiceInstanceId": params["service_instance_id"], "AutoAcceptFlag": params["auto_accept"]}


def wait_for_service(module, client, models, service_id, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_service(module, client, models, service_id, None)
        if absent and current is None:
            return None
        if not absent and current and all(current.get(k) == v for k, v in desired.items()):
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for endpoint service convergence", endpoint_service=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"type": "str", "choices": ["present", "absent"], "default": "present"}, "endpoint_service_id": {"type": "str"}, "name": {"type": "str"}, "vpc_id": {"type": "str"}, "service_instance_id": {"type": "str"}, "service_type": {"type": "str", "default": "CLB"}, "auto_accept": {"type": "bool", "default": True}, "ip_address_type": {"type": "str", "choices": ["IPv4", "IPv6"], "default": "IPv4"}, "tags": {"type": "dict", "default": {}}}, required_one_of=[("endpoint_service_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, client_module = _load_vpc()
    client = module.create_client(client_module.VpcClient, "vpc.tencentcloudapi.com")
    try:
        current = find_service(module, client, models, p["endpoint_service_id"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, endpoint_service=None, msg="Endpoint service is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), endpoint_service=current, msg="Would delete endpoint service")
            module.sdk_call(client.DeleteVpcEndPointService, build_delete_request(models, current["EndPointServiceId"], p["ip_address_type"]))
            wait_for_service(module, client, models, current["EndPointServiceId"], absent=True)
            module.exit_json(changed=True, **(diff or {}), endpoint_service=None, msg="Endpoint service deleted")
        if current is None:
            missing = [key for key in ("name", "vpc_id", "service_instance_id") if not p[key]]
            if missing:
                module.fail_json(msg="Required when creating: %s" % ", ".join(missing))
            desired = _desired(p)
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), endpoint_service=None, msg="Would create endpoint service")
            response = module.sdk_call(client.CreateVpcEndPointService, build_create_request(models, p))
            current = wait_for_service(module, client, models, response.EndPointService.EndPointServiceId, desired)
            module.exit_json(changed=True, **(diff or {}), endpoint_service=current, msg="Endpoint service created")
        desired = _desired(p)
        if all(current.get(k) == v for k, v in desired.items()):
            module.exit_json(changed=False, endpoint_service=current, msg="Endpoint service is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), endpoint_service=current, msg="Would update endpoint service")
        module.sdk_call(client.ModifyVpcEndPointServiceAttribute, build_update_request(models, current["EndPointServiceId"], p))
        current = wait_for_service(module, client, models, current["EndPointServiceId"], desired)
        module.exit_json(changed=True, **(diff or {}), endpoint_service=current, msg="Endpoint service updated")
    except Exception as exc:
        module.fail_json(msg="Tencent Cloud API request failed", error=str(exc), error_code=getattr(exc, "get_code", lambda: None)(), request_id=getattr(exc, "get_request_id", lambda: None)())


def main():
    run_module()


if __name__ == "__main__":
    main()
