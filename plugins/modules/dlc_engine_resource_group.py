#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_engine_resource_group
short_description: Manage Tencent Cloud DLC standard engine resource groups
version_added: "0.14.0"
description:
  - Creates, updates and deletes standard DLC engine resource groups.
  - Reconciles base settings, Spark executor capacity and network bindings from readable API state.
options:
  state:
    description:
      - Desired lifecycle state.
    type: str
    choices: [present, absent]
    default: present
  name:
    description:
      - Exact resource-group name.
    type: str
    required: true
  data_engine_name:
    description:
      - Parent standard engine name, required for creation and immutable afterwards.
    type: str
  auto_launch:
    description:
      - Automatically launch when a task is submitted.
    type: bool
  auto_pause:
    description:
      - Automatically pause while idle.
    type: bool
  auto_pause_time:
    description:
      - Idle minutes before automatic pause.
    type: int
  max_concurrency:
    description:
      - Maximum concurrent tasks.
    type: int
  driver_cu_spec:
    description:
      - Spark driver CU specification.
    type: str
  executor_cu_spec:
    description:
      - Spark executor CU specification.
    type: str
  min_executors:
    description:
      - Minimum executor count.
    type: int
  max_executors:
    description:
      - Maximum executor count.
    type: int
  network_config_names:
    description:
      - Exact network configuration bindings.
    type: list
    elements: str
  static_config:
    description:
      - Exact static Spark configuration map; omitted keys are removed.
    type: dict
  dynamic_config:
    description:
      - Exact dynamic Spark configuration map; omitted keys are removed.
    type: dict
  launch_now:
    description:
      - Launch immediately after creation.
    type: bool
    default: false
  effective_now:
    description:
      - Restart immediately when resource or network configuration changes.
    type: bool
    default: false
  allow_scale_down:
    description:
      - Explicitly authorize reducing executor capacity.
    type: bool
    default: false
  allow_delete:
    description:
      - Explicitly authorize deletion.
    type: bool
    default: false
  wait:
    description:
      - Wait for lifecycle and field convergence.
    type: bool
    default: true
  waiter_delay:
    description:
      - Seconds between polls.
    type: int
    default: 10
  waiter_timeout:
    description:
      - Overall convergence timeout.
    type: int
    default: 1800

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
- susunola.tencentcloud.dlc_engine_resource_group:
    name: spark-etl
    data_engine_name: production-spark
    driver_cu_spec: medium
    executor_cu_spec: large
    min_executors: 2
    max_executors: 10
    auto_pause: true
    auto_pause_time: 15
    network_config_names: [private-data]

- susunola.tencentcloud.dlc_engine_resource_group:
    name: spark-etl
    state: absent
    allow_delete: true
"""
RETURN = r"""resource_group:
  description:
    - Effective standard engine resource-group metadata.
  returned: always
  type: dict
resource_group_id:
  description:
    - Standard engine resource-group ID.
  returned: when present
  type: str"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state

BASE = {"auto_launch": "AutoLaunch", "auto_pause": "AutoPause", "auto_pause_time": "AutoPauseTime", "max_concurrency": "MaxConcurrency"}
CAPACITY = {"driver_cu_spec": "DriverCuSpec", "executor_cu_spec": "ExecutorCuSpec", "min_executors": "MinExecutorNums", "max_executors": "MaxExecutorNums"}


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def _flag(value):
    return 0 if value else 1


def describe_request(models, name, offset=0):
    request = models.DescribeStandardEngineResourceGroupsRequest()
    request.Offset, request.Limit = offset, 100
    item = models.Filter()
    item.Name, item.Values = "engine-resource-group-name-unique", [name]
    request.Filters = [item]
    return request


