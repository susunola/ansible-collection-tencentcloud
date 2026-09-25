#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_gateway_route
short_description: Manage a Tencent Cloud TSE gateway route
version_added: "0.14.0"
description: Creates, updates and deletes an instance-unique cloud-native API gateway route.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  gateway_id:
    description:
      - Gateway the route is served by.
    type: str
    required: true
  service_id:
    description:
      - Owning gateway service ID; required when present.
    type: str
  route_id:
    description:
      - Existing route ID.
    type: str
  name:
    description:
      - Instance-unique route name.
    type: str
    required: true
  methods:
    description:
      - Accepted HTTP methods.
    type: list
    elements: str
  hosts:
    description:
      - Accepted host names.
    type: list
    elements: str
  paths:
    description:
      - Accepted paths.
    type: list
    elements: str
  protocols:
    description:
      - Accepted protocols.
    type: list
    elements: str
  preserve_host:
    description:
      - Preserve the incoming Host header.
    type: bool
  https_redirect_status_code:
    description:
      - Status code returned by the HTTP-to-HTTPS redirect on this route.
    type: int
  strip_path:
    description:
      - Strip the matched path before forwarding.
    type: bool
  force_https:
    description:
      - Redirect plain HTTP requests on this route to HTTPS.
    type: bool
  destination_ports:
    description:
      - Layer-4 destination ports.
    type: list
    elements: int
  headers:
    description:
      - SDK KVMapping header matchers.
    type: list
    elements: dict
  request_buffering:
    description:
      - Buffer request bodies.
    type: bool
  response_buffering:
    description:
      - Buffer response bodies.
    type: bool
  regex_priority:
    description:
      - Regular-expression route priority.
    type: int
  query_string_parameters:
    description:
      - SDK KVMapping query matchers.
    type: list
    elements: dict

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
  diff_mode:
    description:
      - Returns the difference between the observed and the requested state
        when the task runs with C(--diff).
    support: full
  idempotent:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_gateway_route:
    gateway_id: gateway-xxxxxxxx
    service_id: service-xxxxxxxx
    name: orders-api
    methods: [GET, POST]
    paths: [/orders]
    protocols: [https]
    strip_path: true

- name: Delete the route
  susunola.tencentcloud.tse_gateway_route:
    state: absent
    gateway_id: gateway-xxxxxxxx
    name: orders-api
"""
RETURN = r"""route:
  description:
    - Effective gateway route metadata.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    ID: route-1001
    Name: orders
    ServiceID: service-2001
    Methods:
      - GET
      - POST
    Hosts:
      - orders.example.com
    Paths:
      - /orders
    Protocols:
      - https
    StripPath: true
"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def list_request(models, p):
    r = models.DescribeCloudNativeAPIGatewayRoutesRequest()
    r.GatewayId, r.RouteName, r.Offset, r.Limit = p["gateway_id"], p["name"], 0, 1000
    return r


def write_request(cls, payload):
    r = cls()
    r.from_json_string(json.dumps(payload))
    return r


def delete_request(models, p, current):
    r = models.DeleteCloudNativeAPIGatewayRouteRequest()
    r.GatewayId, r.Name = p["gateway_id"], current.get("ID") or p["name"]
    return r


def find(module, client, models, p):
    result = module.sdk_call(client.DescribeCloudNativeAPIGatewayRoutes, list_request(models, p)).Result
    groups = result.RouteList if result else []
    matches = []
    for group in groups or []:
        for item in group.Routes or []:
            value = item._serialize(allow_none=True)
            if (p.get("route_id") and value.get("ID") == p["route_id"]) or (not p.get("route_id") and value.get("Name") == p["name"]):
                matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE gateway routes matched; specify route_id")
    return matches[0] if matches else None


def desired(p):
    mapping = {
        "methods": "Methods",
        "hosts": "Hosts",
        "paths": "Paths",
        "protocols": "Protocols",
        "preserve_host": "PreserveHost",
        "https_redirect_status_code": "HttpsRedirectStatusCode",
        "strip_path": "StripPath",
        "force_https": "ForceHttps",
        "destination_ports": "DestinationPorts",
        "headers": "Headers",
        "request_buffering": "RequestBuffering",
        "response_buffering": "ResponseBuffering",
        "regex_priority": "RegexPriority",
        "query_string_parameters": "QueryStringParameters",
    }
    value = {"Name": p["name"], "ServiceID": p["service_id"]}
    for source, target in mapping.items():
        if p.get(source) is not None:
            value[target] = p[source]
    return value


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and contains(actual[k], v) for k, v in expected.items())
    return actual == expected


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "gateway_id": {"required": True},
        "service_id": {"required": True},
        "route_id": {},
        "name": {"required": True},
        "methods": {"type": "list", "elements": "str"},
        "hosts": {"type": "list", "elements": "str"},
        "paths": {"type": "list", "elements": "str"},
        "protocols": {"type": "list", "elements": "str"},
        "preserve_host": {"type": "bool"},
        "https_redirect_status_code": {"type": "int"},
        "strip_path": {"type": "bool"},
        "force_https": {"type": "bool"},
        "destination_ports": {"type": "list", "elements": "int"},
        "headers": {"type": "list", "elements": "dict"},
        "request_buffering": {"type": "bool"},
        "response_buffering": {"type": "bool"},
        "regex_priority": {"type": "int"},
        "query_string_parameters": {"type": "list", "elements": "dict"},
    }
    spec["service_id"].pop("required", None)
    module = TencentCloudModule(argument_spec=spec, required_if=[("state", "present", ("service_id",))], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, route=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteCloudNativeAPIGatewayRoute, delete_request(models, p, current))
            module.exit_json(changed=True, **(diff or {}), route=None)
        target = desired(p)
        if not any(p.get(key) for key in ("methods", "hosts", "paths", "destination_ports")):
            module.fail_json(msg="At least one route matcher is required: methods, hosts, paths or destination_ports")
        if current and contains(current, target):
            module.exit_json(changed=False, route=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            keys = (
                "Methods",
                "Hosts",
                "Paths",
                "Protocols",
                "PreserveHost",
                "HttpsRedirectStatusCode",
                "StripPath",
                "ForceHttps",
                "DestinationPorts",
                "Headers",
                "RequestBuffering",
                "ResponseBuffering",
                "RegexPriority",
                "QueryStringParameters",
            )
            payload = {"GatewayId": p["gateway_id"], "ServiceID": p["service_id"], "RouteName": p["name"]}
            source = dict(current or {}, **target)
            for key in keys:
                if key in source:
                    payload[key] = source[key]
            if current:
                payload["RouteID"] = current["ID"]
            api = client.ModifyCloudNativeAPIGatewayRoute if current else client.CreateCloudNativeAPIGatewayRoute
            cls = models.ModifyCloudNativeAPIGatewayRouteRequest if current else models.CreateCloudNativeAPIGatewayRouteRequest
            module.sdk_call(api, write_request(cls, payload))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), route=current if not module.check_mode else target)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
