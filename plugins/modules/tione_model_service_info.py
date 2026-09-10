#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tione_model_service_info
short_description: Gather Tencent Cloud TIONE online model services
version_added: "0.14.0"
description:
  - Returns one exact service version, one service group, or a filtered inventory of service groups and their versions.
  - List mode supports workspace, service status, model-version and tag filters with bounded offset pagination.
options:
  service_id: {type: str, description: Exact deployed service-version ID.}
  service_group_id: {type: str, description: Exact service-group ID.}
  project_id: {type: str, description: Optional TI workspace ID.}
  filters: {type: dict, default: {}, description: Service-group API filters used in list mode.}
  tag_filters: {type: dict, default: {}, description: Tag keys mapped to values or value lists in list mode.}
  order_field: {type: str, choices: [CreateTime, UpdateTime], default: UpdateTime, description: List sort field.}
  order: {type: str, choices: [ASC, DESC], default: DESC, description: List sort direction.}
  page_size: {type: int, default: 100, description: 'Service groups requested per page, from 1 to 100.'}
  max_pages: {type: int, default: 1000, description: 'Maximum pages fetched, from 1 to 1000.'}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tione_model_service_info:
    service_id: ms-xxxxxxxx

- susunola.tencentcloud.tione_model_service_info:
    service_group_id: ms-group-xxxxxxxx

- susunola.tencentcloud.tione_model_service_info:
    filters:
      Status: [Normal, Abnormal]
      ModelVersionId: modelversion-xxxxxxxx
    tag_filters:
      environment: production
"""
RETURN = r"""
service: {description: Exact deployed service-version detail., type: dict, returned: when service_id is provided}
service_group: {description: Exact service-group detail., type: dict, returned: when service_group_id is provided}
service_groups: {description: Matching service groups and embedded versions., type: list, elements: dict, returned: in list mode}
total_count: {description: Number of matching service groups., type: int, returned: in list mode}
global_total_count: {description: Total service groups in the current account and region., type: int, returned: in list mode}
truncated: {description: Whether max_pages stopped pagination., type: bool, returned: in list mode}
request_id: {description: Request ID from the exact request or final page., type: str, returned: always}
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tione.v20211111 import models, tione_client

    return models, tione_client


def service_request(models, p):
    request = models.DescribeModelServiceRequest()
    request.ServiceId = p["service_id"]
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    return request


def group_request(models, p):
    request = models.DescribeModelServiceGroupRequest()
    request.ServiceGroupId = p["service_group_id"]
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    return request


def list_request(models, p, offset):
    request = models.DescribeModelServiceGroupsRequest()
    request.Offset, request.Limit = offset, p["page_size"]
    request.Order, request.OrderField = p["order"], p["order_field"]
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    if p["filters"]:
        request.Filters = []
        for name, values in sorted(p["filters"].items()):
            item = models.Filter()
            item.Name, item.Values = name, values if isinstance(values, list) else [values]
            request.Filters.append(item)
    if p["tag_filters"]:
        request.TagFilters = []
        for key, values in sorted(p["tag_filters"].items()):
            item = models.TagFilter()
            item.TagKey, item.TagValues = key, values if isinstance(values, list) else [values]
            request.TagFilters.append(item)
    return request


def read_list(module, client, models, p):
    values, total, global_total, request_id, truncated, offset = [], 0, 0, None, False, 0
    for _ in range(p["max_pages"]):
        response = module.sdk_call(client.DescribeModelServiceGroups, list_request(models, p, offset))
        items = response.ServiceGroups or []
        values.extend(item._serialize(allow_none=True) for item in items)
        total, global_total, request_id = int(response.TotalCount or 0), int(response.GlobalTotalCount or 0), response.RequestId
        offset += len(items)
        if not items or offset >= total:
            break
    else:
        truncated = True
    return values, total, global_total, truncated, request_id


def run_module():
    spec = {
        "service_id": {},
        "service_group_id": {},
        "project_id": {},
        "filters": {"type": "dict", "default": {}},
        "tag_filters": {"type": "dict", "default": {}},
        "order_field": {"choices": ["CreateTime", "UpdateTime"], "default": "UpdateTime"},
        "order": {"choices": ["ASC", "DESC"], "default": "DESC"},
        "page_size": {"type": "int", "default": 100},
        "max_pages": {"type": "int", "default": 1000},
    }
    module = TencentCloudModule(
        argument_spec=spec,
        supports_check_mode=True,
        mutually_exclusive=[
            ("service_id", "service_group_id"),
            ("service_id", "filters"),
            ("service_id", "tag_filters"),
            ("service_group_id", "filters"),
            ("service_group_id", "tag_filters"),
        ],
    )
    p = module.params
    if not 1 <= p["page_size"] <= 100:
        module.fail_json(msg="page_size must be between 1 and 100")
    if not 1 <= p["max_pages"] <= 1000:
        module.fail_json(msg="max_pages must be between 1 and 1000")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TioneClient, "tione.tencentcloudapi.com")
    try:
        if p.get("service_id"):
            response = module.sdk_call(client.DescribeModelService, service_request(models, p))
            value = response.Service._serialize(allow_none=True) if response.Service else None
            module.exit_json(changed=False, service=value, request_id=response.RequestId)
        if p.get("service_group_id"):
            response = module.sdk_call(client.DescribeModelServiceGroup, group_request(models, p))
            value = response.ServiceGroup._serialize(allow_none=True) if response.ServiceGroup else None
            module.exit_json(changed=False, service_group=value, request_id=response.RequestId)
        values, total, global_total, truncated, request_id = read_list(module, client, models, p)
        module.exit_json(changed=False, service_groups=values, total_count=total, global_total_count=global_total, truncated=truncated, request_id=request_id)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
