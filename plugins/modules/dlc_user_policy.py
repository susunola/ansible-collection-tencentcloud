#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: dlc_user_policy
short_description: Manage Tencent Cloud Data Lake Compute user policies
version_added: "0.14.0"
description:
  - Exactly reconciles writable DLC authorization policies directly attached to a user.
  - Ignores server metadata while preferring policy IDs for precise detach operations.
options:
  user_id: {type: str, required: true, description: DLC user ID.}
  account_source: {type: str, choices: [TencentAccount, EntraAccount], default: TencentAccount, description: User source for policy and query APIs.}
  policies: {type: list, elements: dict, required: true, description: Exact desired SDK Policy list.}
  allow_empty: {type: bool, default: false, description: Explicitly authorize removing every directly attached policy.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_user_policy:
    user_id: '100012345678'
    policies:
      - {Catalog: DataLakeCatalog, Database: sales, Table: orders, Operation: SELECT, PolicyType: TABLE}
"""
RETURN = r"""policies: {description: Effective normalized direct policy set., type: list, elements: dict, returned: always}
added: {description: Policies attached by this run., type: list, elements: dict, returned: always}
removed: {description: Policies detached by this run., type: list, elements: dict, returned: always}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state

FIELDS = ("Database", "Catalog", "Table", "Operation", "PolicyType", "Function", "View", "Column", "DataEngine", "ReAuth", "EngineGeneration", "Model")
DEFAULTS = {
    "Database": "",
    "Catalog": "DataLakeCatalog",
    "Table": "",
    "Operation": "ALL",
    "PolicyType": "ADMIN",
    "Function": "",
    "View": "",
    "Column": "",
    "DataEngine": "",
    "ReAuth": False,
    "EngineGeneration": "",
    "Model": "",
}


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def normalize_policy(value):
    return {key: (bool(value.get(key)) if key == "ReAuth" else value.get(key) or DEFAULTS[key]) for key in FIELDS}


def normalize_policies(values):
    result = [normalize_policy(value) for value in values or []]
    keys = [json.dumps(value, sort_keys=True, separators=(",", ":")) for value in result]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate DLC user policies are not allowed")
    return [value for _, value in sorted(zip(keys, result), key=lambda pair: pair[0])]


def describe_request(models, user_id, account_source, offset=0):
    request = models.DescribeUsersRequest()
    request.UserId, request.AccountType = user_id, account_source
    request.Offset, request.Limit = offset, 100
    return request


def current_user(module, client, models, user_id, account_source):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeUsers, describe_request(models, user_id, account_source, offset))
        page = response.UserSet or []
        matches.extend(x._serialize(allow_none=True) for x in page if x.UserId == user_id)
        offset += len(page)
        if not page or offset >= int(response.TotalCount or 0):
            break
    if not matches:
        module.fail_json(msg="DLC user not found", user_id=user_id)
    if len(matches) > 1:
        module.fail_json(msg="Multiple DLC users returned for exact ID", user_id=user_id)
    return matches[0]


def policy_models(models, values):
    result = []
    for value in values:
        item = models.Policy()
        item.from_json_string(json.dumps(value))
        result.append(item)
    return result


def attach_request(models, user_id, account_source, values):
    request = models.AttachUserPolicyRequest()
    request.UserId, request.AccountType = user_id, account_source
    request.PolicySet = policy_models(models, values)
    return request


def detach_request(models, user_id, account_source, values, policy_ids=None):
    request = models.DetachUserPolicyRequest()
    request.UserId, request.AccountType = user_id, account_source
    if policy_ids and len(policy_ids) == len(values):
        request.PolicyIds = policy_ids
    else:
        request.PolicySet = policy_models(models, values)
    return request


def delta(current, target):
    current_map = {json.dumps(value, sort_keys=True, separators=(",", ":")): value for value in normalize_policies(current)}
    target_map = {json.dumps(value, sort_keys=True, separators=(",", ":")): value for value in normalize_policies(target)}
    return [target_map[key] for key in sorted(set(target_map) - set(current_map))], [current_map[key] for key in sorted(set(current_map) - set(target_map))]


def run_module():
    spec = {
        "user_id": {"required": True},
        "account_source": {"choices": ["TencentAccount", "EntraAccount"], "default": "TencentAccount"},
        "policies": {"type": "list", "elements": "dict", "required": True},
        "allow_empty": {"type": "bool", "default": False},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        user = current_user(module, client, models, p["user_id"], p["account_source"])
        if user.get("UserType") == "ADMIN" and p["policies"]:
            module.fail_json(msg="ADMIN DLC users cannot have direct policies", user_id=p["user_id"])
        raw_current = user.get("PolicySet") or []
        current = normalize_policies(raw_current)
        target = normalize_policies(p["policies"])
        if not target and not p["allow_empty"]:
            module.fail_json(msg="set allow_empty=true to authorize removing every direct DLC user policy")
        added, removed = delta(raw_current, target)
        if not added and not removed:
            module.exit_json(changed=False, policies=current, added=[], removed=[])
        diff_value = maybe_diff(module, current, target)
        if not module.check_mode:
            if added:
                module.sdk_call(client.AttachUserPolicy, attach_request(models, p["user_id"], p["account_source"], added))
            if removed:
                removed_keys = {json.dumps(value, sort_keys=True, separators=(",", ":")) for value in removed}
                ids = [
                    str(value.get("PolicyId"))
                    for value in raw_current
                    if json.dumps(normalize_policy(value), sort_keys=True, separators=(",", ":")) in removed_keys and value.get("PolicyId")
                ]
                module.sdk_call(client.DetachUserPolicy, detach_request(models, p["user_id"], p["account_source"], removed, ids))
            wait_for_state(
                module,
                lambda: (
                    "ready"
                    if normalize_policies(current_user(module, client, models, p["user_id"], p["account_source"]).get("PolicySet") or []) == target
                    else "pending"
                ),
                ["ready"],
                timeout=p["waiter_timeout"],
                delay=p["waiter_delay"],
            )
            current = normalize_policies(current_user(module, client, models, p["user_id"], p["account_source"]).get("PolicySet") or [])
        module.exit_json(changed=True, **(diff_value or {}), policies=current if not module.check_mode else target, added=added, removed=removed)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
