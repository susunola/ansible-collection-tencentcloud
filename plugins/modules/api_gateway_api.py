#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: api_gateway_api
short_description: Manage Tencent Cloud API Gateway APIs
version_added: "0.14.0"
description: Creates, updates and deletes an HTTP API within an API Gateway service.
options:
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  service_id: {type: str, required: true, description: Parent service ID.}
  api_id: {type: str, description: Existing API ID.}
  name: {type: str, description: API name.}
  path: {type: str, default: /, description: Public request path.}
  method: {type: str, choices: [GET, POST, PUT, DELETE, HEAD, ANY, OPTIONS, PATCH], default: ANY, description: HTTP method.}
  description: {type: str, default: '', description: API description.}
  auth_type: {type: str, choices: [NONE, SECRET, OAUTH], default: NONE, description: Authentication type.}
  service_type: {type: str, choices: [HTTP, MOCK], default: MOCK, description: Backend type.}
  service_timeout: {type: int, default: 15, description: Backend timeout in seconds.}
  mock_response: {type: str, default: '{}', description: MOCK response body.}
  enable_cors: {type: bool, default: false, description: Enable CORS.}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.api_gateway_api:
    service_id: service-xxxxxxxx
    name: health
    path: /health
    method: GET
"""
RETURN = r"""api: {description: API metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.apigateway.v20180808 import apigateway_client, models

    return models, apigateway_client


def request_config(models, path, method):
    value = models.ApiRequestConfig()
    value.Path, value.Method = path, method
    return value


def build_list(models, service_id, name, offset=0):
    request = models.DescribeApisStatusRequest()
    request.ServiceId, request.Offset, request.Limit = service_id, offset, 100
    if name:
        item = models.Filter()
        item.Name, item.Values = "ApiName", [name]
        request.Filters = [item]
    return request


def build_get(models, service_id, api_id):
    request = models.DescribeApiRequest()
    request.ServiceId, request.ApiId = service_id, api_id
    return request


def apply_request(request, models, p, api_id=None):
    request.ServiceId, request.ApiName = p["service_id"], p["name"]
    request.ApiDesc, request.AuthType = p["description"], p["auth_type"]
    request.ServiceType, request.ServiceTimeout = p["service_type"], p["service_timeout"]
    request.Protocol, request.ApiType = "http", "NORMAL"
    request.RequestConfig = request_config(models, p["path"], p["method"])
    request.EnableCORS = p["enable_cors"]
    if p["service_type"] == "MOCK":
        request.ServiceMockReturnMessage = p["mock_response"]
    if api_id:
        request.ApiId = api_id
    return request


def desired(p):
    return {
        "ApiName": p["name"],
        "ApiDesc": p["description"],
        "AuthType": p["auth_type"],
        "ServiceType": p["service_type"],
        "ServiceTimeout": p["service_timeout"],
        "EnableCORS": p["enable_cors"],
        "Path": p["path"],
        "Method": p["method"],
    }


def comparable(value):
    config = value.get("RequestConfig") or {}
    return {
        "ApiName": value.get("ApiName"),
        "ApiDesc": value.get("ApiDesc") or "",
        "AuthType": value.get("AuthType"),
        "ServiceType": value.get("ServiceType"),
        "ServiceTimeout": value.get("ServiceTimeout"),
        "EnableCORS": bool(value.get("EnableCORS")),
        "Path": config.get("Path"),
        "Method": config.get("Method"),
    }


def find(module, client, models, p):
    if p["api_id"]:
        try:
            result = module.sdk_call(client.DescribeApi, build_get(models, p["service_id"], p["api_id"])).Result
            return result._serialize(allow_none=True) if result else None
        except Exception as exc:
            if is_not_found(exc):
                return None
            raise
    offset, matches = 0, []
    while p["name"]:
        result = module.sdk_call(client.DescribeApisStatus, build_list(models, p["service_id"], p["name"], offset)).Result
        items = list(getattr(result, "ApiIdStatusSet", None) or [])
        matches.extend(x._serialize(allow_none=True) for x in items if x.ApiName == p["name"])
        offset += len(items)
        if not items or offset >= int(result.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple APIs have the requested name", name=p["name"])
    if not matches:
        return None
    result = module.sdk_call(client.DescribeApi, build_get(models, p["service_id"], matches[0]["ApiId"])).Result
    return result._serialize(allow_none=True)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "service_id": {"required": True},
            "api_id": {},
            "name": {},
            "path": {"default": "/"},
            "method": {"choices": ["GET", "POST", "PUT", "DELETE", "HEAD", "ANY", "OPTIONS", "PATCH"], "default": "ANY"},
            "description": {"default": ""},
            "auth_type": {"choices": ["NONE", "SECRET", "OAUTH"], "default": "NONE"},
            "service_type": {"choices": ["HTTP", "MOCK"], "default": "MOCK"},
            "service_timeout": {"type": "int", "default": 15},
            "mock_response": {"default": "{}"},
            "enable_cors": {"type": "bool", "default": False},
        },
        required_one_of=[("api_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.ApigatewayClient, "apigateway.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, api=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.DeleteApiRequest()
                request.ServiceId, request.ApiId = p["service_id"], current["ApiId"]
                module.sdk_call(client.DeleteApi, request)
            module.exit_json(changed=True, **(diff or {}), api=current if module.check_mode else None)
        target = desired(p)
        if current and comparable(current) == target:
            module.exit_json(changed=False, api=current)
        if not current and not p["name"]:
            module.fail_json(msg="name is required when creating an API")
        diff = maybe_diff(module, comparable(current) if current else None, target)
        if not module.check_mode:
            if current:
                module.sdk_call(client.ModifyApi, apply_request(models.ModifyApiRequest(), models, p, current["ApiId"]))
                api_id = current["ApiId"]
            else:
                api_id = module.sdk_call(client.CreateApi, apply_request(models.CreateApiRequest(), models, p)).Result.ApiId
            p["api_id"] = api_id
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), api=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
