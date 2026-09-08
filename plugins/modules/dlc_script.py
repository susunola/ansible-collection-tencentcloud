#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_script
short_description: Manage Tencent Cloud DLC saved SQL scripts
version_added: "0.14.0"
description:
  - Creates and deletes saved DLC SQL scripts using exact-name discovery.
  - Since DLC has no script update API, content drift is blocked unless explicit replacement is authorized.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired lifecycle state.}
  name: {type: str, required: true, description: Exact saved-script name and identity.}
  sql_statement: {type: str, description: Plain-text SQL content; required on creation.}
  description: {type: str, description: Script description, at most 50 characters.}
  database_name: {type: str, description: Default database name.}
  allow_replace: {type: bool, default: false, description: Explicitly authorize delete-and-recreate when immutable script content drifts.}
  allow_delete: {type: bool, default: false, description: Explicitly authorize script deletion.}
  wait: {type: bool, default: true, description: Wait for lifecycle and field convergence.}
  waiter_delay: {type: int, default: 3, description: Seconds between polls.}
  waiter_timeout: {type: int, default: 180, description: Overall convergence timeout.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_script:
    name: daily-sales
    database_name: analytics
    description: Daily sales aggregation
    sql_statement: SELECT sale_date, SUM(amount) FROM sales GROUP BY sale_date

- susunola.tencentcloud.dlc_script:
    name: daily-sales
    state: absent
    allow_delete: true
"""
RETURN = r"""
script:
  description: Effective saved-script metadata and plain-text SQL.
  type: dict
  returned: always
script_id:
  description: DLC script ID.
  type: str
  returned: when present
"""

import base64
import binascii
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def decode_sql(value):
    if value is None:
        return None
    try:
        return base64.b64decode(value, validate=True).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return value


def list_request(models, offset=0):
    request = models.DescribeScriptsRequest()
    request.Offset, request.Limit = offset, 100
    return request


def normalize(value):
    result = dict(value or {})
    if "SQLStatement" in result:
        result["SQLStatement"] = decode_sql(result["SQLStatement"])
    return result


def find(module, client, models, name):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeScripts, list_request(models, offset))
        items = response.Scripts or []
        matches.extend(x._serialize(allow_none=True) for x in items if x.ScriptName == name)
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple DLC saved scripts matched the exact name", name=name)
    return normalize(matches[0]) if matches else None


def desired(p, current=None):
    result = dict(current or {})
    result["ScriptName"] = p["name"]
    for source, target in (("sql_statement", "SQLStatement"), ("description", "ScriptDesc"), ("database_name", "DatabaseName")):
        if p.get(source) is not None:
            result[target] = p[source]
    return result


def drift(p, current):
    target, changes = desired(p, current), {}
    for source, key in (("sql_statement", "SQLStatement"), ("description", "ScriptDesc"), ("database_name", "DatabaseName")):
        if p.get(source) is not None and current.get(key) != target.get(key):
            changes[key] = (current.get(key), target.get(key))
    return changes


def create_request(models, p):
    request = models.CreateScriptRequest()
    request.ScriptName = p["name"]
    request.SQLStatement = base64.b64encode(p["sql_statement"].encode("utf-8")).decode("ascii")
    if p.get("description") is not None:
        request.ScriptDesc = p["description"]
    if p.get("database_name") is not None:
        request.DatabaseName = p["database_name"]
    return request


def delete_request(models, script_id):
    request = models.DeleteScriptRequest()
    request.ScriptIds = [script_id]
    return request


def wait_script(module, client, models, p, absent=False, expected=None):
    def poll():
        current = find(module, client, models, p["name"])
        if absent:
            return "absent" if current is None else "pending"
        if current is None:
            return "absent"
        if expected and any(current.get(k) != v for k, v in expected.items()):
            return "pending"
        return "ready"

    wait_for_state(module, poll, ["absent" if absent else "ready"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "name": {"required": True},
        "sql_statement": {},
        "description": {},
        "database_name": {},
        "allow_replace": {"type": "bool", "default": False},
        "allow_delete": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 3},
        "waiter_timeout": {"type": "int", "default": 180},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if len(p["name"]) > 255:
        module.fail_json(msg="name must not exceed 255 characters")
    if p.get("description") is not None and len(p["description"]) > 50:
        module.fail_json(msg="description must not exceed 50 characters")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["name"])
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, script=None, script_id=None)
            if not p["allow_delete"]:
                module.fail_json(msg="set allow_delete=true to authorize deleting the DLC saved script", script=current)
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteScript, delete_request(models, current["ScriptId"]))
                if p["wait"]:
                    wait_script(module, client, models, p, absent=True)
            module.exit_json(changed=True, **(diff_value or {}), script=None, script_id=None)
        if not current:
            if p.get("sql_statement") is None:
                module.fail_json(msg="sql_statement is required when creating a DLC saved script")
            after, diff_value = desired(p), maybe_diff(module, None, desired(p))
            if not module.check_mode:
                module.sdk_call(client.CreateScript, create_request(models, p))
                if p["wait"]:
                    wait_script(module, client, models, p, expected={k: v for k, v in after.items() if k != "ScriptName"})
                current = find(module, client, models, p["name"])
            module.exit_json(changed=True, **(diff_value or {}), script=current if not module.check_mode else after, script_id=(current or {}).get("ScriptId"))
        changes = drift(p, current)
        if not changes:
            module.exit_json(changed=False, script=current, script_id=current.get("ScriptId"))
        if not p["allow_replace"]:
            module.fail_json(
                msg="DLC does not support updating saved scripts; set allow_replace=true to authorize replacement", script=current, changes=changes
            )
        if p.get("sql_statement") is None:
            module.fail_json(msg="sql_statement is required when replacing a DLC saved script")
        after, diff_value = desired(p, current), maybe_diff(module, current, desired(p, current))
        if not module.check_mode:
            module.sdk_call(client.DeleteScript, delete_request(models, current["ScriptId"]))
            if p["wait"]:
                wait_script(module, client, models, p, absent=True)
            module.sdk_call(client.CreateScript, create_request(models, p))
            if p["wait"]:
                wait_script(module, client, models, p, expected={k: v for k, v in after.items() if k not in ("ScriptName", "ScriptId", "UpdateTime")})
            current = find(module, client, models, p["name"])
        module.exit_json(changed=True, **(diff_value or {}), script=current if not module.check_mode else after, script_id=(current or {}).get("ScriptId"))
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
