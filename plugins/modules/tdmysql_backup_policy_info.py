#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tdmysql_backup_policy_info
short_description: Gather Tencent Cloud TDSQL MySQL backup policy
version_added: "0.14.0"
description: Returns the complete backup-policy list reported for an instance without assuming cardinality.
options:
  instance_id:
    description:
      - Stable TDSQL MySQL instance ID.
    type: str
    required: true

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
"""
EXAMPLES = r"""
- susunola.tencentcloud.tdmysql_backup_policy_info:
    instance_id: tdsql3-xxxxxxxx
"""
RETURN = r"""
backup_policies:
  description:
    - Backup-policy metadata.
  returned: always
  type: list
  elements: dict
total_count:
  description:
    - Policy count reported by the API.
  returned: always
  type: int
request_id:
  description:
    - Tencent Cloud request ID.
  returned: always
  type: str
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tdmysql import _load, backup_policy_describe_request, normalize


def run_module():
    module = TencentCloudModule(argument_spec={"instance_id": {"required": True}}, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TdmysqlClient, "tdmysql.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeDBSBackupPolicy, backup_policy_describe_request(models, p["instance_id"]))
        values = [normalize(item._serialize(allow_none=True)) for item in response.Items or []]
        module.exit_json(changed=False, backup_policies=values, total_count=int(response.TotalCount or 0), request_id=response.RequestId)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
