#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_ray_job_list_info
short_description: List Tencent Cloud DLC Ray jobs
version_added: "0.14.0"
description:
  - Lists DLC Ray jobs with bounded page-number pagination, time bounds, stable filters and ordered sorting.
  - The API reports total pages but not total records, so O(fetched_count) is the exact returned count.
options:
  start_time: {type: int, description: Optional submission-time lower bound in milliseconds.}
  end_time: {type: int, description: Optional submission-time upper bound in milliseconds.}
  filters: {type: dict, default: {}, description: Ray job API filter names mapped to values or value lists.}
  sort_fields:
    type: list
    elements: dict
    description: Ordered API sort definitions.
    options:
      field: {type: str, required: true, description: API entity field name.}
      order: {type: str, choices: [ASC, DESC], default: ASC, description: Sort direction.}
  page_size: {type: int, default: 200, description: Jobs requested per page, from 1 to 200.}
  max_pages: {type: int, default: 1000, description: Maximum pages fetched, from 1 to 1000.}
  retries: {type: int, default: 5, description: Retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_ray_job_list_info:
    filters:
      status: [RUNNING, FAILED]
    sort_fields:
      - {field: CreateTime, order: DESC}
"""
RETURN = r"""
ray_jobs: {description: Matching Ray jobs., type: list, elements: dict, returned: always}
fetched_count: {description: Exact number of returned jobs., type: int, returned: always}
total_pages: {description: Number of pages reported by the API., type: int, returned: always}
truncated: {description: Whether max_pages stopped pagination., type: bool, returned: always}
request_id: {description: Request ID from the final page., type: str, returned: always}
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def build_request(models, p, page):
    request = models.ListRayJobsRequest()
    request.Page, request.PageSize = page, p["page_size"]
    if p.get("start_time") is not None:
        request.StartTime = p["start_time"]
    if p.get("end_time") is not None:
        request.EndTime = p["end_time"]
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
    jobs, total_pages, request_id, truncated = [], 0, None, False
    for page in range(1, p["max_pages"] + 1):
        response = module.sdk_call(client.ListRayJobs, build_request(models, p, page))
        items = response.Items or []
        jobs.extend(x._serialize(allow_none=True) for x in items)
        total_pages, request_id = int(response.TotalPages or 0), response.RequestId
        if page >= total_pages or not items:
            break
    else:
        truncated = True
    return jobs, total_pages, truncated, request_id


def run_module():
    sort = {"field": {"required": True}, "order": {"choices": ["ASC", "DESC"], "default": "ASC"}}
    spec = {
        "start_time": {"type": "int"},
        "end_time": {"type": "int"},
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
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        jobs, total_pages, truncated, request_id = read(module, client, models, p)
        module.exit_json(changed=False, ray_jobs=jobs, fetched_count=len(jobs), total_pages=total_pages, truncated=truncated, request_id=request_id)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