def find(module, client, models, name):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeStandardEngineResourceGroups, describe_request(models, name, offset))
        page = response.UserEngineResourceGroupInfos or []
        matches.extend(x._serialize(allow_none=True) for x in page if x.EngineResourceGroupName == name and x.ResourceGroupState != -1)
        offset += len(page)
        if not page or offset >= int(response.Total or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple DLC engine resource groups matched the exact name", name=name)
    return matches[0] if matches else None


def config_request(models, resource_group_id, offset=0):
    request = models.DescribeStandardEngineResourceGroupConfigInfoRequest()
    request.Offset, request.Limit = offset, 100
    item = models.Filter()
    item.Name, item.Values = "engine-resource-group-id", [resource_group_id]
    request.Filters = [item]
    return request


def read_config(module, client, models, resource_group_id):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeStandardEngineResourceGroupConfigInfo, config_request(models, resource_group_id, offset))
        page = response.StandardEngineResourceGroupConfigInfos or []
        matches.extend(page)
        offset += len(page)
        if not page or offset >= int(response.Total or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple DLC configuration records matched the resource-group ID", resource_group_id=resource_group_id)
    item = matches[0] if matches else None

    def pairs(value):
        return {x.ConfigItem: x.ConfigValue for x in (value or []) if x.ConfigItem is not None}

    return {"StaticConfig": pairs(item.StaticConfigPairs if item else []), "DynamicConfig": pairs(item.DynamicConfigPairs if item else [])}


def enrich_config(module, client, models, current, p):
    if current and (p.get("static_config") is not None or p.get("dynamic_config") is not None):
        current.update(read_config(module, client, models, current["EngineResourceGroupId"]))
    return current


def create_request(models, p):
    request = models.CreateStandardEngineResourceGroupRequest()
    request.EngineResourceGroupName, request.DataEngineName = p["name"], p["data_engine_name"]
    request.IsLaunchNow = _flag(p["launch_now"])
    for source, target in {**BASE, **CAPACITY}.items():
        if p.get(source) is not None:
            setattr(request, target, _flag(p[source]) if source in ("auto_launch", "auto_pause") else p[source])
    if p.get("network_config_names") is not None:
        request.NetworkConfigNames = sorted(set(p["network_config_names"]))

    def pairs(values):
        result = []
        for key, value in sorted((values or {}).items()):
            item = models.EngineResourceGroupConfigPair()
            item.ConfigItem, item.ConfigValue = key, str(value)
            result.append(item)
        return result

    if p.get("static_config") is not None:
        request.StaticConfigPairs = pairs(p["static_config"])
    if p.get("dynamic_config") is not None:
        request.DynamicConfigPairs = pairs(p["dynamic_config"])
    return request


def base_request(models, p):
    request = models.UpdateStandardEngineResourceGroupBaseInfoRequest()
    request.EngineResourceGroupName = p["name"]
    for source, target in BASE.items():
        if p.get(source) is not None:
            setattr(request, target, _flag(p[source]) if source in ("auto_launch", "auto_pause") else p[source])
    return request


def capacity_request(models, p):
    request = models.UpdateStandardEngineResourceGroupResourceInfoRequest()
    request.EngineResourceGroupName = p["name"]
    request.IsEffectiveNow = _flag(p["effective_now"])
    for source, target in CAPACITY.items():
        if p.get(source) is not None:
            setattr(request, target, p[source])
    return request


def network_request(models, resource_group_id, names, effective_now):
    request = models.UpdateEngineResourceGroupNetworkConfigInfoRequest()
    request.EngineResourceGroupId, request.NetworkConfigNames = resource_group_id, sorted(set(names))
    request.IsEffectiveNow = _flag(effective_now)
    return request


def config_update_request(models, name, changes, effective_now):
    request = models.UpdateStandardEngineResourceGroupConfigInfoRequest()
    request.EngineResourceGroupName = name
    request.IsEffectiveNow = _flag(effective_now)
    contexts = []
    for config_type, delta in (("StaticConfigType", changes.get("StaticConfig")), ("DynamicConfigType", changes.get("DynamicConfig"))):
        if not delta:
            continue
        context = models.UpdateConfContext()
        context.ConfigType, context.Params = config_type, []
        for key, (old, new) in sorted(delta.items()):
            item = models.Param()
            item.ConfigItem, item.ConfigValue = key, "" if new is None else str(new)
            item.Operate = "DELETE" if new is None else ("ADD" if old is None else "MODIFY")
            context.Params.append(item)
        contexts.append(context)
    request.UpdateConfContext = contexts
    return request


def delete_request(models, name):
    request = models.DeleteStandardEngineResourceGroupRequest()
    request.EngineResourceGroupName = name
    return request


def desired(p, current=None):
    result = dict(current or {})
    for source, target in {**BASE, **CAPACITY}.items():
        if p.get(source) is not None:
            result[target] = _flag(p[source]) if source in ("auto_launch", "auto_pause") else p[source]
    if p.get("network_config_names") is not None:
        result["NetworkConfigNames"] = sorted(set(p["network_config_names"]))
    if p.get("static_config") is not None:
        result["StaticConfig"] = {k: str(v) for k, v in p["static_config"].items()}
    if p.get("dynamic_config") is not None:
        result["DynamicConfig"] = {k: str(v) for k, v in p["dynamic_config"].items()}
    return result


def drift(p, current):
    changes = {}
    target = desired(p, current)
    for key in list(BASE.values()) + list(CAPACITY.values()):
        if target.get(key) != current.get(key):
            changes[key] = (current.get(key), target.get(key))
    if p.get("network_config_names") is not None:
        old, new = sorted(set(current.get("NetworkConfigNames") or [])), target["NetworkConfigNames"]
        if old != new:
            changes["NetworkConfigNames"] = (old, new)
    for source, target_name in (("static_config", "StaticConfig"), ("dynamic_config", "DynamicConfig")):
        if p.get(source) is not None:
            old, new = current.get(target_name) or {}, target[target_name]
            if old != new:
                changes[target_name] = (old, new)
    return changes


def config_delta(changes):
    result = {}
    for target in ("StaticConfig", "DynamicConfig"):
        if target not in changes:
            continue
        old, new = changes[target]
        keys = set(old) | set(new)
        result[target] = {key: (old.get(key), new.get(key)) for key in keys if old.get(key) != new.get(key)}
    return result


def wait_group(module, client, models, p, absent=False, expected=None):
    def poll():
        current = enrich_config(module, client, models, find(module, client, models, p["name"]), p)
        if absent:
            return "absent" if current is None else "pending"
        if current is None:
            return "absent"
        if current.get("ResourceGroupState") == -1:
            module.fail_json(msg="DLC engine resource group entered a failed state", resource_group=current)
        if current.get("ResourceGroupState") not in (2, 3):
            return "pending"
        if expected and any((sorted(current.get(k) or []) if k == "NetworkConfigNames" else current.get(k)) != v for k, v in expected.items()):
            return "pending"
        return "ready"

    wait_for_state(module, poll, ["absent" if absent else "ready"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "name": {"required": True},
        "data_engine_name": {},
        "auto_launch": {"type": "bool"},
        "auto_pause": {"type": "bool"},
        "auto_pause_time": {"type": "int"},
        "max_concurrency": {"type": "int"},
        "driver_cu_spec": {},
        "executor_cu_spec": {},
        "min_executors": {"type": "int"},
        "max_executors": {"type": "int"},
        "network_config_names": {"type": "list", "elements": "str"},
        "static_config": {"type": "dict"},
        "dynamic_config": {"type": "dict"},
        "launch_now": {"type": "bool", "default": False},
        "effective_now": {"type": "bool", "default": False},
        "allow_scale_down": {"type": "bool", "default": False},
        "allow_delete": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 10},
        "waiter_timeout": {"type": "int", "default": 1800},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if p.get("min_executors") is not None and p.get("max_executors") is not None and p["min_executors"] > p["max_executors"]:
        module.fail_json(msg="min_executors must not exceed max_executors")
    if p.get("auto_pause_time") is not None and not 1 <= p["auto_pause_time"] <= 999:
        module.fail_json(msg="auto_pause_time must be between 1 and 999")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = enrich_config(module, client, models, find(module, client, models, p["name"]), p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, resource_group=None, resource_group_id=None)
            if not p["allow_delete"]:
                module.fail_json(msg="set allow_delete=true to authorize deleting the DLC engine resource group", resource_group=current)
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteStandardEngineResourceGroup, delete_request(models, p["name"]))
                if p["wait"]:
                    wait_group(module, client, models, p, absent=True)
            module.exit_json(changed=True, **(diff_value or {}), resource_group=None, resource_group_id=None)
        if not current:
            if not p.get("data_engine_name"):
                module.fail_json(msg="data_engine_name is required when creating a DLC engine resource group")
            after = desired(p, {"EngineResourceGroupName": p["name"], "DataEngineName": p["data_engine_name"]})
            diff_value = maybe_diff(module, None, after)
            if not module.check_mode:
                module.sdk_call(client.CreateStandardEngineResourceGroup, create_request(models, p))
                if p["wait"]:
                    wait_group(module, client, models, p, expected={k: v for k, v in after.items() if k not in ("EngineResourceGroupName", "DataEngineName")})
                current = enrich_config(module, client, models, find(module, client, models, p["name"]), p)
            module.exit_json(
                changed=True,
                **(diff_value or {}),
                resource_group=current if not module.check_mode else after,
                resource_group_id=(current or {}).get("EngineResourceGroupId"),
            )
        if p.get("data_engine_name") is not None and current.get("DataEngineName") != p["data_engine_name"]:
            module.fail_json(
                msg="data_engine_name is immutable for a DLC engine resource group",
                immutable_drift={"DataEngineName": (current.get("DataEngineName"), p["data_engine_name"])},
            )
        changes = drift(p, current)
        for key in ("MinExecutorNums", "MaxExecutorNums"):
            if key in changes and changes[key][0] is not None and changes[key][1] < changes[key][0] and not p["allow_scale_down"]:
                module.fail_json(msg="set allow_scale_down=true to authorize reducing DLC resource-group capacity", capacity_drift={key: changes[key]})
        if not changes:
            module.exit_json(changed=False, resource_group=current, resource_group_id=current.get("EngineResourceGroupId"))
        after, diff_value = desired(p, current), maybe_diff(module, current, desired(p, current))
        if not module.check_mode:
            if any(k in changes for k in BASE.values()):
                module.sdk_call(client.UpdateStandardEngineResourceGroupBaseInfo, base_request(models, p))
            if any(k in changes for k in CAPACITY.values()):
                module.sdk_call(client.UpdateStandardEngineResourceGroupResourceInfo, capacity_request(models, p))
            if "NetworkConfigNames" in changes:
                module.sdk_call(
                    client.UpdateEngineResourceGroupNetworkConfigInfo,
                    network_request(models, current["EngineResourceGroupId"], p["network_config_names"], p["effective_now"]),
                )
            if "StaticConfig" in changes or "DynamicConfig" in changes:
                module.sdk_call(
                    client.UpdateStandardEngineResourceGroupConfigInfo, config_update_request(models, p["name"], config_delta(changes), p["effective_now"])
                )
            if p["wait"]:
                wait_group(module, client, models, p, expected={k: v[1] for k, v in changes.items()})
            current = enrich_config(module, client, models, find(module, client, models, p["name"]), p)
        module.exit_json(
            changed=True,
            **(diff_value or {}),
            resource_group=current if not module.check_mode else after,
            resource_group_id=(current or {}).get("EngineResourceGroupId"),
        )
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
