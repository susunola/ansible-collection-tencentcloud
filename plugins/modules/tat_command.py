#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tat_command
short_description: Manage Tencent Cloud TAT commands
version_added: "0.14.0"
description: Creates, updates and deletes reusable TencentCloud Automation Tools commands.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  command_id: {description: Existing TAT command ID., type: str}
  name: {description: TAT command name., type: str}
  content: {description: Plain text command script., type: str}
  description: {description: Command description., type: str, default: ''}
  command_type: {description: Command interpreter type., type: str, choices: [SHELL, POWERSHELL, BAT], default: SHELL}
  working_directory: {description: Command working directory., type: str, default: /root}
  timeout: {description: Command timeout in seconds., type: int, default: 60}
  enable_parameters: {description: Enable script parameter placeholders., type: bool, default: false}
  default_parameters: {description: Default placeholder values., type: dict, default: {}}
  username: {description: Operating system user used to execute the command., type: str, default: root}
  output_cos_bucket_url: {description: HTTPS COS bucket URL for command output., type: str}
  output_cos_key_prefix: {description: COS key prefix for command output., type: str}
  tags: {description: Tags assigned when creating the command., type: dict, default: {}}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tat_command:
    name: install-agent
    content: |-
      #!/bin/bash
      curl -fsSL https://example.com/install.sh | bash
    timeout: 300
'''
RETURN = r'''
command: {description: TAT command metadata., type: dict, returned: always}
'''

import base64
import json
import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_tat():
    from tencentcloud.tat.v20201028 import models, tat_client
    return models, tat_client


def _content(value):
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def _parameters(value):
    return json.dumps({str(k): str(v) for k, v in (value or {}).items()}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        item = models.Tag()
        item.Key, item.Value = str(key), str(value)
        result.append(item)
    return result


def build_describe_request(models, command_id=None, name=None, offset=0):
    request = models.DescribeCommandsRequest()
    request.Offset, request.Limit = offset, 100
    if command_id:
        request.CommandIds = [command_id]
    elif name:
        item = models.Filter()
        item.Name, item.Values = "command-name", [name]
        request.Filters = [item]
    return request


def _apply(request, params):
    request.CommandName, request.Content = params["name"], _content(params["content"])
    request.Description, request.CommandType = params["description"], params["command_type"]
    request.WorkingDirectory, request.Timeout = params["working_directory"], params["timeout"]
    request.DefaultParameters = _parameters(params["default_parameters"])
    request.Username = params["username"]
    if params.get("output_cos_bucket_url"):
        request.OutputCOSBucketUrl = params["output_cos_bucket_url"]
    if params.get("output_cos_key_prefix"):
        request.OutputCOSKeyPrefix = params["output_cos_key_prefix"]
    return request


def build_create_request(models, params):
    request = _apply(models.CreateCommandRequest(), params)
    request.EnableParameter = params["enable_parameters"]
    request.Tags = build_tags(models, params["tags"])
    return request


def build_update_request(models, command_id, params):
    request = _apply(models.ModifyCommandRequest(), params)
    request.CommandId = command_id
    return request


def build_delete_request(models, command_id):
    request = models.DeleteCommandRequest()
    request.CommandId = command_id
    return request


def find_command(module, client, models, command_id=None, name=None):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeCommands, build_describe_request(models, command_id, name, offset))
        items = list(response.CommandSet or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if (command_id and value.get("CommandId") == command_id) or (not command_id and value.get("CommandName") == name and value.get("CreatedBy") == "USER"):
                matches.append(value)
        offset += len(items)
        if command_id or not items or offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple user-created TAT commands have the requested name", name=name)
    return matches[0] if matches else None


def _tags(values):
    return {x.get("Key"): x.get("Value") for x in (values or [])}


def _desired(params):
    return {"CommandName": params["name"], "Content": _content(params["content"]), "Description": params["description"], "CommandType": params["command_type"], "WorkingDirectory": params["working_directory"], "Timeout": params["timeout"], "EnableParameter": params["enable_parameters"], "DefaultParameters": _parameters(params["default_parameters"]), "Username": params["username"], "OutputCOSBucketUrl": params["output_cos_bucket_url"], "OutputCOSKeyPrefix": params["output_cos_key_prefix"], "Tags": {str(k): str(v) for k, v in params["tags"].items()}}


def _matches(current, desired):
    return all((_tags(current.get(key)) if key == "Tags" else (current.get(key) or None)) == (value or None) for key, value in desired.items())


def wait_for_command(module, client, models, command_id, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_command(module, client, models, command_id, None)
        if absent and current is None:
            return None
        if not absent and current and _matches(current, desired):
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for TAT command convergence", command=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"type": "str", "choices": ["present", "absent"], "default": "present"}, "command_id": {"type": "str"}, "name": {"type": "str"}, "content": {"type": "str"}, "description": {"type": "str", "default": ""}, "command_type": {"type": "str", "choices": ["SHELL", "POWERSHELL", "BAT"], "default": "SHELL"}, "working_directory": {"type": "str", "default": "/root"}, "timeout": {"type": "int", "default": 60}, "enable_parameters": {"type": "bool", "default": False}, "default_parameters": {"type": "dict", "default": {}}, "username": {"type": "str", "default": "root"}, "output_cos_bucket_url": {"type": "str"}, "output_cos_key_prefix": {"type": "str", "no_log": False}, "tags": {"type": "dict", "default": {}}}, required_one_of=[("command_id", "name")], required_if=[("state", "present", ("name", "content"))], supports_check_mode=True)
    p = module.params
    if p["default_parameters"] and not p["enable_parameters"]:
        module.fail_json(msg="enable_parameters must be true when default_parameters are provided")
    module.require_sdk()
    models, client_module = _load_tat()
    client = module.create_client(client_module.TatClient, "tat.tencentcloudapi.com")
    try:
        current = find_command(module, client, models, p["command_id"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, command=None, msg="TAT command is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), command=current, msg="Would delete TAT command")
            module.sdk_call(client.DeleteCommand, build_delete_request(models, current["CommandId"]))
            wait_for_command(module, client, models, current["CommandId"], absent=True)
            module.exit_json(changed=True, **(diff or {}), command=None, msg="TAT command deleted")
        desired = _desired(p)
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), command=None, msg="Would create TAT command")
            response = module.sdk_call(client.CreateCommand, build_create_request(models, p))
            current = wait_for_command(module, client, models, response.CommandId, desired)
            module.exit_json(changed=True, **(diff or {}), command=current, msg="TAT command created")
        if current.get("EnableParameter") != desired["EnableParameter"]:
            module.fail_json(msg="TAT command enable_parameters cannot be changed; recreate the command")
        if _tags(current.get("Tags")) != desired["Tags"]:
            module.fail_json(msg="TAT command tags cannot be changed by ModifyCommand; recreate the command")
        if _matches(current, desired):
            module.exit_json(changed=False, command=current, msg="TAT command is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), command=current, msg="Would update TAT command")
        module.sdk_call(client.ModifyCommand, build_update_request(models, current["CommandId"], p))
        current = wait_for_command(module, client, models, current["CommandId"], desired)
        module.exit_json(changed=True, **(diff or {}), command=current, msg="TAT command updated")
    except Exception as exc:
        module.fail_json(msg="Tencent Cloud API request failed", error=str(exc), error_code=getattr(exc, "get_code", lambda: None)(), request_id=getattr(exc, "get_request_id", lambda: None)())


def main():
    run_module()


if __name__ == "__main__":
    main()
