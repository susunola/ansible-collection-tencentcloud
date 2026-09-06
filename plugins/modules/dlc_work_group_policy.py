#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: dlc_work_group_policy
short_description: Manage Tencent Cloud Data Lake Compute work-group policies
version_added: "0.14.0"
description:
  - Exactly reconciles writable DLC authorization policies attached to a work group.
  - Ignores server-generated policy IDs, sources, operators and timestamps while preferring PolicyId for precise detach operations.
options:
  work_group_id: {type: int, required: true, description: DLC work-group ID.}
  policies: {type: list, elements: dict, required: true, description: Exact desired SDK Policy list.}
  allow_empty: {type: bool, default: false, description: Explicitly authorize removing every policy from the work group.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between convergence polls.}
  waiter_timeout: {type: int, default: 120, description: Overall convergence timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_work_group_policy:
    work_group_id: 10042
    policies:
      - {Catalog: DataLakeCatalog, Database: sales, Table: orders, Operation: SELECT, PolicyType: TABLE}
      - {DataEngine: production-spark, Operation: ALL, PolicyType: ENGINE}
"""
RETURN = r"""policies: {description: Effective normalized policy set., type: list, elements: dict, returned: always}
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
        raise ValueError("duplicate DLC work-group policies are not allowed")
    return [value for _, value in sorted(zip(keys, result), key=lambda pair: pair[0])]


def describe_request(models, work_group_id):
    r = models.DescribeWorkGroupsRequest()
    r.WorkGroupId, r.Offset, r.Limit = work_group_id, 0, 100
    return r


def current_group(module, client, models, work_group_id):
    response = module.sdk_call(client.DescribeWorkGroups, describe_request(models, work_group_id))
    matches = [x._serialize(allow_none=True) for x in response.WorkGroupSet or [] if x.WorkGroupId == work_group_id]
    if not matches:
        module.fail_json(msg="DLC work group not found", work_group_id=work_group_id)
    if len(matches) > 1:
        module.fail_json(msg="Multiple DLC work groups returned for exact ID", work_group_id=work_group_id)
    return matches[0]


def policy_models(models, values):
    result = []
    for value in values:
        item = models.Policy()
        item.from_json_string(json.dumps(value))
        result.append(item)
    return result


def attach_request(models, work_group_id, values):
    r = models.AttachWorkGroupPolicyRequest()
    r.WorkGroupId, r.PolicySet = work_group_id, policy_models(models, values)
    return r


def detach_request(models, work_group_id, values, policy_ids=None):
    r = models.DetachWorkGroupPolicyRequest()
    r.WorkGroupId = work_group_id
    if policy_ids and len(policy_ids) == len(values):
        r.PolicyIds = policy_ids
    else:
        r.PolicySet = policy_models(models, values)
    return r


def delta(current, target):
    current_map = {json.dumps(value, sort_keys=True, separators=(",", ":")): value for value in normalize_policies(current)}
    target_map = {json.dumps(value, sort_keys=True, separators=(",", ":")): value for value in normalize_policies(target)}
    return [target_map[key] for key in sorted(set(target_map) - set(current_map))], [current_map[key] for key in sorted(set(current_map) - set(target_map))]


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "work_group_id": {"type": "int", "required": True},
            "policies": {"type": "list", "elements": "dict", "required": True},
            "allow_empty": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        group = current_group(module, client, models, p["work_group_id"])
        raw_current = group.get("PolicySet") or []
        current = normalize_policies(raw_current)
        target = normalize_policies(p["policies"])
        if not target and not p["allow_empty"]:
            module.fail_json(msg="set allow_empty=true to authorize removing every DLC work-group policy")
        added, removed = delta(raw_current, target)
        if not added and not removed:
            module.exit_json(changed=False, policies=current, added=[], removed=[])
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            if added:
                module.sdk_call(client.AttachWorkGroupPolicy, attach_request(models, p["work_group_id"], added))
            if removed:
                removed_keys = {json.dumps(value, sort_keys=True, separators=(",", ":")) for value in removed}
                ids = [
                    str(value.get("PolicyId"))
                    for value in raw_current
                    if json.dumps(normalize_policy(value), sort_keys=True, separators=(",", ":")) in removed_keys and value.get("PolicyId")
                ]
                module.sdk_call(client.DetachWorkGroupPolicy, detach_request(models, p["work_group_id"], removed, ids))
            wait_for_state(
                module,
                lambda: (
                    "ready" if normalize_policies(current_group(module, client, models, p["work_group_id"]).get("PolicySet") or []) == target else "pending"
                ),
                ["ready"],
                timeout=p["waiter_timeout"],
                delay=p["waiter_delay"],
            )
            current = normalize_policies(current_group(module, client, models, p["work_group_id"]).get("PolicySet") or [])
        module.exit_json(changed=True, **(diff or {}), policies=current if not module.check_mode else target, added=added, removed=removed)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
