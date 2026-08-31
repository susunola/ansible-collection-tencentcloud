#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: dlc_data_engine
short_description: Manage Tencent Cloud Data Lake Compute engines
version_added: "0.14.0"
description:
  - Creates, updates, starts, suspends, switches images and deletes private DLC data engines.
  - Engine identity, type, billing, network and generation are immutable after creation.
options:
  state: {type: str, choices: [present, running, suspended, absent], default: present, description: Desired engine lifecycle state.}
  name: {type: str, required: true, description: Data engine name.}
  engine_type: {type: str, choices: [spark, presto, kyuubi], description: Engine type required for creation.}
  cluster_type: {type: str, description: Cluster resource type required for creation.}
  mode: {type: int, choices: [0, 1, 2], description: Billing mode required for creation.}
  size: {type: int, description: Desired engine CU size.}
  min_clusters: {type: int, description: Desired minimum cluster count.}
  max_clusters: {type: int, description: Desired maximum cluster count.}
  auto_resume: {type: bool, description: Automatically resume the engine.}
  auto_suspend: {type: bool, description: Automatically suspend an idle engine.}
  auto_suspend_time: {type: int, description: Idle minutes before automatic suspension.}
  max_concurrency: {type: int, description: Maximum concurrent tasks per cluster.}
  tolerable_queue_time: {type: int, description: Queue duration before elasticity may trigger.}
  description: {type: str, description: Engine description, at most 250 characters.}
  cidr_block: {type: str, description: Creation-time VPC CIDR block.}
  engine_network_id: {type: str, description: Creation-time engine network ID.}
  engine_exec_type: {type: str, choices: [SQL, BATCH], description: Creation-time execution type.}
  resource_type: {type: str, choices: [Standard_CU, Memory_CU], description: Creation-time resource type.}
  engine_generation: {type: str, choices: [Native, SuperSQL], description: Creation-time engine generation.}
  image_version_name: {type: str, description: Desired engine image name, resolved to an online image version ID for existing engines.}
  allow_image_switch: {type: bool, default: false, description: Explicitly authorize switching an existing engine image.}
  pay_mode: {type: int, choices: [0, 1], default: 0, description: Payment type used during creation.}
  allow_scale_down: {type: bool, default: false, description: Explicitly authorize reducing size or cluster bounds.}
  allow_delete: {type: bool, default: false, description: Explicitly authorize engine deletion.}
  wait: {type: bool, default: true, description: Wait for lifecycle and configuration convergence.}
  waiter_delay: {type: int, default: 10, description: Seconds between convergence polls.}
  waiter_timeout: {type: int, default: 1800, description: Overall convergence timeout in seconds.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.dlc_data_engine:
    name: production-spark
    engine_type: spark
    cluster_type: spark_cu
    mode: 1
    size: 16
    min_clusters: 1
    max_clusters: 4
    auto_suspend: true
    auto_suspend_time: 15
    state: running

- susunola.tencentcloud.dlc_data_engine:
    name: production-spark
    state: absent
    allow_delete: true
'''
RETURN = r'''data_engine: {description: Effective DLC data-engine metadata., type: dict, returned: always}
data_engine_id: {description: DLC data-engine ID., type: str, returned: when present}'''

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


MUTABLE = {
    "size": "Size", "min_clusters": "MinClusters", "max_clusters": "MaxClusters",
    "auto_resume": "AutoResume", "auto_suspend": "AutoSuspend",
    "auto_suspend_time": "AutoSuspendTime", "max_concurrency": "MaxConcurrency",
    "tolerable_queue_time": "TolerableQueueTime",
}
IMMUTABLE = {
    "engine_type": "EngineType", "cluster_type": "ClusterType", "mode": "Mode",
    "cidr_block": "CidrBlock", "engine_network_id": "EngineNetworkId",
    "engine_exec_type": "EngineExecType", "resource_type": "ResourceType",
    "engine_generation": "EngineGeneration",
}


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client
    return models, dlc_client


def describe_request(models, name, offset=0):
    request = models.DescribeDataEnginesRequest()
    request.Offset, request.Limit, request.ExcludePublicEngine = offset, 100, True
    item = models.Filter(); item.Name, item.Values = "data-engine-name", [name]
    request.Filters = [item]
    return request


def find(module, client, models, name):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeDataEngines, describe_request(models, name, offset))
        page = response.DataEngines or []
        matches.extend(x._serialize(allow_none=True) for x in page if x.DataEngineName == name and x.State != -2)
        offset += len(page)
        if not page or offset >= int(response.TotalCount or 0): break
    if len(matches) > 1: module.fail_json(msg="Multiple DLC data engines matched the exact name", name=name)
    return matches[0] if matches else None


def create_request(models, p):
    payload = {
        "DataEngineName": p["name"], "EngineType": p["engine_type"],
        "ClusterType": p["cluster_type"], "Mode": p["mode"], "PayMode": p["pay_mode"],
        "Message": p.get("description"),
    }
    for source, target in {**MUTABLE, **IMMUTABLE}.items():
        if p.get(source) is not None: payload[target] = p[source]
    if p.get("image_version_name") is not None: payload["ImageVersionName"] = p["image_version_name"]
    request = models.CreateDataEngineRequest(); request.from_json_string(json.dumps(payload)); return request


def update_request(models, p):
    payload = {"DataEngineName": p["name"]}
    for source, target in MUTABLE.items():
        if p.get(source) is not None: payload[target] = p[source]
    request = models.UpdateDataEngineRequest(); request.from_json_string(json.dumps(payload)); return request


def description_request(models, name, message):
    request = models.ModifyDataEngineDescriptionRequest(); request.DataEngineName, request.Message = name, message; return request


def operation_request(models, name, operation):
    request = models.SuspendResumeDataEngineRequest(); request.DataEngineName, request.Operate = name, operation; return request


def delete_request(models, name):
    request = models.DeleteDataEngineRequest(); request.DataEngineNames = [name]; return request


def image_versions_request(models, engine_type):
    request = models.DescribeDataEngineImageVersionsRequest(); request.EngineType, request.Sort, request.Asc = engine_type, "UpdateTime", False; return request


def resolve_image(module, client, models, current, name):
    engine_type = current.get("EngineTypeDetail")
    if not engine_type:
        base = str(current.get("EngineType") or "").lower()
        engine_type = "SparkBatch" if current.get("EngineExecType") == "BATCH" else ("SparkSQL" if base == "spark" else "PrestoSQL")
    response = module.sdk_call(client.DescribeDataEngineImageVersions, image_versions_request(models, engine_type))
    matches = [x for x in (response.ImageParentVersions or []) if x.ImageVersion == name and x.State == 2]
    if not matches: module.fail_json(msg="online DLC data-engine image version was not found", image_version_name=name, engine_type=engine_type)
    if len(matches) > 1: module.fail_json(msg="multiple online DLC data-engine images matched the exact version name", image_version_name=name, engine_type=engine_type)
    return {"ImageVersionId": matches[0].ImageVersionId, "ImageVersionName": matches[0].ImageVersion}


def image_switch_request(models, engine_id, image_id):
    request = models.SwitchDataEngineImageRequest(); request.DataEngineId, request.NewImageVersionId = engine_id, image_id; return request


def desired_view(p, current=None):
    result = dict(current or {})
    for source, target in MUTABLE.items():
        if p.get(source) is not None: result[target] = p[source]
    if p.get("description") is not None: result["Message"] = p["description"]
    if p.get("image_version_name") is not None: result["ImageVersionName"] = p["image_version_name"]
    return result


def drift(p, current):
    return {target: (current.get(target), p[source]) for source, target in MUTABLE.items()
            if p.get(source) is not None and current.get(target) != p[source]}


def wait_engine(module, client, models, p, target, desired=None):
    def poll():
        current = find(module, client, models, p["name"])
        if target == "absent": return "absent" if current is None else "pending"
        if current is None: return "absent"
        if current.get("State") == -1:
            module.fail_json(msg="DLC data engine entered a failed state", data_engine=current)
        if target == "running" and current.get("State") != 2: return "pending"
        if target == "suspended" and current.get("State") != 1: return "pending"
        if target == "ready" and current.get("State") not in (1, 2): return "pending"
        if desired and any(current.get(k) != v for k, v in desired.items()): return "pending"
        return target
    wait_for_state(module, poll, [target], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    spec = {
        "state": {"choices": ["present", "running", "suspended", "absent"], "default": "present"},
        "name": {"required": True}, "engine_type": {"choices": ["spark", "presto", "kyuubi"]},
        "cluster_type": {}, "mode": {"type": "int", "choices": [0, 1, 2]}, "size": {"type": "int"},
        "min_clusters": {"type": "int"}, "max_clusters": {"type": "int"}, "auto_resume": {"type": "bool"},
        "auto_suspend": {"type": "bool"}, "auto_suspend_time": {"type": "int"},
        "max_concurrency": {"type": "int"}, "tolerable_queue_time": {"type": "int"}, "description": {},
        "cidr_block": {}, "engine_network_id": {}, "engine_exec_type": {"choices": ["SQL", "BATCH"]},
        "resource_type": {"choices": ["Standard_CU", "Memory_CU"]},
        "engine_generation": {"choices": ["Native", "SuperSQL"]}, "image_version_name": {},
        "pay_mode": {"type": "int", "choices": [0, 1], "default": 0},
        "allow_scale_down": {"type": "bool", "default": False}, "allow_image_switch": {"type": "bool", "default": False},
        "allow_delete": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True}, "waiter_delay": {"type": "int", "default": 10},
        "waiter_timeout": {"type": "int", "default": 1800},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True); p = module.params
    if p.get("description") is not None and len(p["description"]) > 250: module.fail_json(msg="DLC data-engine description must not exceed 250 characters")
    if p.get("min_clusters") is not None and p.get("max_clusters") is not None and p["min_clusters"] > p["max_clusters"]: module.fail_json(msg="min_clusters must not exceed max_clusters")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["name"])
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, data_engine=None, data_engine_id=None)
            if not p["allow_delete"]: module.fail_json(msg="set allow_delete=true to authorize deleting the DLC data engine", data_engine=current)
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteDataEngine, delete_request(models, p["name"]))
                if p["wait"]: wait_engine(module, client, models, p, "absent")
            module.exit_json(changed=True, **(diff_value or {}), data_engine=None, data_engine_id=None)
        if not current:
            required = ("engine_type", "cluster_type", "mode")
            missing = [key for key in required if p.get(key) is None]
            if missing: module.fail_json(msg="creation parameters are required for a DLC data engine", missing=missing)
            target = desired_view(p, {"DataEngineName": p["name"], "State": 2 if p["state"] == "running" else None})
            diff_value = maybe_diff(module, None, target)
            if not module.check_mode:
                engine_id = module.sdk_call(client.CreateDataEngine, create_request(models, p)).DataEngineId
                if p["wait"]: wait_engine(module, client, models, p, "ready", {k: v for k, v in target.items() if k not in ("State", "DataEngineName")})
                current = find(module, client, models, p["name"])
                target_state = {"running": 2, "suspended": 1}.get(p["state"])
                if target_state is not None and (current or {}).get("State") != target_state:
                    operation = "resume" if target_state == 2 else "suspend"
                    module.sdk_call(client.SuspendResumeDataEngine, operation_request(models, p["name"], operation))
                    if p["wait"]: wait_engine(module, client, models, p, p["state"])
                    current = find(module, client, models, p["name"])
            else: engine_id = None
            module.exit_json(changed=True, **(diff_value or {}), data_engine=current if not module.check_mode else target, data_engine_id=(current or {}).get("DataEngineId") if not module.check_mode else engine_id)
        immutable_drift = {target: (current.get(target), p[source]) for source, target in IMMUTABLE.items() if p.get(source) is not None and current.get(target) != p[source]}
        if immutable_drift: module.fail_json(msg="DLC data-engine identity, type, billing, network and generation fields are immutable", immutable_drift=immutable_drift)
        changes = drift(p, current)
        image_target = None
        if p.get("image_version_name") is not None and current.get("ImageVersionName") != p["image_version_name"]:
            image_target = resolve_image(module, client, models, current, p["image_version_name"])
            if not p["allow_image_switch"]: module.fail_json(msg="set allow_image_switch=true to authorize switching the DLC engine image", image_drift={"ImageVersionName": (current.get("ImageVersionName"), p["image_version_name"])}, image_target=image_target)
            changes["ImageVersionName"] = (current.get("ImageVersionName"), image_target["ImageVersionName"])
            changes["ImageVersionId"] = (current.get("ImageVersionId"), image_target["ImageVersionId"])
        for key in ("Size", "MinClusters", "MaxClusters"):
            if key in changes and changes[key][0] is not None and changes[key][1] < changes[key][0] and not p["allow_scale_down"]:
                module.fail_json(msg="set allow_scale_down=true to authorize reducing DLC engine capacity", capacity_drift={key: changes[key]})
        if p.get("description") is not None and (current.get("Message") or "") != p["description"]: changes["Message"] = (current.get("Message") or "", p["description"])
        target_state = {"running": 2, "suspended": 1}.get(p["state"])
        state_change = target_state is not None and current.get("State") != target_state
        if not changes and not state_change: module.exit_json(changed=False, data_engine=current, data_engine_id=current.get("DataEngineId"))
        after = desired_view(p, current)
        if image_target: after.update(image_target)
        if target_state is not None: after["State"] = target_state
        diff_value = maybe_diff(module, current, after)
        if not module.check_mode:
            mutable_changes = {k: v for k, v in changes.items() if k != "Message"}
            mutable_changes = {k: v for k, v in mutable_changes.items() if k not in ("ImageVersionName", "ImageVersionId")}
            if mutable_changes: module.sdk_call(client.UpdateDataEngine, update_request(models, p))
            if "Message" in changes: module.sdk_call(client.ModifyDataEngineDescription, description_request(models, p["name"], p["description"]))
            if image_target: module.sdk_call(client.SwitchDataEngineImage, image_switch_request(models, current["DataEngineId"], image_target["ImageVersionId"]))
            if changes and p["wait"]: wait_engine(module, client, models, p, "ready", {k: v[1] for k, v in changes.items()})
            current = find(module, client, models, p["name"])
            if state_change and current.get("State") != target_state:
                operation = "resume" if target_state == 2 else "suspend"
                module.sdk_call(client.SuspendResumeDataEngine, operation_request(models, p["name"], operation))
                if p["wait"]: wait_engine(module, client, models, p, p["state"])
                current = find(module, client, models, p["name"])
        module.exit_json(changed=True, **(diff_value or {}), data_engine=current if not module.check_mode else after, data_engine_id=current.get("DataEngineId"))
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
