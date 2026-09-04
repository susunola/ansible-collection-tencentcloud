#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: api_gateway_service
short_description: Manage Tencent Cloud API Gateway services
version_added: "0.14.0"
description: Creates, updates and deletes API Gateway service containers.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  service_id: {description: Existing service ID., type: str}
  name: {description: Service name., type: str}
  description: {description: Service description., type: str, default: ''}
  protocol: {description: Service protocol., type: str, choices: [http, https, http&https], default: http&https}
  network_types: {description: Exact enabled network types., type: list, elements: str, choices: [INNER, OUTER], default: [OUTER]}
  ip_version: {description: Service address family applied at creation., type: str, choices: [IPv4, IPv6], default: IPv4}
  vpc_id: {description: VPC ID for private API Gateway services., type: str}
  instance_id: {description: Dedicated API Gateway instance ID., type: str}
  tags: {description: Tags applied at creation., type: dict, default: {}}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.api_gateway_service:
    name: order-api
    protocol: http&https
    network_types: [OUTER]
    description: Order service APIs
'''
RETURN = r'''
service: {description: API Gateway service metadata., type: dict, returned: always}
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found


def _load_api_gateway():
    from tencentcloud.apigateway.v20180808 import apigateway_client, models

    return models, apigateway_client


def build_list_request(models, name=None, offset=0):
    request = models.DescribeServicesStatusRequest()
    request.Offset, request.Limit = offset, 100
    if name:
        item = models.Filter()
        item.Name, item.Values = "ServiceName", [name]
        request.Filters = [item]
    return request


def build_get_request(models, service_id):
    request = models.DescribeServiceRequest()
    request.ServiceId = service_id
    return request


def build_create_request(models, params):
    request = models.CreateServiceRequest()
    request.ServiceName, request.ServiceDesc = params["name"], params["description"]
    request.Protocol, request.NetTypes = params["protocol"], params["network_types"]
    request.IpVersion = params["ip_version"]
    if params.get("vpc_id"):
        request.UniqVpcId = params["vpc_id"]
    if params.get("instance_id"):
        request.InstanceId = params["instance_id"]
    if params.get("tags"):
        request.Tags = []
        for key, value in sorted(params["tags"].items()):
            tag = models.Tag()
            tag.Key, tag.Value = str(key), str(value)
            request.Tags.append(tag)
    return request


def build_update_request(models, service_id, params):
    request = models.ModifyServiceRequest()
    request.ServiceId, request.ServiceName = service_id, params["name"]
    request.ServiceDesc, request.Protocol = params["description"], params["protocol"]
    request.NetTypes = params["network_types"]
    if params.get("vpc_id"):
        request.UniqVpcId = params["vpc_id"]
    return request


def build_delete_request(models, service_id):
    request = models.DeleteServiceRequest()
    request.ServiceId = service_id
    return request


def find_service(module, client, models, service_id, name):
    if service_id:
        try:
            response = module.sdk_call(client.DescribeService, build_get_request(models, service_id))
        except Exception as exc:
            if is_not_found(exc):
                return None
            raise
        result = getattr(response, "Result", None)
        return result._serialize(allow_none=True) if result else None
    offset, matches = 0, []
    while name:
        response = module.sdk_call(client.DescribeServicesStatus, build_list_request(models, name, offset))
        result = getattr(response, "Result", None)
        items = list(getattr(result, "ServiceSet", None) or [])
        matches.extend(item._serialize(allow_none=True) for item in items if getattr(item, "ServiceName", None) == name)
        offset += len(items)
        if not items or offset >= int(getattr(result, "TotalCount", 0) or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple API Gateway services have the requested name", name=name)
    return matches[0] if matches else None


def _desired(params):
    return {"ServiceName": params["name"], "ServiceDesc": params["description"], "Protocol": params["protocol"], "NetTypes": sorted(params["network_types"])}


def _matches(current, desired):
    return all((sorted(current.get(k) or []) if k == "NetTypes" else current.get(k)) == v for k, v in desired.items())


def wait_for_service(module, client, models, service_id, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        try:
            current = find_service(module, client, models, service_id, None)
        except Exception as exc:
            if absent and is_not_found(exc):
                return None
            raise
        if absent and current is None:
            return None
        if not absent and current and _matches(current, desired):
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for API Gateway service convergence", service=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "service_id": {"type": "str"},
            "name": {"type": "str"},
            "description": {"type": "str", "default": ""},
            "protocol": {"type": "str", "choices": ["http", "https", "http&https"], "default": "http&https"},
            "network_types": {"type": "list", "elements": "str", "choices": ["INNER", "OUTER"], "default": ["OUTER"]},
            "ip_version": {"type": "str", "choices": ["IPv4", "IPv6"], "default": "IPv4"},
            "vpc_id": {"type": "str"},
            "instance_id": {"type": "str"},
            "tags": {"type": "dict", "default": {}},
        },
        required_one_of=[("service_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, client_module = _load_api_gateway()
    client = module.create_client(client_module.ApigatewayClient, "apigateway.tencentcloudapi.com")
    try:
        current = find_service(module, client, models, p["service_id"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, service=None, msg="API Gateway service is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), service=current, msg="Would delete API Gateway service")
            module.sdk_call(client.DeleteService, build_delete_request(models, current["ServiceId"]))
            wait_for_service(module, client, models, current["ServiceId"], absent=True)
            module.exit_json(changed=True, **(diff or {}), service=None, msg="API Gateway service deleted")
        desired = _desired(p)
        if current is None:
            if not p["name"]:
                module.fail_json(msg="name is required when creating an API Gateway service")
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), service=None, msg="Would create API Gateway service")
            response = module.sdk_call(client.CreateService, build_create_request(models, p))
            current = wait_for_service(module, client, models, response.ServiceId, desired)
            module.exit_json(changed=True, **(diff or {}), service=current, msg="API Gateway service created")
        if _matches(current, desired):
            module.exit_json(changed=False, service=current, msg="API Gateway service is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), service=current, msg="Would update API Gateway service")
        module.sdk_call(client.ModifyService, build_update_request(models, current["ServiceId"], p))
        current = wait_for_service(module, client, models, current["ServiceId"], desired)
        module.exit_json(changed=True, **(diff or {}), service=current, msg="API Gateway service updated")
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )


def main():
    run_module()


if __name__ == "__main__":
    main()
