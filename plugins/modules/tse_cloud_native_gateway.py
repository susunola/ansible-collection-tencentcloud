#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_cloud_native_gateway
short_description: Manage a Tencent Cloud TSE cloud-native API gateway
version_added: "0.14.0"
description: Creates, updates and deletes cloud-native API gateways with topology drift protection and node specification reconciliation.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  gateway_id: {type: str, description: Existing gateway ID.}
  name: {type: str, description: Gateway name.}
  gateway_type: {type: str, choices: [kong], default: kong, description: Gateway engine type.}
  gateway_version: {type: str, description: Gateway engine version.}
  node_config: {type: dict, description: SDK CloudNativeAPIGatewayNodeConfig payload.}
  spec_group_id: {type: str, description: Gateway group ID used when changing node_config on an existing gateway. The group must be the default group represented by the gateway NodeConfig readback.}
  vpc_config: {type: dict, description: SDK CloudNativeAPIGatewayVpcConfig payload.}
  description: {type: str, description: Gateway description.}
  tags: {type: list, elements: dict, description: SDK InstanceTagInfo entries.}
  enable_cls: {type: bool, description: Enable CLS logging; the API cannot disable it after activation.}
  feature_version: {type: str, choices: [TRIAL, STANDARD, PROFESSIONAL], description: Product edition.}
  internet_max_bandwidth_out: {type: int, description: Public egress bandwidth in Mbps.}
  ingress_class_name: {type: str, description: Ingress class name.}
  trade_type: {type: int, choices: [0, 1], description: Postpaid or prepaid billing; creation defaults to postpaid.}
  internet_config: {type: dict, description: SDK InternetConfig payload.}
  prometheus_id: {type: str, description: Associated Prometheus instance ID.}
  internet_pay_mode: {type: str, choices: [BANDWIDTH, TRAFFIC], description: Public network billing mode.}
  delete_protect: {type: bool, description: Enable deletion protection.}
  delete_cls_topic: {type: bool, default: false, description: Delete the associated CLS topic with the gateway.}

  waiter_delay: {type: int, default: 5, description: Polling interval.}
  waiter_timeout: {type: int, default: 600, description: Convergence timeout.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_cloud_native_gateway:
    gateway_id: gateway-xxxxxxxx
    name: production-gateway
    node_config: {Specification: 4c8g, Number: 4}
    spec_group_id: group-xxxxxxxx
"""
RETURN = r"""
gateway: {description: Effective gateway metadata., type: dict, returned: always}
task_id: {description: Tencent Cloud asynchronous task ID for a node specification change., type: str, returned: when node_config changes}
"""
import json
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def list_request(models, p):
    r = models.DescribeCloudNativeAPIGatewaysRequest()
    r.Offset, r.Limit = 0, 100
    if p.get("gateway_id") or p.get("name"):
        f = models.Filter()
        f.Name, f.Values = ("GatewayId", [p["gateway_id"]]) if p.get("gateway_id") else ("Name", [p["name"]])
        r.Filters = [f]
    return r


def detail_request(models, gateway_id):
    r = models.DescribeCloudNativeAPIGatewayRequest()
    r.GatewayId = gateway_id
    return r


def create_request(models, p):
    payload = {
        "Name": p["name"],
        "Type": p["gateway_type"],
        "GatewayVersion": p["gateway_version"],
        "NodeConfig": p["node_config"],
        "VpcConfig": p["vpc_config"],
        "Description": p.get("description"),
        "Tags": p.get("tags"),
        "EnableCls": p.get("enable_cls"),
        "FeatureVersion": p.get("feature_version"),
        "InternetMaxBandwidthOut": p.get("internet_max_bandwidth_out"),
        "EngineRegion": p["region"],
        "IngressClassName": p.get("ingress_class_name"),
        "TradeType": p["trade_type"],
        "InternetConfig": p.get("internet_config"),
        "PromId": p.get("prometheus_id"),
    }
    r = models.CreateCloudNativeAPIGatewayRequest()
    r.from_json_string(json.dumps({k: v for k, v in payload.items() if v is not None}))
    return r


def update_request(models, gateway_id, target):
    r = models.ModifyCloudNativeAPIGatewayRequest()
    r.GatewayId = gateway_id
    r.Name, r.Description, r.EnableCls = target["Name"], target.get("Description"), target.get("EnableCls")
    r.InternetPayMode, r.DeleteProtect = target.get("InternetPayMode"), target.get("DeleteProtect")
    return r


def spec_request(models, gateway_id, group_id, node_config):
    payload = {"GatewayId": gateway_id, "GroupId": group_id, "NodeConfig": node_config}
    r = models.UpdateCloudNativeAPIGatewaySpecRequest()
    r.from_json_string(json.dumps(payload))
    return r


def delete_request(models, p, gateway_id):
    r = models.DeleteCloudNativeAPIGatewayRequest()
    r.GatewayId, r.DeleteClsTopic = gateway_id, p["delete_cls_topic"]
    return r


def find(module, client, models, p):
    result = module.sdk_call(client.DescribeCloudNativeAPIGateways, list_request(models, p)).Result
    values = result.GatewayList if result else []
    matches = []
    for item in values or []:
        value = item._serialize(allow_none=True)
        if (p.get("gateway_id") and value.get("GatewayId") == p["gateway_id"]) or (not p.get("gateway_id") and value.get("Name") == p.get("name")):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE gateways matched; specify gateway_id")
    if not matches:
        return None
    detail = module.sdk_call(client.DescribeCloudNativeAPIGateway, detail_request(models, matches[0]["GatewayId"])).Result
    return detail._serialize(allow_none=True) if detail else matches[0]


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and contains(actual[k], v) for k, v in expected.items())
    return actual == expected


def wait(module, client, models, p, gateway_id, expected=None):
    deadline = time.time() + p["waiter_timeout"]
    p["gateway_id"] = gateway_id
    while True:
        value = find(module, client, models, p)
        status = str((value or {}).get("Status") or "").lower()
        if status in ("running", "run", "success") and (expected is None or contains(value, expected)):
            return value
        if status in ("failed", "create_failed", "update_failed"):
            module.fail_json(msg="TSE gateway operation failed", gateway=value)
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for TSE gateway convergence", gateway=value)
        time.sleep(p["waiter_delay"])


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "gateway_id": {},
        "name": {},
        "gateway_type": {"choices": ["kong"], "default": "kong"},
        "gateway_version": {},
        "node_config": {"type": "dict"},
        "spec_group_id": {},
        "vpc_config": {"type": "dict"},
        "description": {},
        "tags": {"type": "list", "elements": "dict"},
        "enable_cls": {"type": "bool"},
        "feature_version": {"choices": ["TRIAL", "STANDARD", "PROFESSIONAL"]},
        "internet_max_bandwidth_out": {"type": "int"},
        "ingress_class_name": {},
        "trade_type": {"type": "int", "choices": [0, 1]},
        "internet_config": {"type": "dict"},
        "prometheus_id": {},
        "internet_pay_mode": {"choices": ["BANDWIDTH", "TRAFFIC"]},
        "delete_protect": {"type": "bool"},
        "delete_cls_topic": {"type": "bool", "default": False},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("gateway_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, gateway=None)
            if current.get("DeleteProtect"):
                module.fail_json(msg="Disable delete_protect before deleting the TSE gateway", gateway_id=current["GatewayId"])
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteCloudNativeAPIGateway, delete_request(models, p, current["GatewayId"]))
            module.exit_json(changed=True, **(diff or {}), gateway=None)
        if not current:
            missing = [k for k in ("name", "gateway_version", "node_config", "vpc_config", "feature_version") if p.get(k) is None]
            if missing:
                module.fail_json(msg="creation parameters are required for a TSE gateway", missing=missing)
            target = {
                "Name": p["name"],
                "Type": p["gateway_type"],
                "GatewayVersion": p["gateway_version"],
                "NodeConfig": p["node_config"],
                "VpcConfig": p["vpc_config"],
                "FeatureVersion": p["feature_version"],
            }
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                response = module.sdk_call(client.CreateCloudNativeAPIGateway, create_request(models, p))
                gateway_id = response.Result.GatewayId
                current = wait(module, client, models, p, gateway_id)
            module.exit_json(changed=True, **(diff or {}), gateway=current if not module.check_mode else target)
        before = {k: current.get(k) for k in ("Name", "Description", "EnableCls", "InternetPayMode", "DeleteProtect")}
        target = dict(before)
        for source, key in (
            ("name", "Name"),
            ("description", "Description"),
            ("enable_cls", "EnableCls"),
            ("internet_pay_mode", "InternetPayMode"),
            ("delete_protect", "DeleteProtect"),
        ):
            if p.get(source) is not None:
                target[key] = p[source]
        immutable = {
            "Type": p.get("gateway_type"),
            "GatewayVersion": p.get("gateway_version"),
            "VpcConfig": p.get("vpc_config"),
            "FeatureVersion": p.get("feature_version"),
            "TradeType": p.get("trade_type"),
            "IngressClassName": p.get("ingress_class_name"),
        }
        desired_immutable = {k: v for k, v in immutable.items() if v is not None}
        drift = {k: (current.get(k), v) for k, v in desired_immutable.items() if not contains(current.get(k), v)}
        if drift:
            module.fail_json(msg="TSE gateway topology and billing identity are immutable", immutable_drift=drift)
        if current.get("EnableCls") and target.get("EnableCls") is False:
            module.fail_json(msg="TSE API cannot disable CLS after it has been enabled")
        node_changed = p.get("node_config") is not None and not contains(current.get("NodeConfig"), p["node_config"])
        if node_changed and not p.get("spec_group_id"):
            module.fail_json(msg="spec_group_id is required to change node_config on an existing TSE gateway", gateway_id=current["GatewayId"])
        metadata_changed = before != target
        if not metadata_changed and not node_changed:
            module.exit_json(changed=False, gateway=current)
        desired = dict(target)
        diff_before = dict(before)
        if p.get("node_config") is not None:
            desired["NodeConfig"] = p["node_config"]
            diff_before["NodeConfig"] = current.get("NodeConfig")
        diff = maybe_diff(module, diff_before, desired)
        task_id = None
        if not module.check_mode:
            if metadata_changed:
                module.sdk_call(client.ModifyCloudNativeAPIGateway, update_request(models, current["GatewayId"], target))
            if node_changed:
                response = module.sdk_call(
                    client.UpdateCloudNativeAPIGatewaySpec, spec_request(models, current["GatewayId"], p["spec_group_id"], p["node_config"])
                )
                task_id = getattr(getattr(response, "Result", None), "TaskId", None)
            current = wait(module, client, models, p, current["GatewayId"], desired)
        module.exit_json(changed=True, **(diff or {}), gateway=current if not module.check_mode else desired, task_id=task_id)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
