#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tse_gateway_service_inventory_info
short_description: Gather Tencent Cloud TSE gateway service and route inventory
version_added: "0.14.0"
description: Returns paginated service-to-route relationships and optionally resolves upstream targets for every matching service.
options:
  gateway_id: {type: str, required: true, description: Cloud-native API gateway ID.}
  filters: {type: dict, default: {}, description: Service filters such as name and upstreamType.}
  include_upstreams: {type: bool, default: false, description: Query upstream targets for every matching service.}
  page_size: {type: int, default: 100, description: Number of services requested per API call.}
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tse_gateway_service_inventory_info:
    gateway_id: gateway-xxxxxxxx
    include_upstreams: true
  register: gateway_inventory
'''
RETURN = r'''
services: {description: Gateway services with nested route relationships., type: list, elements: dict, returned: always}
upstreams: {description: Upstream target data keyed by service name., type: dict, returned: always}
total_count: {description: Service count reported by the API., type: int, returned: always}
request_ids: {description: Request IDs for inventory and upstream queries., type: dict, returned: always}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client
    return models, tse_client


def inventory_request(models, params, offset):
    value = models.DescribeCNGWServicesWithRoutesRequest()
    value.GatewayId, value.Offset, value.Limit = params["gateway_id"], offset, params["page_size"]
    value.Filters = []
    for key, selected in sorted(params["filters"].items()):
        item = models.ListFilter()
        item.Key, item.Value = key, str(selected)
        value.Filters.append(item)
    return value


def upstream_request(models, gateway_id, service_name):
    value = models.DescribeCloudNativeAPIGatewayUpstreamRequest()
    value.GatewayId, value.ServiceName = gateway_id, service_name
    return value


def fetch_inventory(module, client, models, params):
    services, offset, total, request_id = [], 0, None, None
    while total is None or offset < total:
        response = module.sdk_call(client.DescribeCNGWServicesWithRoutes, inventory_request(models, params, offset))
        result = response.Result
        page = (result.ServiceList if result else None) or []
        services.extend(item._serialize(allow_none=True) for item in page)
        total, request_id = (result.TotalCount if result else 0), response.RequestId
        offset += len(page)
        if not page:
            break
    return services, total if total is not None else len(services), request_id


def service_name(value):
    return value.get("Name") or value.get("ServiceName")


def run_module():
    module = TencentCloudModule(argument_spec={
        "gateway_id": {"required": True}, "filters": {"type": "dict", "default": {}},
        "include_upstreams": {"type": "bool", "default": False},
        "page_size": {"type": "int", "default": 100},
    }, supports_check_mode=True)
    params = module.params
    if params["page_size"] < 1 or params["page_size"] > 100:
        module.fail_json(msg="page_size must be between 1 and 100")
    unsupported = sorted(set(params["filters"]) - {"name", "upstreamType"})
    if unsupported:
        module.fail_json(msg="unsupported TSE gateway service inventory filters", unsupported_filters=unsupported)
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.TseClient, "tse.tencentcloudapi.com")
    try:
        services, total_count, inventory_request_id = fetch_inventory(module, client, models, params)
        upstreams, upstream_request_ids = {}, {}
        if params["include_upstreams"]:
            for name in sorted(set(filter(None, (service_name(value) for value in services)))):
                response = module.sdk_call(
                    client.DescribeCloudNativeAPIGatewayUpstream,
                    upstream_request(models, params["gateway_id"], name),
                )
                upstreams[name] = response.Result._serialize(allow_none=True) if response.Result else {}
                upstream_request_ids[name] = response.RequestId
        module.exit_json(
            changed=False, services=services, upstreams=upstreams, total_count=total_count,
            request_ids={"inventory": inventory_request_id, "upstreams": upstream_request_ids},
        )
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
