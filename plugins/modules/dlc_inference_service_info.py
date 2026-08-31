#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: dlc_inference_service_info
short_description: Gather Tencent Cloud DLC inference services
version_added: "0.14.0"
description:
  - Lists DLC inference services with complete page-number pagination, time bounds, API filters and ordered sorting.
options:
  start_time: {type: int, description: Optional creation-time lower bound in milliseconds.}
  end_time: {type: int, description: Optional creation-time upper bound in milliseconds.}
  filters: {type: dict, default: {}, description: DLC inference-service filter names mapped to values or value lists.}
  sort_fields:
    type: list
    elements: dict
    description: Ordered API sort definitions.
    options:
      field: {type: str, required: true, description: API entity field name.}
      order: {type: str, choices: [ASC, DESC], default: ASC, description: Sort direction.}
  page_size: {type: int, default: 200, description: Services requested per page, from 1 to 200.}
  max_pages: {type: int, default: 1000, description: Maximum pages fetched, from 1 to 1000.}
  retries: {type: int, default: 5, description: Retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.dlc_inference_service_info:
    filters:
      status: [Running, Stopped]
    sort_fields:
      - {field: CreateTime, order: DESC}
'''
RETURN = r'''
services: {description: Matching DLC inference services., type: list, elements: dict, returned: always}
total_count: {description: Number of services reported by the API., type: int, returned: always}
truncated: {description: Whether max_pages stopped pagination., type: bool, returned: always}
request_id: {description: Request ID from the final page., type: str, returned: always}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client
    return models, dlc_client


def build_request(models, p, page):
    request = models.ListInferenceServicesRequest(); request.Page, request.PageSize = page, p["page_size"]
    if p.get("start_time") is not None: request.StartTime = p["start_time"]
    if p.get("end_time") is not None: request.EndTime = p["end_time"]
    if p["filters"]:
        request.Filters = []
        for name, values in sorted(p["filters"].items()):
            item = models.Filter(); item.Name, item.Values = name, values if isinstance(values, list) else [values]; request.Filters.append(item)
    if p.get("sort_fields"):
        request.SortFields = []
        for value in p["sort_fields"]:
            item = models.SortField(); item.Field, item.Order = value["field"], value["order"]; request.SortFields.append(item)
    return request


def read(module, client, models, p):
    services, total, request_id, truncated = [], 0, None, False
    for page in range(1, p["max_pages"] + 1):
        response = module.sdk_call(client.ListInferenceServices, build_request(models, p, page)); items = response.Items or []
        services.extend(x._serialize(allow_none=True) for x in items); total, request_id = int(response.Total or 0), response.RequestId
        if page >= int(response.TotalPages or 0) or not items: break
    else: truncated = True
    return services, total, truncated, request_id


def run_module():
    sort = {"field": {"required": True}, "order": {"choices": ["ASC", "DESC"], "default": "ASC"}}
    spec = {
        "start_time": {"type": "int"}, "end_time": {"type": "int"}, "filters": {"type": "dict", "default": {}},
        "sort_fields": {"type": "list", "elements": "dict", "options": sort}, "page_size": {"type": "int", "default": 200},
        "max_pages": {"type": "int", "default": 1000},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True); p = module.params
    if not 1 <= p["page_size"] <= 200: module.fail_json(msg="page_size must be between 1 and 200")
    if not 1 <= p["max_pages"] <= 1000: module.fail_json(msg="max_pages must be between 1 and 1000")
    if p.get("start_time") is not None and p.get("end_time") is not None and p["start_time"] > p["end_time"]: module.fail_json(msg="start_time must not exceed end_time")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        services, total, truncated, request_id = read(module, client, models, p)
        module.exit_json(changed=False, services=services, total_count=total, truncated=truncated, request_id=request_id)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
