#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cls_config_machine_group_binding
short_description: Bind CLS collection configurations to machine groups
version_added: "0.14.0"
description: Idempotently applies or removes a CLS collection configuration on a machine group.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  config_id: {type: str, required: true, description: CLS configuration ID.}
  group_id: {type: str, required: true, description: CLS machine group ID.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cls_config_machine_group_binding:
    config_id: config-xxxxxxxx
    group_id: group-xxxxxxxx
"""
RETURN = r"""binding: {description: Normalized CLS config binding., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cls.v20201016 import cls_client, models

    return models, cls_client


def build_describe(models, group_id):
    request = models.DescribeMachineGroupConfigsRequest()
    request.GroupId = group_id
    return request


def build_apply(models, config_id, group_id):
    request = models.ApplyConfigToMachineGroupRequest()
    request.ConfigId, request.GroupId = config_id, group_id
    return request


def build_remove(models, config_id, group_id):
    request = models.DeleteConfigFromMachineGroupRequest()
    request.ConfigId, request.GroupId = config_id, group_id
    return request


def find(module, client, models, config_id, group_id):
    response = module.sdk_call(client.DescribeMachineGroupConfigs, build_describe(models, group_id))
    for item in list(response.Configs or []):
        if item.ConfigId == config_id:
            return {"ConfigId": config_id, "GroupId": group_id}
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "config_id": {"required": True}, "group_id": {"required": True}},
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.ClsClient, "cls.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["config_id"], p["group_id"])
        target = {"ConfigId": p["config_id"], "GroupId": p["group_id"]}
        present = p["state"] == "present"
        if (present and current) or (not present and not current):
            module.exit_json(changed=False, binding=current)
        diff = maybe_diff(module, current, target if present else None)
        if not module.check_mode:
            operation = client.ApplyConfigToMachineGroup if present else client.DeleteConfigFromMachineGroup
            request = build_apply(models, p["config_id"], p["group_id"]) if present else build_remove(models, p["config_id"], p["group_id"])
            module.sdk_call(operation, request)
        module.exit_json(changed=True, **(diff or {}), binding=target if present else None)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
