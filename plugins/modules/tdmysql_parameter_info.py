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
  retries: {type: int, default: 5, description: Retries for transient API failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
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
from ansible_collections.susunola.tencentcloud.plugins.modules.tdmysql_parameter import _load, read_parameters, selected


def run_module():
    module = TencentCloudModule(argument_spec={"instance_id": {"required": True}, "names": {"type": "list", "elements": "str"}}, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TdmysqlClient, "tdmysql.tencentcloudapi.com")
    try:
        values = read_parameters(module, client, models, p["instance_id"])
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
