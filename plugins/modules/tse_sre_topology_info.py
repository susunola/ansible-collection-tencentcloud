#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tse_sre_topology_info
short_description: Gather Tencent Cloud TSE registry-engine topology
version_added: "0.14.0"
description: Returns replica and server-interface topology for Nacos or ZooKeeper registry engines.
options:
  instance_id: {type: str, required: true, description: TSE engine instance ID.}
  engine_type: {type: str, required: true, choices: [nacos, zookeeper], description: Registry-engine family.}
  page_size: {type: int, default: 100, description: Number of records requested per API call.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- susunola.tencentcloud.tse_sre_topology_info:
    instance_id: ins-xxxxxxxx
    engine_type: nacos
  register: engine_topology
'''

RETURN = r'''
replicas: {description: Engine replica topology., type: list, elements: dict, returned: always}
interfaces: {description: Engine server interfaces., type: list, elements: dict, returned: always}
replica_count: {description: Replica count reported by the API., type: int, returned: always}
interface_count: {description: Interface count reported by the API., type: int, returned: always}
request_ids: {description: Request IDs of the last replica and interface API calls., type: dict, returned: always}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client
    return models, tse_client


def build_request(request_class, instance_id, offset, limit):
    request = request_class()
    request.InstanceId = instance_id
    request.Offset = offset
    request.Limit = limit
    return request


def fetch_all(module, operation, request_class, instance_id, page_size, item_field):
    values = []
    offset = 0
    total = None
    request_id = None
    while total is None or offset < total:
        response = module.sdk_call(
            operation, build_request(request_class, instance_id, offset, page_size)
        )
        page = getattr(response, item_field, None) or []
        values.extend(item._serialize(allow_none=True) for item in page)
        total = getattr(response, "TotalCount", None)
        request_id = getattr(response, "RequestId", None)
        offset += len(page)
        if not page or total is None:
            break
    return values, total if total is not None else len(values), request_id


def run_module():
    spec = {
        "instance_id": {"required": True},
        "engine_type": {"required": True, "choices": ["nacos", "zookeeper"]},
        "page_size": {"type": "int", "default": 100},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    params = module.params
    if params["page_size"] < 1 or params["page_size"] > 100:
        module.fail_json(msg="page_size must be between 1 and 100")
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.TseClient, "tse.tencentcloudapi.com")
    if params["engine_type"] == "nacos":
        replica_operation = client.DescribeNacosReplicas
        replica_request_class = models.DescribeNacosReplicasRequest
        interface_operation = client.DescribeNacosServerInterfaces
        interface_request_class = models.DescribeNacosServerInterfacesRequest
    else:
        replica_operation = client.DescribeZookeeperReplicas
        replica_request_class = models.DescribeZookeeperReplicasRequest
        interface_operation = client.DescribeZookeeperServerInterfaces
        interface_request_class = models.DescribeZookeeperServerInterfacesRequest
    try:
        replicas, replica_count, replica_request_id = fetch_all(
            module, replica_operation, replica_request_class,
            params["instance_id"], params["page_size"], "Replicas"
        )
        interfaces, interface_count, interface_request_id = fetch_all(
            module, interface_operation, interface_request_class,
            params["instance_id"], params["page_size"], "Content"
        )
        module.exit_json(
            changed=False, replicas=replicas, interfaces=interfaces,
            replica_count=replica_count, interface_count=interface_count,
            request_ids={"replicas": replica_request_id, "interfaces": interface_request_id},
        )
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
