#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tse_config_file_catalog_info
short_description: Gather Tencent Cloud TSE configuration file inventory
version_added: "0.14.0"
description: Returns a paginated configuration file catalog filtered by namespace, group, name, ID or tags.
options:
  instance_id: {type: str, required: true, description: TSE engine instance ID.}
  namespace: {type: str, description: Configuration namespace filter.}
  group: {type: str, description: Configuration group filter.}
  name: {type: str, description: Configuration file name filter.}
  config_file_id: {type: str, description: Configuration file ID filter.}
  tags: {type: list, elements: dict, description: SDK ConfigFileTag filter payloads.}
  page_size: {type: int, default: 100, description: Number of files requested per API call.}
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
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
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


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
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
