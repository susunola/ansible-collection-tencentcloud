#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: dlc_data_mask_strategy
short_description: Manage Tencent Cloud Data Lake Compute masking strategies
version_added: "0.14.0"
description:
  - Creates, discovers, updates and deletes DLC data masking strategies.
  - Normalizes user and work-group ordering for stable idempotency.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired strategy state.}
  strategy_id: {type: str, description: Existing masking strategy ID.}
  name: {type: str, description: Strategy name, required for creation and usable for exact discovery.}
  strategy_type: {type: str, choices: [MASK_SHOW_FIRST_4, MASK_SHOW_LAST_4, MASK_HASH, MASK_DATE_SHOW_YEAR, MASK_NULL, MASK_DEFAULT], description: Desired masking method.}
  description: {type: str, description: Desired strategy description.}
  groups: {type: list, elements: dict, description: Desired GroupInfo list containing WorkGroupId and StrategyType.}
  users: {type: list, elements: str, description: Exact desired sub-account UIN list.}
  allow_delete: {type: bool, default: false, description: Explicitly authorize strategy deletion.}
  wait: {type: bool, default: true, description: Wait for mutation convergence.}

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
- susunola.tencentcloud.dlc_data_mask_strategy:
    name: mask-customer-phone
    strategy_type: MASK_SHOW_LAST_4
    description: Reveal only the final four digits
    groups:
      - {WorkGroupId: 10042, StrategyType: MASK_SHOW_LAST_4}
    users: ['100012345678']

- susunola.tencentcloud.dlc_data_mask_strategy:
    strategy_id: dms-xxxxxxxx
    state: absent
    allow_delete: true
"""
RETURN = r"""strategy: {description: Effective normalized masking strategy., type: dict, returned: always}
strategy_id: {description: DLC masking strategy ID., type: str, returned: when present}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def describe_request(models, p, offset=0):
    request = models.DescribeDataMaskStrategiesRequest()
    request.Offset, request.Limit = offset, 100
    if p.get("name"):
        item = models.Filter()
        item.Name, item.Values = "strategy-name", [p["name"]]
        request.Filters = [item]
    return request


def normalize_groups(values):
    result = [{"WorkGroupId": int(x["WorkGroupId"]), "StrategyType": x.get("StrategyType") or ""} for x in values or []]
    keys = [(x["WorkGroupId"], x["StrategyType"]) for x in result]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate DLC masking work-group rules are not allowed")
    return sorted(result, key=lambda x: (x["WorkGroupId"], x["StrategyType"]))


def normalize_users(value):
    values = value.split(";") if isinstance(value, str) else (value or [])
    result = sorted({str(x) for x in values if str(x)})
    return result


def normalize(value):
    return {
        "StrategyId": value.get("StrategyId"),
        "StrategyName": value.get("StrategyName") or "",
        "StrategyType": value.get("StrategyType") or "",
        "StrategyDesc": value.get("StrategyDesc") or "",
        "Groups": normalize_groups(value.get("Groups")),
        "Users": normalize_users(value.get("Users")),
    }


def find(module, client, models, p):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeDataMaskStrategies, describe_request(models, p, offset))
        page = response.Strategies or []
        for item in page:
            value = item._serialize(allow_none=True)
            if value.get("State") == 0:
                continue
            if (p.get("strategy_id") and value.get("StrategyId") == p["strategy_id"]) or (
                not p.get("strategy_id") and value.get("StrategyName") == p.get("name")
            ):
                matches.append(value)
        offset += len(page)
        if not page or offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple DLC masking strategies matched; specify strategy_id")
    return matches[0] if matches else None


def desired(p, current=None):
    value = normalize(current or {})
    if p.get("strategy_id"):
        value["StrategyId"] = p["strategy_id"]
    mapping = {"name": "StrategyName", "strategy_type": "StrategyType", "description": "StrategyDesc"}
    for source, target in mapping.items():
        if p.get(source) is not None:
            value[target] = p[source]
    if p.get("groups") is not None:
        value["Groups"] = normalize_groups(p["groups"])
    if p.get("users") is not None:
        value["Users"] = normalize_users(p["users"])
    return value


def strategy_model(models, value):
    payload = dict(value)
    payload["Users"] = ";".join(value.get("Users") or [])
    item = models.DataMaskStrategyInfo()
    item.from_json_string(json.dumps(payload))
    return item


def create_request(models, target):
    request = models.CreateDataMaskStrategyRequest()
    request.Strategy = strategy_model(models, target)
    return request


def update_request(models, target):
    request = models.UpdateDataMaskStrategyRequest()
    request.Strategy = strategy_model(models, target)
    return request


def delete_request(models, strategy_id):
    request = models.DeleteDataMaskStrategyRequest()
    request.StrategyId = strategy_id
    return request


def wait_strategy(module, client, models, p, target=None):
    def poll():
        current = find(module, client, models, p)
        if target is None:
            return "absent" if current is None else "pending"
        return "ready" if current is not None and normalize(current) == target else "pending"

    wait_for_state(module, poll, ["absent" if target is None else "ready"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    types = ["MASK_SHOW_FIRST_4", "MASK_SHOW_LAST_4", "MASK_HASH", "MASK_DATE_SHOW_YEAR", "MASK_NULL", "MASK_DEFAULT"]
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "strategy_id": {},
        "name": {},
        "strategy_type": {"choices": types},
        "description": {},
        "groups": {"type": "list", "elements": "dict"},
        "users": {"type": "list", "elements": "str"},
        "allow_delete": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 5},
        "waiter_timeout": {"type": "int", "default": 120},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("strategy_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, strategy=None, strategy_id=None)
            if not p["allow_delete"]:
                module.fail_json(msg="set allow_delete=true to authorize deleting the DLC masking strategy", strategy=normalize(current))
            diff_value = maybe_diff(module, normalize(current), None)
            if not module.check_mode:
                p["strategy_id"] = current["StrategyId"]
                module.sdk_call(client.DeleteDataMaskStrategy, delete_request(models, p["strategy_id"]))
                if p["wait"]:
                    wait_strategy(module, client, models, p)
            module.exit_json(changed=True, **(diff_value or {}), strategy=None, strategy_id=None)
        if not current:
            missing = [key for key in ("name", "strategy_type") if not p.get(key)]
            if missing:
                module.fail_json(msg="creation parameters are required for a DLC masking strategy", missing=missing)
            target = desired(p)
            diff_value = maybe_diff(module, None, target)
            strategy_id = None
            if not module.check_mode:
                strategy_id = module.sdk_call(client.CreateDataMaskStrategy, create_request(models, target)).StrategyId
                p["strategy_id"] = strategy_id
                target["StrategyId"] = strategy_id
                if p["wait"]:
                    wait_strategy(module, client, models, p, target)
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff_value or {}), strategy=normalize(current) if not module.check_mode else target, strategy_id=strategy_id)
        before, target = normalize(current), desired(p, current)
        if before == target:
            module.exit_json(changed=False, strategy=before, strategy_id=before["StrategyId"])
        diff_value = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.UpdateDataMaskStrategy, update_request(models, target))
            p["strategy_id"] = before["StrategyId"]
            if p["wait"]:
                wait_strategy(module, client, models, p, target)
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff_value or {}), strategy=normalize(current) if not module.check_mode else target, strategy_id=before["StrategyId"])
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
