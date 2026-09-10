#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tse_gateway_runtime_info
short_description: Gather Tencent Cloud TSE gateway runtime topology
version_added: "0.14.0"
description: Returns gateway network configuration, protocol ports, public addresses and optional group nodes.
options:
  gateway_id: {type: str, required: true, description: Cloud-native API gateway ID.}
  group_id: {type: str, description: 'Optional gateway group ID used to scope configuration, addresses and nodes.'}
  page_size: {type: int, default: 100, description: Number of nodes requested per API call.}
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tse_gateway_runtime_info:
    gateway_id: gateway-xxxxxxxx
    group_id: group-xxxxxxxx
  register: gateway_runtime
'''
RETURN = r'''
network_config: {description: Gateway or group network configuration., type: dict, returned: always}
ports: {description: Gateway protocol port configuration., type: dict, returned: always}
public_addresses: {description: Public address configurations., type: list, elements: dict, returned: always}
nodes: {description: Nodes in the selected gateway group., type: list, elements: dict, returned: always}
node_count: {description: Node count reported by the API., type: int, returned: always}
request_ids: {description: Request IDs keyed by query type., type: dict, returned: always}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client
    return models, tse_client


def request(request_class, gateway_id, group_id=None):
    value = request_class()
    value.GatewayId = gateway_id
    if hasattr(value, "GroupId"):
        value.GroupId = group_id
    return value


def serialized(value):
    return value._serialize(allow_none=True) if value else {}


def fetch_nodes(module, client, models, gateway_id, group_id, page_size):
    nodes, offset, total, request_id = [], 0, None, None
    while total is None or offset < total:
        value = request(models.DescribeCloudNativeAPIGatewayNodesRequest, gateway_id, group_id)
        value.Offset, value.Limit = offset, page_size
        response = module.sdk_call(client.DescribeCloudNativeAPIGatewayNodes, value)
        result = response.Result
        page = (result.NodeList if result else None) or []
        nodes.extend(serialized(item) for item in page)
        total = result.TotalCount if result else 0
        request_id = response.RequestId
        offset += len(page)
        if not page:
            break
    return nodes, total if total is not None else len(nodes), request_id


def run_module():
    module = TencentCloudModule(argument_spec={
        "gateway_id": {"required": True}, "group_id": {},
        "page_size": {"type": "int", "default": 100},
    }, supports_check_mode=True)
    params = module.params
    if params["page_size"] < 1 or params["page_size"] > 100:
        module.fail_json(msg="page_size must be between 1 and 100")
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.TseClient, "tse.tencentcloudapi.com")
    try:
        config_response = module.sdk_call(
            client.DescribeCloudNativeAPIGatewayConfig,
            request(models.DescribeCloudNativeAPIGatewayConfigRequest, params["gateway_id"], params.get("group_id")),
        )
        ports_response = module.sdk_call(
            client.DescribeCloudNativeAPIGatewayPorts,
            request(models.DescribeCloudNativeAPIGatewayPortsRequest, params["gateway_id"]),
        )
        address_response = module.sdk_call(
            client.DescribePublicAddressConfig,
            request(models.DescribePublicAddressConfigRequest, params["gateway_id"], params.get("group_id")),
        )
        address_result = address_response.Result
        nodes, node_count, node_request_id = ([], 0, None)
        if params.get("group_id"):
            nodes, node_count, node_request_id = fetch_nodes(
                module, client, models, params["gateway_id"], params["group_id"], params["page_size"]
            )
        module.exit_json(
            changed=False, network_config=serialized(config_response.Result),
            ports=serialized(ports_response.Result),
            public_addresses=[serialized(item) for item in ((address_result.ConfigList if address_result else None) or [])],
            nodes=nodes, node_count=node_count,
            request_ids={"network_config": config_response.RequestId, "ports": ports_response.RequestId,
                         "public_addresses": address_response.RequestId, "nodes": node_request_id},
        )
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
