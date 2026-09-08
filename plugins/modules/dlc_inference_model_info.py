#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_inference_model_info
short_description: Gather Tencent Cloud DLC inference models
version_added: "0.14.0"
description:
  - Lists DLC inference models with bounded page-number pagination, time bounds, parameter-size bounds, stable filters and ordered sorting.
options:
  start_time: {type: int, description: Optional creation-time lower bound in milliseconds.}
  end_time: {type: int, description: Optional creation-time upper bound in milliseconds.}
  parameter_size_min: {type: float, description: Optional minimum model parameter size.}
  parameter_size_max: {type: float, description: Optional maximum model parameter size.}
  filters: {type: dict, default: {}, description: Inference-model API filter names mapped to values or value lists.}
  sort_fields:
    type: list
    elements: dict
    description: Ordered API sort definitions.
    options:
      field: {type: str, required: true, description: API entity field name.}
      order: {type: str, choices: [ASC, DESC], default: ASC, description: Sort direction.}
  page_size: {type: int, default: 200, description: Models requested per page, from 1 to 200.}
  max_pages: {type: int, default: 1000, description: Maximum pages fetched, from 1 to 1000.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_inference_model_info:
    parameter_size_min: 7
    parameter_size_max: 70
    sort_fields:
      - {field: CreateTime, order: DESC}
"""
RETURN = r"""
models: {description: Matching DLC inference models., type: list, elements: dict, returned: always}
total_count: {description: Number of models reported by the API., type: int, returned: always}
truncated: {description: Whether max_pages stopped pagination., type: bool, returned: always}
request_id: {description: Request ID from the final page., type: str, returned: always}
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def build_request(models, p, page):
    request = models.ListInferenceModelsRequest()
    request.Page, request.PageSize = page, p["page_size"]
    for source, target in (
        ("start_time", "StartTime"),
        ("end_time", "EndTime"),
        ("parameter_size_min", "ParameterSizeMin"),
        ("parameter_size_max", "ParameterSizeMax"),
    ):
        if p.get(source) is not None:
            setattr(request, target, p[source])
    if p["filters"]:
        request.Filters = []
        for name, values in sorted(p["filters"].items()):
            item = models.Filter()
            item.Name, item.Values = name, values if isinstance(values, list) else [values]
            request.Filters.append(item)
    if p.get("sort_fields"):
        request.SortFields = []
        for value in p["sort_fields"]:
            item = models.SortField()
            item.Field, item.Order = value["field"], value["order"]
            request.SortFields.append(item)
    return request


def read(module, client, models, p):
    values, total, request_id, truncated = [], 0, None, False
    for page in range(1, p["max_pages"] + 1):
        response = module.sdk_call(client.ListInferenceModels, build_request(models, p, page))
        items = response.Items or []
        values.extend(x._serialize(allow_none=True) for x in items)
        total, request_id = int(response.Total or 0), response.RequestId
        if page >= int(response.TotalPages or 0) or not items:
            break
    else:
        truncated = True
    return values, total, truncated, request_id


def run_module():
    sort = {"field": {"required": True}, "order": {"choices": ["ASC", "DESC"], "default": "ASC"}}
    spec = {
        "start_time": {"type": "int"},
        "end_time": {"type": "int"},
        "parameter_size_min": {"type": "float"},
        "parameter_size_max": {"type": "float"},
        "filters": {"type": "dict", "default": {}},
        "sort_fields": {"type": "list", "elements": "dict", "options": sort},
        "page_size": {"type": "int", "default": 200},
        "max_pages": {"type": "int", "default": 1000},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if not 1 <= p["page_size"] <= 200:
        module.fail_json(msg="page_size must be between 1 and 200")
    if not 1 <= p["max_pages"] <= 1000:
        module.fail_json(msg="max_pages must be between 1 and 1000")
    if p.get("start_time") is not None and p.get("end_time") is not None and p["start_time"] > p["end_time"]:
        module.fail_json(msg="start_time must not exceed end_time")
    if p.get("parameter_size_min") is not None and p.get("parameter_size_max") is not None and p["parameter_size_min"] > p["parameter_size_max"]:
        module.fail_json(msg="parameter_size_min must not exceed parameter_size_max")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        values, total, truncated, request_id = read(module, client, models, p)
        module.exit_json(changed=False, models=values, total_count=total, truncated=truncated, request_id=request_id)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
