#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_config_file_group
short_description: Manage a Tencent Cloud TSE configuration file group
version_added: "0.14.0"
description: Creates, updates and deletes a namespace-scoped configuration group with exact operator sets.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: TSE engine instance ID.}
  namespace: {type: str, required: true, description: Configuration namespace.}
  name: {type: str, required: true, description: Configuration group name.}
  comment: {type: str, description: Group description.}
  department: {type: str, description: Owning department.}
  business: {type: str, description: Owning business.}
  user_ids: {type: list, elements: str, description: Exact operator user IDs.}
  group_ids: {type: list, elements: str, description: Exact operator group IDs.}
  tags: {type: list, elements: dict, description: SDK ConfigFileGroupTag entries.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_config_file_group:
    instance_id: ins-xxxxxxxx
    namespace: production
    name: application
"""
RETURN = r"""group: {description: Effective configuration group metadata., type: dict, returned: always}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def describe_request(models, p):
    r = models.DescribeConfigFileGroupsRequest()
    r.InstanceId, r.Namespace, r.Group, r.Offset, r.Limit = p["instance_id"], p["namespace"], p["name"], 0, 100
    return r


def _model(models, value):
    x = models.ConfigFileGroup()
    x.from_json_string(json.dumps(value))
    return x


def request(cls, models, p, value):
    r = cls()
    r.InstanceId = p["instance_id"]
    r.ConfigFileGroup = _model(models, value)
    return r


def delete_request(models, p):
    r = models.DeleteConfigFileGroupRequest()
    r.InstanceId, r.Namespace, r.Group = p["instance_id"], p["namespace"], p["name"]
    return r


def find(module, client, models, p):
    values = module.sdk_call(client.DescribeConfigFileGroups, describe_request(models, p)).ConfigFileGroups or []
    matches = [x._serialize(allow_none=True) for x in values if x.Name == p["name"] and x.Namespace == p["namespace"]]
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE configuration groups matched", name=p["name"], namespace=p["namespace"])
    return matches[0] if matches else None


def desired(p):
    mapping = {
        "comment": "Comment",
        "department": "Department",
        "business": "Business",
        "user_ids": "UserIds",
        "group_ids": "GroupIds",
        "tags": "ConfigFileGroupTags",
    }
    value = {"Name": p["name"], "Namespace": p["namespace"]}
    for source, target in mapping.items():
        if p.get(source) is not None:
            value[target] = sorted(p[source]) if source in ("user_ids", "group_ids") else p[source]
    return value


def comparable(value, target):
    result = {key: value.get(key) for key in target}
    for key in ("UserIds", "GroupIds"):
        if key in result:
            result[key] = sorted(result[key] or [])
    return result


def mutation(current, target):
    value = dict(target)
    for key, remove_key in (("UserIds", "RemoveUserIds"), ("GroupIds", "RemoveGroupIds")):
        if key in target:
            before = set((current or {}).get(key) or [])
            after = set(target[key])
            value[key] = sorted(after - before)
            value[remove_key] = sorted(before - after)
    return value


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "instance_id": {"required": True},
            "namespace": {"required": True},
            "name": {"required": True},
            "comment": {},
            "department": {},
            "business": {},
            "user_ids": {"type": "list", "elements": "str"},
            "group_ids": {"type": "list", "elements": "str"},
            "tags": {"type": "list", "elements": "dict"},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, group=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteConfigFileGroup, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), group=None)
        target = desired(p)
        if current and comparable(current, target) == target:
            module.exit_json(changed=False, group=current)
        diff = maybe_diff(module, comparable(current or {}, target) if current else None, target)
        if not module.check_mode:
            payload = mutation(current, target)
            api = client.ModifyConfigFileGroup if current else client.CreateConfigFileGroup
            cls = models.ModifyConfigFileGroupRequest if current else models.CreateConfigFileGroupRequest
            module.sdk_call(api, request(cls, models, p, payload))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), group=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
