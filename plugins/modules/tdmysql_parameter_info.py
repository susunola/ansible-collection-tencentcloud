#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tdmysql_parameter_info
short_description: Gather Tencent Cloud TDSQL MySQL instance parameters
version_added: "0.14.0"
description: Returns current parameter values, defaults, constraints and restart requirements.
options:
  instance_id:
    description:
      - Stable TDSQL MySQL instance ID.
    type: str
    required: true
  names:
    description:
      - Optional exact parameter names to return.
    type: list
    elements: str

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
seealso:
  - module: susunola.tencentcloud.tdmysql_parameter
    description: Manage Tencent Cloud TDSQL MySQL instance parameters.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tdmysql_parameter_info:
    instance_id: tdsql3-xxxxxxxx
    names: [max_connections, slow_query_log]
"""
RETURN = r"""
parameters:
  description:
    - Parameter metadata keyed by name.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    max_connections:
      Param: max_connections
      Value: '151'
      Default: '151'
      NeedRestart: 0
      Description: Maximum permitted simultaneous client connections
    slow_query_log:
      Param: slow_query_log
      Value: 'ON'
      Default: 'OFF'
      NeedRestart: 1
      Description: Whether the slow query log is enabled
    innodb_buffer_pool_size:
      Param: innodb_buffer_pool_size
      Value: '134217728'
      Default: '134217728'
      NeedRestart: 0
      Description: InnoDB buffer pool size in bytes
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tdmysql import _load, parameter_describe_request, parameter_map, selected


def run_module():
    module = TencentCloudModule(argument_spec={"instance_id": {"required": True}, "names": {"type": "list", "elements": "str"}}, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TdmysqlClient, "tdmysql.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeDBParameters, parameter_describe_request(models, p["instance_id"]))
        values = parameter_map(response)
        if p.get("names") is not None:
            missing = sorted(set(p["names"]) - set(values))
            if missing:
                module.fail_json(msg="unknown TDSQL MySQL parameter names", unknown_parameters=missing)
            values = selected(values, p["names"])
        module.exit_json(changed=False, parameters=values)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
