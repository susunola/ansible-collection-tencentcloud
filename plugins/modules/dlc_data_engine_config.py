#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_data_engine_config
short_description: Reconcile Tencent Cloud DLC data-engine runtime configuration
version_added: "0.14.0"
description:
  - Reconciles the complete custom configuration pair set for an existing DLC data engine.
  - Optionally reconciles its Spark session resource template and supports exact engine-name resolution.
options:
  engine_id: {type: str, description: Exact DLC data-engine ID.}
  engine_name: {type: str, description: Exact DLC data-engine name resolved to its ID.}
  config_pairs:
    type: list
    elements: dict
    required: true
    description: Complete desired custom configuration set.
    options:
      key: {type: str, required: true, description: Configuration item name.}
      value: {type: str, required: true, description: Configuration item value.}
  session_resource_template:
    type: dict
    description: Optional desired Spark session resource template; omit to preserve the current template.
    options:
      driver_size: {type: str, description: Driver size.}
      executor_size: {type: str, description: Executor size.}
      executor_nums: {type: int, description: Initial executor count.}
      executor_max_numbers: {type: int, description: Maximum dynamic executor count.}
      running_time_parameters:
        type: list
        elements: dict
        description: Complete runtime parameter set for the session template.
        options:
          key: {type: str, required: true, description: Runtime parameter name.}
          value: {type: str, required: true, description: Runtime parameter value.}
  allow_empty: {type: bool, default: false, description: Explicitly authorize clearing every custom configuration pair.}
  wait: {type: bool, default: true, description: Wait for readable configuration convergence.}
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
- susunola.tencentcloud.dlc_data_engine_config:
    engine_name: production-spark
    config_pairs:
      - {key: spark.sql.adaptive.enabled, value: 'true'}
      - {key: spark.sql.shuffle.partitions, value: '200'}
    session_resource_template:
      driver_size: medium
      executor_size: large
      executor_nums: 2
      executor_max_numbers: 8
