#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tione_data_source_info
short_description: Gather Tencent Cloud TIONE data sources
version_added: "0.14.0"
description:
  - Lists TIONE storage data sources with workspace scoping, stable filters, tag filters, sorting and bounded offset pagination.
options:
  project_id: {type: str, description: Optional TI workspace ID.}
  filters: {type: dict, default: {}, description: Data-source API filter names mapped to values or value lists.}
  tag_filters: {type: dict, default: {}, description: Tag keys mapped to tag values or value lists.}
  order_field: {type: str, description: API field used for ordering.}
  order: {type: str, choices: [ASC, DESC], default: DESC, description: Sort direction.}
  page_size: {type: int, default: 200, description: Data sources requested per page, from 1 to 200.}
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
- susunola.tencentcloud.tione_data_source_info:
    project_id: workspace-xxxxxxxx
    filters:
      Type: CFS
      Permission: RW
    tag_filters:
      environment: production
    order_field: CreateTime
    order: DESC
"""
RETURN = r"""
data_sources: {description: Matching TIONE data sources., type: list, elements: dict, returned: always}
total_count: {description: Number of data sources reported by the API., type: int, returned: always}
truncated: {description: Whether max_pages stopped pagination., type: bool, returned: always}
request_id: {description: Request ID from the final page., type: str, returned: always}
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tione.v20211111 import models, tione_client

    return models, tione_client


def build_request(models, p, offset):
    request = models.DescribeDataSourcesRequest()
    request.Offset, request.Limit = offset, p["page_size"]
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
    if p.get("order_field") is not None:
        request.OrderField = p["order_field"]
    request.Order = p["order"]
    return request


def read(module, client, models, p):
    values, total, request_id, truncated, offset = [], 0, None, False, 0
    for _ in range(p["max_pages"]):
        response = module.sdk_call(client.DescribeDataSources, build_request(models, p, offset))
        items = response.DataSourceInfos or []
        values.extend(item._serialize(allow_none=True) for item in items)
        total, request_id = int(response.TotalCount or 0), response.RequestId
        offset += len(items)
        if not items or offset >= total:
            break
    else:
        truncated = True
    return values, total, truncated, request_id


def run_module():
    spec = {
        "project_id": {},
        "filters": {"type": "dict", "default": {}},
        "tag_filters": {"type": "dict", "default": {}},
        "order_field": {},
        "order": {"choices": ["ASC", "DESC"], "default": "DESC"},
        "page_size": {"type": "int", "default": 200},
        "max_pages": {"type": "int", "default": 1000},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if not 1 <= p["page_size"] <= 200:
        module.fail_json(msg="page_size must be between 1 and 200")
    if not 1 <= p["max_pages"] <= 1000:
        module.fail_json(msg="max_pages must be between 1 and 1000")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TioneClient, "tione.tencentcloudapi.com")
    try:
        values, total, truncated, request_id = read(module, client, models, p)
        module.exit_json(changed=False, data_sources=values, total_count=total, truncated=truncated, request_id=request_id)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
