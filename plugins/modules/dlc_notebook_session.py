#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_notebook_session
short_description: Manage Tencent Cloud DLC Notebook sessions
version_added: "0.14.0"
description:
  - Creates, discovers, waits for and deletes DLC Notebook sessions.
  - Session creation settings are immutable; changing them requires explicitly authorized replacement.
  - Historical terminal sessions are ignored during name discovery, while C(session_id) remains a strong identity.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired session lifecycle state.}
  session_id: {type: str, description: Exact session ID; recommended for deletion and strong identity.}
  name: {type: str, description: Exact session name; required for creation and usable for active-session discovery.}
  kind: {type: str, choices: [spark, pyspark, sparkr, sql], description: Session language kind required for creation.}
  data_engine_name: {type: str, description: Exact DLC Spark engine name required for creation and usable to scope discovery.}
  dependent_files: {type: list, elements: str, description: Complete creation-time dependent-file path list.}
  dependent_jars: {type: list, elements: str, description: Complete creation-time dependent-JAR path list.}
  dependent_python: {type: list, elements: str, description: Complete creation-time Python dependency path list.}
  archives: {type: list, elements: str, description: Complete creation-time PySpark environment archive list.}
  driver_size: {type: str, choices: [small, medium, large, xlarge], description: Creation-time driver size.}
  executor_size: {type: str, choices: [small, medium, large, xlarge], description: Creation-time executor size.}
  executor_numbers: {type: int, description: Creation-time initial executor count.}
  executor_max_numbers: {type: int, description: Creation-time maximum executor count.}
  arguments:
    type: list
    elements: dict
    description: Complete creation-time session argument set.
    options:
      key: {type: str, required: true, description: Argument key.}
      value: {type: str, required: true, description: Argument value.}
  proxy_user: {type: str, description: Creation-time proxy user.}
  timeout: {type: int, description: Creation-time session timeout in seconds.}
  allow_replace: {type: bool, default: false, description: Explicitly authorize deleting and recreating a session whose immutable settings drift.}
  allow_delete: {type: bool, default: false, description: Explicitly authorize session deletion.}
  wait: {type: bool, default: true, description: Wait until a created session is usable or a deleted session is terminal.}
  waiter_delay: {type: int, default: 5, description: Seconds between polls.}
  waiter_timeout: {type: int, default: 900, description: Overall lifecycle timeout.}
  retries: {type: int, default: 5, description: Retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_notebook_session:
    name: analyst-pyspark
    kind: pyspark
    data_engine_name: production-spark
    driver_size: medium
    executor_size: medium
    executor_numbers: 2
    timeout: 7200

- susunola.tencentcloud.dlc_notebook_session:
    session_id: d3018ad4-xxxxxxxx
    state: absent
    allow_delete: true
"""
RETURN = r"""
session: {description: Effective Notebook session metadata., type: dict, returned: always}
session_id: {description: DLC Notebook session ID., type: str, returned: when present}
"""

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


ACTIVE = {"not_started", "starting", "idle", "busy", "shutting_down"}
FAILED = {"error", "dead", "killed"}
TERMINAL = FAILED | {"success"}
FIELDS = {
    "kind": "Kind",
    "data_engine_name": "DataEngineName",
    "dependent_files": "ProgramDependentFiles",
    "dependent_jars": "ProgramDependentJars",
    "dependent_python": "ProgramDependentPython",
    "archives": "ProgramArchives",
    "driver_size": "DriverSize",
    "executor_size": "ExecutorSize",
    "executor_numbers": "ExecutorNumbers",
    "executor_max_numbers": "ExecutorMaxNumbers",
    "proxy_user": "ProxyUser",
    "timeout": "TimeoutInSecond",
}
LIST_FIELDS = {"dependent_files", "dependent_jars", "dependent_python", "archives"}


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def _pairs(values):
    result = [{"Key": x.get("Key", x.get("key")), "Value": x.get("Value", x.get("value"))} for x in values or []]
    return sorted(result, key=lambda x: (x["Key"], x["Value"]))


def normalize(value):
    if value is None:
        return None
    source = value if isinstance(value, dict) else value._serialize(allow_none=True)
    result = dict(source)
    result["Arguments"] = _pairs(source.get("Arguments"))
    for key in ("ProgramDependentFiles", "ProgramDependentJars", "ProgramDependentPython", "ProgramArchives"):
        result[key] = sorted(source.get(key) or [])
    return result


def describe_request(models, session_id):
    request = models.DescribeNotebookSessionRequest()
    request.SessionId = session_id
    return request


def read_id(module, client, models, session_id):
    try:
        response = module.sdk_call(client.DescribeNotebookSession, describe_request(models, session_id))
    except Exception as exc:
        if is_not_found(exc):
            return None
        raise
    return normalize(response.Session)


def list_request(models, p, offset=0):
    request = models.DescribeNotebookSessionsRequest()
    request.Offset, request.Limit = offset, 100
    if p.get("data_engine_name"):
        request.DataEngineName = p["data_engine_name"]
    item = models.Filter()
    item.Name, item.Values = "notebook-keyword", [p["name"]]
    request.Filters = [item]
    return request


def find(module, client, models, p):
    if p.get("session_id"):
        return read_id(module, client, models, p["session_id"])
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeNotebookSessions, list_request(models, p, offset))
        page = response.Sessions or []
        for item in page:
            if item.Name == p["name"] and item.State in ACTIVE and (not p.get("data_engine_name") or item.DataEngineName == p["data_engine_name"]):
                value = read_id(module, client, models, item.SessionId)
                if value:
                    matches.append(value)
        offset += len(page)
        if not page or offset >= int(response.TotalElements or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple active DLC Notebook sessions matched; specify session_id", name=p["name"])
    return matches[0] if matches else None


def create_request(models, p):
    payload = {"Name": p["name"]}
    for source, target in FIELDS.items():
        if p.get(source) is not None:
            payload[target] = sorted(p[source]) if source in LIST_FIELDS else p[source]
    if p.get("arguments") is not None:
        payload["Arguments"] = _pairs(p["arguments"])
    request = models.CreateNotebookSessionRequest()
    request.from_json_string(json.dumps(payload))
    return request


def delete_request(models, session_id):
    request = models.DeleteNotebookSessionRequest()
    request.SessionId = session_id
    return request


def desired(p, current=None):
    result = dict(current or {})
    result["Name"] = p.get("name") or result.get("Name")
    for source, target in FIELDS.items():
        if p.get(source) is not None:
            result[target] = sorted(p[source]) if source in LIST_FIELDS else p[source]
    if p.get("arguments") is not None:
        result["Arguments"] = _pairs(p["arguments"])
    return result


def immutable_drift(p, current):
    target, changes = desired(p, current), {}
    if p.get("name") is not None and current.get("Name") != p["name"]:
        changes["Name"] = (current.get("Name"), p["name"])
    for source, remote in FIELDS.items():
        if p.get(source) is not None and current.get(remote) != target.get(remote):
            changes[remote] = (current.get(remote), target.get(remote))
    if p.get("arguments") is not None and _pairs(current.get("Arguments")) != target["Arguments"]:
        changes["Arguments"] = (_pairs(current.get("Arguments")), target["Arguments"])
    return changes


def wait_session(module, client, models, p, session_id, present):
    def poll():
        current = read_id(module, client, models, session_id)
        if not present:
            return "absent" if current is None or current.get("State") in TERMINAL else "pending"
        if current is None:
            return "absent"
        state = current.get("State")
        if state in FAILED:
            module.fail_json(msg="DLC Notebook session entered a failed state", session=current)
        return "ready" if state in ("idle", "busy") else "pending"

    wait_for_state(module, poll, ["ready" if present else "absent"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    pair = {"key": {"required": True}, "value": {"required": True}}
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "session_id": {},
        "name": {},
        "kind": {"choices": ["spark", "pyspark", "sparkr", "sql"]},
        "data_engine_name": {},
        "dependent_files": {"type": "list", "elements": "str"},
        "dependent_jars": {"type": "list", "elements": "str"},
        "dependent_python": {"type": "list", "elements": "str"},
        "archives": {"type": "list", "elements": "str"},
        "driver_size": {"choices": ["small", "medium", "large", "xlarge"]},
        "executor_size": {"choices": ["small", "medium", "large", "xlarge"]},
        "executor_numbers": {"type": "int"},
        "executor_max_numbers": {"type": "int"},
        "arguments": {"type": "list", "elements": "dict", "options": pair},
        "proxy_user": {},
        "timeout": {"type": "int"},
        "allow_replace": {"type": "bool", "default": False},
        "allow_delete": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 5},
        "waiter_timeout": {"type": "int", "default": 900},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("session_id", "name")], supports_check_mode=True)
    p = module.params
    if p.get("executor_numbers") is not None and p.get("executor_max_numbers") is not None and p["executor_numbers"] > p["executor_max_numbers"]:
        module.fail_json(msg="executor_numbers must not exceed executor_max_numbers")
    if p.get("arguments") is not None and len({x["key"] for x in p["arguments"]}) != len(p["arguments"]):
        module.fail_json(msg="arguments contains duplicate keys")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current or current.get("State") in TERMINAL:
                module.exit_json(changed=False, session=None, session_id=None)
            if not p["allow_delete"]:
                module.fail_json(msg="set allow_delete=true to authorize deleting the DLC Notebook session", session=current)
            diff_value = maybe_diff(module, current, None)
            session_id = current["SessionId"]
            if not module.check_mode:
                module.sdk_call(client.DeleteNotebookSession, delete_request(models, session_id))
                if p["wait"]:
                    wait_session(module, client, models, p, session_id, False)
            module.exit_json(changed=True, **(diff_value or {}), session=None, session_id=None)
        if current and current.get("State") in TERMINAL:
            if p.get("session_id"):
                module.fail_json(
                    msg="the specified DLC Notebook session is terminal and cannot be restarted; omit session_id to create a new named session", session=current
                )
            current = None
        if not current:
            missing = [key for key in ("name", "kind", "data_engine_name") if not p.get(key)]
            if missing:
                module.fail_json(msg="creation parameters are required for a DLC Notebook session", missing=missing)
            target = desired(p)
            diff_value = maybe_diff(module, None, target)
            session_id = None
            if not module.check_mode:
                session_id = module.sdk_call(client.CreateNotebookSession, create_request(models, p)).SessionId
                if p["wait"]:
                    wait_session(module, client, models, p, session_id, True)
                current = read_id(module, client, models, session_id)
            module.exit_json(changed=True, **(diff_value or {}), session=current if not module.check_mode else target, session_id=session_id)
        if current.get("State") == "shutting_down":
            module.fail_json(msg="DLC Notebook session is shutting down; wait for it to become terminal before recreating", session=current)
        changes = immutable_drift(p, current)
        if not changes:
            module.exit_json(changed=False, session=current, session_id=current.get("SessionId"))
        if not p["allow_replace"]:
            module.fail_json(
                msg="DLC Notebook session settings are immutable; set allow_replace=true to authorize replacement", immutable_drift=changes, session=current
            )
        if not p.get("name"):
            module.fail_json(msg="name is required when replacing a DLC Notebook session")
        target = desired(p)
        diff_value = maybe_diff(module, current, target)
        old_id = current["SessionId"]
        if not module.check_mode:
            module.sdk_call(client.DeleteNotebookSession, delete_request(models, old_id))
            if p["wait"]:
                wait_session(module, client, models, p, old_id, False)
            session_id = module.sdk_call(client.CreateNotebookSession, create_request(models, p)).SessionId
            if p["wait"]:
                wait_session(module, client, models, p, session_id, True)
            current = read_id(module, client, models, session_id)
        else:
            session_id = None
        module.exit_json(changed=True, **(diff_value or {}), session=current if not module.check_mode else target, session_id=session_id)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