"""
RETURN = r"""
data_engine_config: {description: Effective normalized engine configuration., type: dict, returned: always}
engine_id: {description: Resolved DLC data-engine ID., type: str, returned: always}
"""

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def _pairs(values):
    result = []
    for value in values or []:
        key = value.get("ConfigItem", value.get("key"))
        item = value.get("ConfigValue", value.get("value"))
        result.append({"ConfigItem": key, "ConfigValue": item})
    return sorted(result, key=lambda value: (value["ConfigItem"], value["ConfigValue"]))


def _template(value):
    if value is None:
        return None
    source = value if isinstance(value, dict) else value._serialize(allow_none=True)
    mapping = {
        "driver_size": "DriverSize",
        "executor_size": "ExecutorSize",
        "executor_nums": "ExecutorNums",
        "executor_max_numbers": "ExecutorMaxNumbers",
    }
    result = {}
    for local, remote in mapping.items():
        item = source.get(remote, source.get(local))
        if item is not None:
            result[remote] = item
    runtime = source.get("RunningTimeParameters", source.get("running_time_parameters"))
    if runtime is not None:
        result["RunningTimeParameters"] = _pairs(runtime)
    return result


def normalize(value):
    if value is None:
        return None
    source = value if isinstance(value, dict) else value._serialize(allow_none=True)
    return {
        "DataEngineId": source.get("DataEngineId"),
        "DataEngineConfigPairs": _pairs(source.get("DataEngineConfigPairs", source.get("config_pairs"))),
        "SessionResourceTemplate": _template(source.get("SessionResourceTemplate", source.get("session_resource_template"))),
    }


def engine_request(models, name, offset=0):
    request = models.DescribeDataEnginesRequest()
    request.Offset, request.Limit, request.ExcludePublicEngine = offset, 100, True
    item = models.Filter()
    item.Name, item.Values = "data-engine-name", [name]
    request.Filters = [item]
    return request


def resolve_engine_id(module, client, models, p):
    if p.get("engine_id"):
        return p["engine_id"]
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeDataEngines, engine_request(models, p["engine_name"], offset))
        page = response.DataEngines or []
        matches.extend(x.DataEngineId for x in page if x.DataEngineName == p["engine_name"] and x.State != -2)
        offset += len(page)
        if not page or offset >= int(response.TotalCount or 0):
            break
    if not matches:
        module.fail_json(msg="DLC data engine was not found", engine_name=p["engine_name"])
    if len(matches) > 1:
        module.fail_json(msg="Multiple DLC data engines matched the exact name", engine_name=p["engine_name"])
    return matches[0]


def describe_request(models, engine_id, offset=0):
    request = models.DescribeUserDataEngineConfigRequest()
    request.Offset, request.Limit = offset, 100
    item = models.Filter()
    item.Name, item.Values = "engine-id", [engine_id]
    request.Filters = [item]
    return request


def read(module, client, models, engine_id):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeUserDataEngineConfig, describe_request(models, engine_id, offset))
        page = response.DataEngineConfigInstanceInfos or []
        matches.extend(normalize(x) for x in page if x.DataEngineId == engine_id)
        offset += len(page)
        if not page or offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple DLC engine configuration records matched", engine_id=engine_id)
    return matches[0] if matches else {"DataEngineId": engine_id, "DataEngineConfigPairs": [], "SessionResourceTemplate": None}


def desired(p, engine_id, current):
    result = {"DataEngineId": engine_id, "DataEngineConfigPairs": _pairs(p["config_pairs"])}
    result["SessionResourceTemplate"] = (
        _template(p["session_resource_template"]) if p.get("session_resource_template") is not None else current.get("SessionResourceTemplate")
    )
    return result


def update_request(models, target):
    request = models.UpdateUserDataEngineConfigRequest()
    request.DataEngineId = target["DataEngineId"]
    request.DataEngineConfigPairs = []
    for value in target["DataEngineConfigPairs"]:
        item = models.DataEngineConfigPair()
        item.from_json_string(json.dumps(value))
        request.DataEngineConfigPairs.append(item)
    if target.get("SessionResourceTemplate") is not None:
        request.SessionResourceTemplate = models.SessionResourceTemplate()
        request.SessionResourceTemplate.from_json_string(json.dumps(target["SessionResourceTemplate"]))
    return request


def wait_config(module, client, models, p, engine_id, target):
    def poll():
        return "ready" if read(module, client, models, engine_id) == target else "pending"

    wait_for_state(module, poll, ["ready"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    pair = {"key": {"required": True}, "value": {"required": True}}
    template = {
        "driver_size": {},
        "executor_size": {},
        "executor_nums": {"type": "int"},
        "executor_max_numbers": {"type": "int"},
        "running_time_parameters": {"type": "list", "elements": "dict", "options": pair},
    }
    spec = {
        "engine_id": {},
        "engine_name": {},
        "config_pairs": {"type": "list", "elements": "dict", "required": True, "options": pair},
        "session_resource_template": {"type": "dict", "options": template},
        "allow_empty": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 3},
        "waiter_timeout": {"type": "int", "default": 180},
    }
    module = TencentCloudModule(
        argument_spec=spec, required_one_of=[("engine_id", "engine_name")], mutually_exclusive=[("engine_id", "engine_name")], supports_check_mode=True
    )
    p = module.params
    target_pairs = _pairs(p["config_pairs"])
    if len({x["ConfigItem"] for x in target_pairs}) != len(target_pairs):
        module.fail_json(msg="config_pairs contains duplicate keys")
    if not target_pairs and not p["allow_empty"]:
        module.fail_json(msg="set allow_empty=true to authorize clearing all DLC engine configuration pairs")
    runtime = (p.get("session_resource_template") or {}).get("running_time_parameters")
    if runtime is not None and len({x["key"] for x in runtime}) != len(runtime):
        module.fail_json(msg="running_time_parameters contains duplicate keys")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        engine_id = resolve_engine_id(module, client, models, p)
        current = read(module, client, models, engine_id)
        target = desired(p, engine_id, current)
        if current == target:
            module.exit_json(changed=False, data_engine_config=current, engine_id=engine_id)
        diff_value = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.UpdateUserDataEngineConfig, update_request(models, target))
            if p["wait"]:
                wait_config(module, client, models, p, engine_id, target)
            current = read(module, client, models, engine_id)
        module.exit_json(changed=True, **(diff_value or {}), data_engine_config=current if not module.check_mode else target, engine_id=engine_id)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
