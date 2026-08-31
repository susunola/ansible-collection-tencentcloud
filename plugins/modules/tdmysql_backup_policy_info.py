#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: tdmysql_backup_policy_info
short_description: Gather Tencent Cloud TDSQL MySQL backup policy
version_added: "0.14.0"
description: Returns the complete backup-policy list reported for an instance without assuming cardinality.
options:
  instance_id: {type: str, required: true, description: Stable TDSQL MySQL instance ID.}
  retries: {type: int, default: 5, description: Retries for transient API failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tdmysql_backup_policy_info:
    instance_id: tdsql3-xxxxxxxx
'''
RETURN = r'''
backup_policies: {description: Backup-policy metadata., type: list, elements: dict, returned: always}
total_count: {description: Policy count reported by the API., type: int, returned: always}
request_id: {description: Tencent Cloud request ID., type: str, returned: always}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.modules.tdmysql_backup_policy import _load, describe_request, normalize


def run_module():
    module = TencentCloudModule(argument_spec={"instance_id": {"required": True}}, supports_check_mode=True); p = module.params
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TdmysqlClient, "tdmysql.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeDBSBackupPolicy, describe_request(models, p["instance_id"])); values = [normalize(item._serialize(allow_none=True)) for item in response.Items or []]
        module.exit_json(changed=False, backup_policies=values, total_count=int(response.TotalCount or 0), request_id=response.RequestId)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
