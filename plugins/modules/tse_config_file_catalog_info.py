#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tse_config_file_catalog_info
short_description: Gather Tencent Cloud TSE configuration file inventory
version_added: "0.14.0"
description: Returns a paginated configuration file catalog filtered by namespace, group, name, ID or tags.
options:
  instance_id:
    description:
      - TSE engine instance ID.
    type: str
    required: true
  namespace:
    description:
      - Configuration namespace filter.
    type: str
  group:
    description:
      - Configuration group filter.
    type: str
  name:
    description:
      - Configuration file name filter.
    type: str
  config_file_id:
    description:
      - Configuration file ID filter.
    type: str
  tags:
    description:
      - SDK ConfigFileTag filter payloads.
    type: list
    elements: dict
  page_size:
    description:
      - Number of files requested per API call.
    type: int
    default: 100
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
attributes:
  check_mode:
    description:
      - 'Can run in C(check_mode): the module reads the current state and
        predicts the result without issuing a write API call.'
    support: full
  idempotency:
    description:
      - 'Read-only: every run returns the current state and never changes
        the target, so a repeated run reports C(changed=false).'
    support: full
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tse_config_file_catalog_info:
    instance_id: ins-xxxxxxxx
    namespace: production
    group: application
  register: config_catalog
'''
RETURN = r'''
config_files: {description: Matching configuration files., type: list, elements: dict, returned: always}
total_count: {description: File count reported by Tencent Cloud., type: int, returned: always}
request_id: {description: Request ID of the last API call., type: str, returned: always}
'''

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client
    return models, tse_client


def request(models, params, offset):
    value = models.DescribeConfigFilesRequest()
    value.InstanceId, value.Namespace, value.Group = params["instance_id"], params.get("namespace"), params.get("group")
    value.Name, value.Id = params.get("name"), params.get("config_file_id")
    value.Offset, value.Limit = offset, params["page_size"]
    if params.get("tags") is not None:
        value.Tags = []
        for selected in params["tags"]:
            item = models.ConfigFileTag()
            item.from_json_string(json.dumps(selected))
            value.Tags.append(item)
    return value


def fetch_all(module, client, models, params):
    values, offset, total, request_id = [], 0, None, None
    while total is None or offset < total:
        response = module.sdk_call(client.DescribeConfigFiles, request(models, params, offset))
        page = response.ConfigFiles or []
        values.extend(item._serialize(allow_none=True) for item in page)
        total, request_id = response.TotalCount, response.RequestId
        offset += len(page)
        if not page:
            break
    return values, total if total is not None else len(values), request_id


def run_module():
    module = TencentCloudModule(argument_spec={
        "instance_id": {"required": True}, "namespace": {}, "group": {}, "name": {}, "config_file_id": {},
        "tags": {"type": "list", "elements": "dict"}, "page_size": {"type": "int", "default": 100},
    }, supports_check_mode=True)
    params = module.params
    if params["page_size"] < 1 or params["page_size"] > 100:
        module.fail_json(msg="page_size must be between 1 and 100")
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.TseClient, "tse.tencentcloudapi.com")
    try:
        config_files, total_count, request_id = fetch_all(module, client, models, params)
        module.exit_json(changed=False, config_files=config_files, total_count=total_count, request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
