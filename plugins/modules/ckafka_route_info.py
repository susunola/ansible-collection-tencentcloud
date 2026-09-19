#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: ckafka_route_info
short_description: Gather Tencent Cloud CKafka access routes
version_added: "1.4.0"
description:
  - Returns observable access routes for a CKafka instance.
  - Results can be narrowed by route ID or immutable network identity.
options:
  instance_id:
    description: CKafka instance ID.
    type: str
    required: true
  route_id:
    description: Route ID to read.
    type: int
  network_type:
    description: Public, VPC or internal-support route type.
    type: int
    choices: [1, 3, 7]
  access_type:
    description: Authentication and transport mode.
    type: int
    choices: [0, 1, 3, 4, 5]
  vpc_id:
    description: VPC ID used to filter routes.
    type: str
  subnet_id:
    description: Subnet ID used to filter routes.
    type: str
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Read all routes for an instance
  susunola.tencentcloud.ckafka_route_info:
    region: ap-guangzhou
    instance_id: ckafka-xxxxxxxx

- name: Read one VPC route
  susunola.tencentcloud.ckafka_route_info:
    region: ap-guangzhou
    instance_id: ckafka-xxxxxxxx
    network_type: 3
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
'''

RETURN = r'''
routes:
  description: Matching access routes.
  returned: always
  type: list
  elements: dict
route:
  description: The single matching route when exactly one route matches.
  returned: always
  type: dict
request_id:
  description: Request ID returned by the API.
  returned: always
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile,
    create_credential,
    sdk_call,
    serialize_sdk_object,
    tencentcloud_argument_spec,
)


def build_request(models, instance_id, route_id=None):
    request = models.DescribeRouteRequest()
    request.InstanceId = instance_id
    request.RouteId = route_id
    return request


def matches(route, route_id=None, network_type=None, access_type=None, vpc_id=None, subnet_id=None):
    return all(
        (
            route_id is None or int(route.get("RouteId") or 0) == route_id,
            network_type is None or route.get("VipType") == network_type,
            access_type is None or route.get("AccessType") == access_type,
            vpc_id is None or (route.get("VpcId") or None) == vpc_id,
            subnet_id is None or (route.get("Subnet") or None) == subnet_id,
        )
    )


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update(
        {
            "instance_id": {"type": "str", "required": True},
            "route_id": {"type": "int"},
            "network_type": {"type": "int", "choices": [1, 3, 7]},
            "access_type": {"type": "int", "choices": [0, 1, 3, 4, 5]},
            "vpc_id": {"type": "str"},
            "subnet_id": {"type": "str"},
        }
    )
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    try:
        from tencentcloud.ckafka.v20190819 import ckafka_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-ckafka package is required.")

    p = module.params
    client = ckafka_client.CkafkaClient(create_credential(module), p["region"], create_client_profile(module, "ckafka.tencentcloudapi.com"))
    response = sdk_call(module, client.DescribeRoute, build_request(models, p["instance_id"], p.get("route_id")))
    result = getattr(response, "Result", None)
    routes = [serialize_sdk_object(item) for item in (getattr(result, "Routers", None) or [])]
    routes = [item for item in routes if matches(item, p.get("route_id"), p.get("network_type"), p.get("access_type"), p.get("vpc_id"), p.get("subnet_id"))]
    module.exit_json(changed=False, routes=routes, route=routes[0] if len(routes) == 1 else None, request_id=getattr(response, "RequestId", None))


def main():
    run_module()


if __name__ == "__main__":
    main()
