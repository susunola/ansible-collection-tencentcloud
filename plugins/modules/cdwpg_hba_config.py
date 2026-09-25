#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cdwpg_hba_config
short_description: Manage Tencent Cloud CDW PostgreSQL HBA rules
version_added: "0.14.0"
description:
  - Replaces the complete user-managed pg_hba rule list while preserving rule order.
  - Emptying the list requires explicit authorization because it can remove database access.
options:
  instance_id:
    description:
      - CDW PostgreSQL instance ID.
    type: str
    required: true
  rules:
    type: list
    elements: dict
    required: true
    description: Exact ordered HBA rule list.
    suboptions:
      type:
        description:
          - Connection type such as host or hostssl.
        type: str
        required: true
      database:
        description:
          - Database selector.
        type: str
        required: true
      user:
        description:
          - User selector.
        type: str
        required: true
      address:
        description:
          - Client address or CIDR.
        type: str
        required: true
      method:
        description:
          - Authentication method.
        type: str
        required: true
      mask:
        description:
          - Optional service mask value.
        type: str
  allow_empty:
    description:
      - Explicitly authorize removing every user-managed HBA rule.
    type: bool
    default: false

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
  diff_mode:
    description:
      - Returns the difference between the observed and the requested state
        when the task runs with C(--diff).
    support: full
  idempotent:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
seealso:
  - module: susunola.tencentcloud.cdwpg_hba_config_info
    description: Gather information about Tencent Cloud CDWPG user hba configs.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cdwpg_hba_config:
    instance_id: cdwpg-xxxxxxxx
    rules:
      - {type: hostssl, database: all, user: analysts, address: 10.0.0.0/16, method: md5}
"""
RETURN = r"""rules:
  description:
    - Effective ordered HBA rules.
  returned: always
  type: list
  elements: dict
task_id:
  description:
    - Service task ID.
  returned: when changed
  type: int"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error

FIELDS = (("type", "Type"), ("database", "Database"), ("user", "User"), ("address", "Address"), ("method", "Method"), ("mask", "Mask"))


def _load():
    from tencentcloud.cdwpg.v20201230 import models, cdwpg_client

    return models, cdwpg_client


def normalize(values):
    result = []
    for item in values or []:
        value = {}
        for key, sdk in FIELDS:
            field_value = item.get(key) if key in item else item.get(sdk)
            if field_value is not None:
                value[sdk] = field_value
        result.append(value)
    return result


def describe(module, client, models, instance_id):
    r = models.DescribeUserHbaConfigRequest()
    r.InstanceId = instance_id
    response = module.sdk_call(client.DescribeUserHbaConfig, r)
    return normalize([x._serialize(allow_none=True) for x in response.HbaConfigs or []])


def change_request(models, instance_id, rules):
    r = models.ModifyUserHbaRequest()
    r.InstanceId = instance_id
    r.HbaConfigs = []
    for value in rules:
        item = models.HbaConfig()
        item.from_json_string(json.dumps(value))
        r.HbaConfigs.append(item)
    return r


def run_module():
    rule_options = {key: {"required": key != "mask"} for key, _ in FIELDS}
    module = TencentCloudModule(
        argument_spec={
            "instance_id": {"required": True},
            "rules": {"type": "list", "elements": "dict", "required": True, "options": rule_options},
            "allow_empty": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    p = module.params
    if not p["rules"] and not p["allow_empty"]:
        module.fail_json(msg="set allow_empty=true to authorize removing every CDW PostgreSQL HBA rule")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CdwpgClient, "cdwpg.tencentcloudapi.com")
    try:
        current = describe(module, client, models, p["instance_id"])
        target = normalize(p["rules"])
        if current == target:
            module.exit_json(changed=False, rules=current)
        diff = maybe_diff(module, current, target)
        task_id = None
        if not module.check_mode:
            response = module.sdk_call(client.ModifyUserHba, change_request(models, p["instance_id"], target))
            task_id = response.TaskId
            if response.ErrorMsg:
                module.fail_json(msg=response.ErrorMsg, task_id=task_id)
            current = describe(module, client, models, p["instance_id"])
        module.exit_json(changed=True, **(diff or {}), rules=current if not module.check_mode else target, task_id=task_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
