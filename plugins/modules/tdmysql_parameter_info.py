#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tdmysql_parameter_info
short_description: Gather Tencent Cloud TDSQL MySQL instance parameters
version_added: "0.14.0"
description: Returns current parameter values, defaults, constraints and restart requirements.
options:
  instance_id: {type: str, required: true, description: Stable TDSQL MySQL instance ID.}
  names: {type: list, elements: str, description: Optional exact parameter names to return.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tdmysql_parameter_info:
    instance_id: tdsql3-xxxxxxxx
    names: [max_connections, slow_query_log]
"""
RETURN = r"""
parameters: {description: Parameter metadata keyed by name., type: dict, returned: always}
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
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
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
