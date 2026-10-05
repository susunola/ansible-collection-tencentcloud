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
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  idempotent:
    description:
      - Read-only, so every run returns the current state and never changes
        the target, and a repeated run reports C(changed=false).
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
config_files:
  description:
    - Matching configuration files.
  returned: always
  type: list
  elements: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    - Name: a
total_count:
  description:
    - File count reported by Tencent Cloud.
  returned: always
  type: int
  sample: 3
request_id:
  description:
    - Request ID of the last API call.
  returned: always
  type: str
  sample: req-empty
'''

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.module_utils.paging import Paginator


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
    """Walk every page of the listing.

    Termination follows the shared paginator rather than a page counter: a
    short page ends the walk when the API reports no total, and a page the API
    serves twice is a failure instead of a loop. The loop this replaces
    advanced the offset by the size of the page it had just been handed and
    stopped only when a page came back empty, so an API that ignored ``Offset``
    while reporting no ``TotalCount`` never returned at all.

    The call goes through ``module.sdk_call`` rather than the plain read
    wrapper, so this module's ``retries`` option and the
    ``tencentcloud_resource_actions`` call audit trail stay in play.
    """
    paginator = Paginator(
        params["page_size"],
        lambda offset, limit: request(models, params, offset),
        lambda req: module.sdk_call(client.DescribeConfigFiles, req),
        lambda response: response.ConfigFiles,
        lambda response: response.TotalCount,
    )
    values, total = paginator.fetch_all()
    return ([item._serialize(allow_none=True) for item in values], total,
            paginator.request_id)


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
