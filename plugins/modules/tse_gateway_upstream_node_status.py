#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tse_gateway_upstream_node_status
short_description: Reconcile Tencent Cloud TSE gateway upstream node health state
version_added: "0.14.0"
description: Declaratively drains or restores one upstream target and waits for the queried topology to converge.
options:
  gateway_id: {type: str, required: true, description: Cloud-native API gateway ID.}
  service_name: {type: str, required: true, description: Gateway service name.}
  host: {type: str, required: true, description: Upstream target IP address or hostname.}
  port: {type: int, required: true, description: Upstream target port.}
  status: {type: str, required: true, choices: [HEALTHY, UNHEALTHY], description: Desired target state.}
  waiter_delay: {type: int, default: 2, description: Polling interval while waiting for convergence.}
  waiter_timeout: {type: int, default: 60, description: Maximum convergence wait.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- name: Drain one upstream node
  susunola.tencentcloud.tse_gateway_upstream_node_status:
    gateway_id: gateway-xxxxxxxx
    service_name: orders
    host: 10.0.0.20
    port: 8080
    status: UNHEALTHY
'''
RETURN = r'''
node: {description: Effective upstream target metadata., type: dict, returned: always}
'''

import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client
    return models, tse_client


def describe_request(models, params):
    value = models.DescribeCloudNativeAPIGatewayUpstreamRequest()
    value.GatewayId, value.ServiceName = params["gateway_id"], params["service_name"]
    return value


def modify_request(models, params):
    value = models.ModifyUpstreamNodeStatusRequest()
    value.GatewayId, value.ServiceName = params["gateway_id"], params["service_name"]
    value.Host, value.Port, value.Status = params["host"], params["port"], params["status"]
    return value


def find_node(module, client, models, params):
    response = module.sdk_call(client.DescribeCloudNativeAPIGatewayUpstream, describe_request(models, params))
    result = response.Result
    matches = []
    for upstream in ((result.UpstreamList if result else None) or []):
        for target in (upstream.Target or []):
            value = target._serialize(allow_none=True)
            if value.get("Host") == params["host"] and int(value.get("Port")) == params["port"]:
                matches.append(value)
    if not matches:
        module.fail_json(msg="TSE gateway upstream target was not found", service_name=params["service_name"],
                         host=params["host"], port=params["port"])
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE gateway upstream targets matched", service_name=params["service_name"],
                         host=params["host"], port=params["port"])
    return matches[0]


def wait(module, client, models, params):
    deadline = time.time() + params["waiter_timeout"]
    while True:
        node = find_node(module, client, models, params)
        if str(node.get("Health") or "").upper() == params["status"]:
            return node
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for TSE upstream target state convergence",
                             node=node, expected_status=params["status"])
        time.sleep(params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={
        "gateway_id": {"required": True}, "service_name": {"required": True},
        "host": {"required": True}, "port": {"type": "int", "required": True},
        "status": {"required": True, "choices": ["HEALTHY", "UNHEALTHY"]},
        "waiter_delay": {"type": "int", "default": 2}, "waiter_timeout": {"type": "int", "default": 60},
    }, supports_check_mode=True)
    params = module.params
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.TseClient, "tse.tencentcloudapi.com")
    try:
        node = find_node(module, client, models, params)
        before = str(node.get("Health") or "").upper()
        if before == params["status"]:
            module.exit_json(changed=False, node=node)
        diff = maybe_diff(module, {"Health": before}, {"Health": params["status"]})
        if not module.check_mode:
            response = module.sdk_call(client.ModifyUpstreamNodeStatus, modify_request(models, params))
            if response.Result is not True:
                module.fail_json(msg="TSE upstream target state operation returned an unsuccessful result")
            node = wait(module, client, models, params)
        else:
            node = dict(node, Health=params["status"])
        module.exit_json(changed=True, **(diff or {}), node=node)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
