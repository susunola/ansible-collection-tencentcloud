#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_resource_config
short_description: Manage Tencent Cloud DLC Ray and Spark resource templates
version_added: "0.14.0"
description:
  - Creates, updates and deletes reusable DLC Head and Worker resource templates.
  - Worker sets, environment variables and labels are order-insensitive and capacity reduction is guarded.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired lifecycle state.}
  name: {type: str, required: true, description: Exact template name and immutable identity.}
  template_type: {type: str, choices: [Ray, ray, Spark, spark], description: Template workload type.}
  description: {type: str, description: Template description.}
  head: {type: dict, description: HeadSpecDTO-compatible Head node configuration using snake_case or SDK field names.}
  workers: {type: list, elements: dict, description: Exact WorkerSpecDTO-compatible Worker set using snake_case or SDK field names.}
  allow_scale_down: {type: bool, default: false, description: Explicitly authorize reducing Head or Worker capacity or removing Workers.}
  allow_delete: {type: bool, default: false, description: Explicitly authorize template deletion.}
  allow_delete_in_use: {type: bool, default: false, description: Explicitly authorize deletion while Labs or Ray clusters reference the template.}
  wait: {type: bool, default: true, description: Wait for lifecycle and field convergence.}
  waiter_delay: {type: int, default: 5, description: Seconds between polls.}
  waiter_timeout: {type: int, default: 300, description: Overall convergence timeout.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_resource_config:
    name: analytics-ray-small
    template_type: Ray
    description: Shared notebook and Ray template
    head:
      name: head
      pod_cpu: 4
      pod_mem: 16
      pod_num: 1
      resource_type: CPU
      spec: 4
      billing_item: sv_dlc_standard_cu_standard_cu
    workers:
      - name: workers
        pod_cpu: 4
        pod_mem: 16
        min_pod_num: 1
        max_pod_num: 8
        enable_auto_scaling: true
        resource_type: CPU
        spec: 4
        billing_item: sv_dlc_standard_cu_standard_cu

- susunola.tencentcloud.dlc_resource_config:
    name: analytics-ray-small
    state: absent
    allow_delete: true
"""
RETURN = r"""
resource_config:
  description: Effective DLC resource template metadata.
  type: dict
  returned: always
resource_config_id:
  description: DLC resource template ID.
  type: str
  returned: when present
references:
  description: Labs and Ray clusters referencing the template during deletion.
  type: list
  returned: when deletion is blocked
"""

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state

NODE_FIELDS = {
    "name": "Name",
    "pod_cpu": "PodCpu",
    "pod_mem": "PodMem",
    "gpu_type": "GpuType",
    "gpu_num": "GpuNum",
    "envs": "Envs",
    "labels": "Labels",
    "resources_labels": "ResourcesLabels",
    "pod_num": "PodNum",
    "high_availability": "HighAvailability",
    "min_pod_num": "MinPodNum",
    "max_pod_num": "MaxPodNum",
    "enable_auto_scaling": "EnableAutoScaling",
    "resource_type": "ResourceType",
    "instance_type": "InstanceType",
    "spec": "Spec",
    "billing_item": "BillingItem",
}
CAPACITY = ("PodCpu", "PodMem", "GpuNum", "PodNum", "MinPodNum", "MaxPodNum", "Spec")


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def list_request(models, page=1, ray=False):
    request = models.ListRayClustersRequest() if ray else models.ListResourceConfigsRequest()
    request.Page, request.PageSize = page, 200
    return request


def _pairs(values):
    result = []
    for item in values or []:
        result.append({"Name": item.get("Name", item.get("name")), "Value": item.get("Value", item.get("value"))})
    return sorted(result, key=lambda x: (x["Name"], x["Value"]))


def node(value):
    if value is None:
        return None
    result = {}
    for source, target in NODE_FIELDS.items():
        current = value.get(target, value.get(source))
        if target in ("Envs", "Labels", "ResourcesLabels"):
            if current:
                result[target] = _pairs(current)
        elif current is not None:
            result[target] = current
    return result


def workers(values):
    return sorted((node(item) for item in (values or [])), key=lambda x: x.get("Name", ""))


def normalize(value):
    result = dict(value or {})
    if "Head" in result:
        result["Head"] = node(result["Head"])
    if "Worker" in result:
        result["Worker"] = workers(result["Worker"])
    return result


def find(module, client, models, name):
    page, matches = 1, []
    while True:
        response = module.sdk_call(client.ListResourceConfigs, list_request(models, page))
        items = response.Items or []
        matches.extend(x._serialize(allow_none=True) for x in items if x.Name == name)
        if not items or page >= int(response.TotalPages or 1):
            break
        page += 1
    if len(matches) > 1:
        module.fail_json(msg="Multiple DLC resource templates matched the exact name", name=name)
    return normalize(matches[0]) if matches else None


def payload(p, config_id=None):
    result = {"Name": p["name"]}
    if config_id:
        result["Id"] = config_id
    if p.get("description") is not None:
        result["Description"] = p["description"]
    if p.get("template_type") is not None:
        result["Type"] = p["template_type"]
    if p.get("head") is not None:
        result["Head"] = node(p["head"])
    if p.get("workers") is not None:
        result["Worker"] = workers(p["workers"])
    return result


def make_request(models, p, update=False, config_id=None):
    request = models.UpdateResourceConfigRequest() if update else models.CreateResourceConfigRequest()
    request.from_json_string(json.dumps(payload(p, config_id)))
    return request


def delete_request(models, config_id):
    request = models.DeleteResourceConfigRequest()
    request.Id = config_id
    return request


def desired(p, current=None):
    result = dict(current or {})
    result["Name"] = p["name"]
    if p.get("description") is not None:
        result["Description"] = p["description"]
    if p.get("template_type") is not None:
        result["Type"] = p["template_type"]
    if p.get("head") is not None:
        result["Head"] = node(p["head"])
    if p.get("workers") is not None:
        result["Worker"] = workers(p["workers"])
    return result


def drift(p, current):
    target, changes = desired(p, current), {}
    for source, key in (("description", "Description"), ("template_type", "Type"), ("head", "Head"), ("workers", "Worker")):
        if p.get(source) is not None and current.get(key) != target.get(key):
            changes[key] = (current.get(key), target.get(key))
    return changes


def scale_down(old_head, new_head, old_workers, new_workers):
    def lower(old, new):
        return any(old.get(k) is not None and new.get(k) is not None and new[k] < old[k] for k in CAPACITY)

    if old_head and new_head and lower(old_head, new_head):
        return True
    before = {x.get("Name"): x for x in old_workers or []}
    after = {x.get("Name"): x for x in new_workers or []}
    if set(before) - set(after):
        return True
    return any(name in before and lower(before[name], item) for name, item in after.items())


def references(module, client, models, config_id):
    found = []
    for kind, method, ray in (("lab", client.ListLabs, False), ("ray_cluster", client.ListRayClusters, True)):
        page = 1
        while True:
            request = list_request(models, page, ray=ray) if ray else models.ListLabsRequest()
            if not ray:
                request.Page, request.PageSize = page, 200
            response = module.sdk_call(method, request)
            items = response.Items or []
            found.extend({"type": kind, "id": x.Id, "name": x.Name} for x in items if x.ResourceConfigId == config_id)
            if not items or page >= int(response.TotalPages or 1):
                break
            page += 1
    return found


def wait_config(module, client, models, p, absent=False, expected=None):
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
        "template_type": {"choices": ["Ray", "ray", "Spark", "spark"]},
        "description": {},
        "head": {"type": "dict"},
        "workers": {"type": "list", "elements": "dict"},
        "allow_scale_down": {"type": "bool", "default": False},
        "allow_delete": {"type": "bool", "default": False},
        "allow_delete_in_use": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 5},
        "waiter_timeout": {"type": "int", "default": 300},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    worker_names = [node(x).get("Name") for x in p.get("workers") or []]
    if None in worker_names or len(worker_names) != len(set(worker_names)):
        module.fail_json(msg="each worker requires a unique name")
    for item in p.get("workers") or []:
        value = node(item)
        if value.get("MinPodNum") is not None and value.get("MaxPodNum") is not None and value["MinPodNum"] > value["MaxPodNum"]:
            module.fail_json(msg="worker min_pod_num must not exceed max_pod_num", worker=value)
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["name"])
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, resource_config=None, resource_config_id=None)
            if not p["allow_delete"]:
                module.fail_json(msg="set allow_delete=true to authorize deleting the DLC resource template", resource_config=current)
            refs = references(module, client, models, current["Id"])
            if refs and not p["allow_delete_in_use"]:
                module.fail_json(
                    msg="set allow_delete_in_use=true to delete a DLC resource template referenced by Labs or Ray clusters",
                    references=refs,
                    resource_config=current,
                )
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteResourceConfig, delete_request(models, current["Id"]))
                if p["wait"]:
                    wait_config(module, client, models, p, absent=True)
            module.exit_json(changed=True, **(diff_value or {}), resource_config=None, resource_config_id=None)
        if not current:
            missing = [key for key in ("template_type", "head", "workers") if p.get(key) is None]
            if missing:
                module.fail_json(msg="creation parameters are required for a DLC resource template", missing=missing)
            after, diff_value = desired(p), maybe_diff(module, None, desired(p))
            config_id = None
            if not module.check_mode:
                config_id = module.sdk_call(client.CreateResourceConfig, make_request(models, p)).Id
                if p["wait"]:
                    wait_config(module, client, models, p, expected={k: v for k, v in after.items() if k != "Name"})
                current = find(module, client, models, p["name"])
            module.exit_json(
                changed=True,
                **(diff_value or {}),
                resource_config=current if not module.check_mode else after,
                resource_config_id=(current or {}).get("Id") or config_id,
            )
        changes = drift(p, current)
        after = desired(p, current)
        if (
            ("Head" in changes or "Worker" in changes)
            and scale_down(current.get("Head"), after.get("Head"), current.get("Worker"), after.get("Worker"))
            and not p["allow_scale_down"]
        ):
            module.fail_json(
                msg="set allow_scale_down=true to authorize reducing DLC resource-template capacity",
                capacity_drift={k: v for k, v in changes.items() if k in ("Head", "Worker")},
            )
        if not changes:
            module.exit_json(changed=False, resource_config=current, resource_config_id=current.get("Id"))
        diff_value = maybe_diff(module, current, after)
        if not module.check_mode:
            module.sdk_call(client.UpdateResourceConfig, make_request(models, p, update=True, config_id=current["Id"]))
            if p["wait"]:
                wait_config(module, client, models, p, expected={k: v[1] for k, v in changes.items()})
            current = find(module, client, models, p["name"])
        module.exit_json(changed=True, **(diff_value or {}), resource_config=current if not module.check_mode else after, resource_config_id=current.get("Id"))
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
