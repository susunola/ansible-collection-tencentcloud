#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_governance_alias
short_description: Manage a Tencent Cloud TSE governance service alias
version_added: "0.14.0"
description: Creates, retargets, updates and deletes a namespace-scoped governance service alias.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  instance_id:
    description:
      - TSE engine instance ID.
    type: str
    required: true
  alias:
    description:
      - Service alias.
    type: str
    required: true
  alias_namespace:
    description:
      - Namespace containing the alias.
    type: str
    required: true
  service:
    description:
      - Target service name.
    type: str
  namespace:
    description:
      - Target service namespace.
    type: str
  comment:
    description:
      - Alias description.
    type: str
  waiter_delay:
    description:
      - Reconciliation polling interval.
    type: int
    default: 2
  waiter_timeout:
    description:
      - Reconciliation timeout.
    type: int
    default: 60

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
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_governance_alias:
    instance_id: ins-xxxxxxxx
    alias_namespace: shared
    alias: orders-api
    namespace: production
    service: orders
"""
RETURN = r"""alias_info: {description: Effective governance alias metadata., type: dict, returned: always}"""
import json
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def describe_request(models, p, offset=0):
    r = models.DescribeGovernanceAliasesRequest()
    r.InstanceId, r.Alias, r.AliasNamespace, r.Offset, r.Limit = p["instance_id"], p["alias"], p["alias_namespace"], offset, 100
    return r


def desired(p, current=None):
    value = {"Alias": p["alias"], "AliasNamespace": p["alias_namespace"]}
    for source, target in (("service", "Service"), ("namespace", "Namespace"), ("comment", "Comment")):
        selected = p.get(source) if p.get(source) is not None else (current or {}).get(target)
        if selected is not None:
            value[target] = selected
    return value


def write_request(cls, models, p, value):
    if cls in (models.CreateGovernanceAliasRequest, models.ModifyGovernanceAliasRequest):
        r = cls()
        r.from_json_string(json.dumps({"InstanceId": p["instance_id"], **value}))
        return r
    item = models.GovernanceAlias()
    item.from_json_string(json.dumps(value))
    r = cls()
    r.InstanceId, r.GovernanceAliases = p["instance_id"], [item]
    return r


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeGovernanceAliases, describe_request(models, p, offset))
        page = response.Content or []
        for item in page:
            value = item._serialize(allow_none=True)
            if value.get("Alias") == p["alias"] and value.get("AliasNamespace") == p["alias_namespace"]:
                matches.append(value)
        offset += len(page)
        if offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE governance aliases matched", alias=p["alias"], alias_namespace=p["alias_namespace"])
    return matches[0] if matches else None


def comparable(value, target):
    return {key: value.get(key) for key in target}


def wait(module, client, models, p, target=None, absent=False):
    deadline = time.time() + p["waiter_timeout"]
    while True:
        value = find(module, client, models, p)
        if absent and value is None:
            return None
        if not absent and value is not None and comparable(value, target) == target:
            return value
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for TSE governance alias convergence", alias_info=value)
        time.sleep(p["waiter_delay"])


def require_success(module, response, operation):
    if getattr(response, "Result", None) is not True:
        module.fail_json(msg="TSE governance alias operation returned an unsuccessful result", operation=operation)


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "instance_id": {"required": True},
        "alias": {"required": True},
        "alias_namespace": {"required": True},
        "service": {},
        "namespace": {},
        "comment": {},
        "waiter_delay": {"type": "int", "default": 2},
        "waiter_timeout": {"type": "int", "default": 60},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, alias_info=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                require_success(
                    module,
                    module.sdk_call(client.DeleteGovernanceAliases, write_request(models.DeleteGovernanceAliasesRequest, models, p, desired(p, current))),
                    "DeleteGovernanceAliases",
                )
                wait(module, client, models, p, absent=True)
            module.exit_json(changed=True, **(diff or {}), alias_info=None)
        target = desired(p, current)
        if not current:
            missing = [key for key in ("service", "namespace") if p.get(key) is None]
            if missing:
                module.fail_json(msg="creation parameters are required for a TSE governance alias", missing=missing)
        if current and comparable(current, target) == target:
            module.exit_json(changed=False, alias_info=current)
        diff = maybe_diff(module, comparable(current, target) if current else None, target)
        if not module.check_mode:
            cls = models.ModifyGovernanceAliasRequest if current else models.CreateGovernanceAliasRequest
            api = client.ModifyGovernanceAlias if current else client.CreateGovernanceAlias
            require_success(
                module, module.sdk_call(api, write_request(cls, models, p, target)), "ModifyGovernanceAlias" if current else "CreateGovernanceAlias"
            )
            current = wait(module, client, models, p, target)
        module.exit_json(changed=True, **(diff or {}), alias_info=current if not module.check_mode else target)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
