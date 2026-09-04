#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cls_config
short_description: Manage Tencent Cloud CLS collection configurations
version_added: "0.14.0"
description: Creates, updates and deletes LogListener collection configurations.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  config_id: {type: str, description: Existing configuration ID.}
  name: {type: str, description: Configuration name.}
  topic_id: {type: str, description: Destination CLS topic ID.}
  path: {type: str, default: '', description: File collection path.}
  log_type: {type: str, default: minimalist_log, description: CLS extraction mode.}
  extract_rule: {type: dict, description: SDK-compatible extraction rule.}
  exclude_paths: {type: list, elements: dict, default: [], description: SDK-compatible excluded path definitions.}
  user_define_rule: {type: str, description: Serialized custom collection rule.}
  advanced_config: {type: str, description: Serialized advanced collection configuration.}
  input_type: {type: str, description: Log input type.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cls_config:
    name: nginx-access
    topic_id: topic-xxxxxxxx
    path: /var/log/nginx/access.log
    log_type: minimalist_log
"""
RETURN = r"""config: {description: CLS collection configuration metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cls.v20201016 import cls_client, models

    return models, cls_client


def build_describe(models, name=None):
    request = models.DescribeConfigsRequest()
    request.Offset, request.Limit = 0, 100
    if name:
        item = models.Filter()
        item.Key, item.Values = "configName", [name]
        request.Filters = [item]
    return request


def _model(models, name, value):
    item = getattr(models, name)()
    item._deserialize(value)
    return item


def apply(request, models, p, config_id=None):
    if config_id:
        request.ConfigId = config_id
    request.Name, request.Output, request.Path, request.LogType = p["name"], p["topic_id"], p["path"], p["log_type"]
    if p.get("extract_rule") is not None:
        request.ExtractRule = _model(models, "ExtractRuleInfo", p["extract_rule"])
    request.ExcludePaths = [_model(models, "ExcludePathInfo", x) for x in p["exclude_paths"]]
    request.UserDefineRule, request.AdvancedConfig, request.InputType = p.get("user_define_rule"), p.get("advanced_config"), p.get("input_type")
    return request


def build_create(models, p):
    return apply(models.CreateConfigRequest(), models, p)


def build_update(models, p, config_id):
    return apply(models.ModifyConfigRequest(), models, p, config_id)


def build_delete(models, config_id):
    request = models.DeleteConfigRequest()
    request.ConfigId = config_id
    return request


def find(module, client, models, config_id, name):
    response = module.sdk_call(client.DescribeConfigs, build_describe(models, name))
    matches = [
        x._serialize(allow_none=True) for x in list(response.Configs or []) if (config_id and x.ConfigId == config_id) or (not config_id and x.Name == name)
    ]
    if len(matches) > 1:
        module.fail_json(msg="Multiple CLS configs have the requested name", name=name)
    return matches[0] if matches else None


def desired(p):
    return {
        "Name": p["name"],
        "Output": p["topic_id"],
        "Path": p["path"],
        "LogType": p["log_type"],
        "ExtractRule": p.get("extract_rule"),
        "ExcludePaths": p["exclude_paths"],
        "UserDefineRule": p.get("user_define_rule"),
        "AdvancedConfig": p.get("advanced_config"),
        "InputType": p.get("input_type"),
    }


def comparable(v):
    return {k: v.get(k) for k in ("Name", "Output", "Path", "LogType", "ExtractRule", "ExcludePaths", "UserDefineRule", "AdvancedConfig", "InputType")}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "config_id": {},
            "name": {},
            "topic_id": {},
            "path": {"default": ""},
            "log_type": {"default": "minimalist_log"},
            "extract_rule": {"type": "dict"},
            "exclude_paths": {"type": "list", "elements": "dict", "default": []},
            "user_define_rule": {},
            "advanced_config": {},
            "input_type": {},
        },
        required_one_of=[("config_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and (not p["name"] or not p["topic_id"]):
        module.fail_json(msg="name and topic_id are required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.ClsClient, "cls.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["config_id"], p["name"])
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, config=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteConfig, build_delete(models, current["ConfigId"]))
            module.exit_json(changed=True, **(diff or {}), config=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, config=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                module.sdk_call(client.ModifyConfig, build_update(models, p, current["ConfigId"]))
                config_id = current["ConfigId"]
            else:
                config_id = module.sdk_call(client.CreateConfig, build_create(models, p)).ConfigId
            current = find(module, client, models, config_id, None)
        module.exit_json(changed=True, **(diff or {}), config=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
