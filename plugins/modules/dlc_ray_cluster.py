#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: dlc_ray_cluster
short_description: Manage Tencent Cloud DLC Ray clusters
version_added: "0.14.0"
description:
  - Creates, updates and deletes persistent DLC Ray clusters.
  - Uses exact-name discovery with stable ID updates and normalized JSON and tag comparison.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired lifecycle state.}
  name: {type: str, required: true, description: Exact cluster name and immutable identity.}
  description: {type: str, description: Cluster description.}
  group_id: {type: str, description: Compute group ID.}
  resource_partition_id: {type: str, description: Resource partition ID.}
  queue: {type: str, description: Resource partition queue name.}
  image: {type: str, description: Ray cluster image.}
  image_pull_policy: {type: str, choices: [Always, IfNotPresent, Never], description: Image pull policy.}
  image_pull_type: {type: str, choices: [BuiltIn, Custom, CustomCcr], description: Image source type.}
  resource_config: {type: str, description: Inline resource configuration JSON.}
  resource_config_id: {type: str, description: Reusable resource-template ID.}
  catalog: {type: str, description: Volume and mount configuration JSON.}
  advanced_options: {type: str, description: Flattened Ray cluster options JSON.}
  priority: {type: int, description: Scheduling priority from 1 to 9.}
  tags:
    type: list
    elements: dict
    description: Exact Tencent Cloud tag set.
    options:
      key: {type: str, required: true, description: Tag key.}
      value: {type: str, required: true, description: Tag value.}
  allow_delete: {type: bool, default: false, description: Explicitly authorize cluster deletion.}
  wait: {type: bool, default: true, description: Wait for lifecycle and field convergence.}
  waiter_delay: {type: int, default: 10, description: Seconds between polls.}
  waiter_timeout: {type: int, default: 1800, description: Overall convergence timeout.}
  retries: {type: int, default: 5, description: Retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.dlc_ray_cluster:
    name: analytics-ray
    resource_partition_id: rp-xxxxxxxx
    queue: notebooks
    image: ccr.ccs.tencentyun.com/dlc/ray:latest
    image_pull_type: BuiltIn
    resource_config_id: rc-xxxxxxxx
    priority: 5
    tags:
      - {key: environment, value: production}

- susunola.tencentcloud.dlc_ray_cluster:
    name: analytics-ray
    state: absent
    allow_delete: true
'''
RETURN = r'''
ray_cluster:
  description: Effective DLC Ray cluster metadata.
  type: dict
  returned: always
ray_cluster_id:
  description: DLC Ray cluster ID.
  type: str
  returned: when present
'''

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state

FIELDS = {
    "description": "Description", "group_id": "GroupId", "resource_partition_id": "ResourcePartitionId",
    "queue": "Queue", "image": "Image", "image_pull_policy": "ImagePullPolicy", "image_pull_type": "ImagePullType",
    "resource_config": "ResourceConfig", "resource_config_id": "ResourceConfigId", "catalog": "Catalog",
    "advanced_options": "AdvancedOptions", "priority": "Priority", "tags": "Tags",
}
JSON_FIELDS = {"resource_config", "catalog", "advanced_options"}


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client
    return models, dlc_client


def list_request(models, page=1):
    request = models.ListRayClustersRequest(); request.Page, request.PageSize = page, 200; return request


def _canonical(value):
    if value is None: return None
    try: return json.dumps(json.loads(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError): return value


def _tags(value):
    result = []
    for item in value or []:
        result.append({"TagKey": item.get("TagKey", item.get("key")), "TagValue": item.get("TagValue", item.get("value"))})
    return sorted(result, key=lambda x: (x["TagKey"], x["TagValue"]))


def normalize(value):
    result = dict(value or {}); result["Tags"] = _tags(result.get("Tags"))
    for key in ("ResourceConfig", "Catalog", "AdvancedOptions"):
        if key in result: result[key] = _canonical(result[key])
    return result


def find(module, client, models, name):
    page, matches = 1, []
    while True:
        response = module.sdk_call(client.ListRayClusters, list_request(models, page)); items = response.Items or []
        matches.extend(x._serialize(allow_none=True) for x in items if x.Name == name and x.Type in (None, "CLUSTER"))
        if not items or page >= int(response.TotalPages or 1): break
        page += 1
    if len(matches) > 1: module.fail_json(msg="Multiple DLC Ray clusters matched the exact name", name=name)
    return normalize(matches[0]) if matches else None


def payload(p, cluster_id=None):
    result = {"Name": p["name"]}
    if cluster_id: result["Id"] = cluster_id
    for source, target in FIELDS.items():
        if p.get(source) is not None:
            value = _tags(p[source]) if source == "tags" else (_canonical(p[source]) if source in JSON_FIELDS else p[source])
            result[target] = value
    return result


def make_request(models, p, update=False, cluster_id=None):
    request = models.UpdateRayClusterRequest() if update else models.CreateRayClusterRequest()
    request.from_json_string(json.dumps(payload(p, cluster_id))); return request


def delete_request(models, cluster_id):
    request = models.DeleteRayClusterRequest(); request.Id = cluster_id; return request


def desired(p, current=None):
    result = dict(current or {}); result["Name"] = p["name"]
    for source, target in FIELDS.items():
        if p.get(source) is not None:
            result[target] = _tags(p[source]) if source == "tags" else (_canonical(p[source]) if source in JSON_FIELDS else p[source])
    return result


def drift(p, current):
    target, changes = desired(p, current), {}
    for source, key in FIELDS.items():
        if p.get(source) is not None and current.get(key) != target.get(key): changes[key] = (current.get(key), target.get(key))
    return changes


def wait_cluster(module, client, models, p, absent=False, expected=None):
    def poll():
        current = find(module, client, models, p["name"])
        if absent: return "absent" if current is None else "pending"
        if current is None: return "absent"
        status = str(current.get("Status") or "").upper()
        if "FAIL" in status or "ERROR" in status: module.fail_json(msg="DLC Ray cluster entered a failed state", ray_cluster=current)
        if expected and any(current.get(k) != v for k, v in expected.items()): return "pending"
        return "ready"
    wait_for_state(module, poll, ["absent" if absent else "ready"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    tag_options = {"key": {"required": True}, "value": {"required": True}}
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"}, "name": {"required": True}, "description": {}, "group_id": {},
        "resource_partition_id": {}, "queue": {}, "image": {}, "image_pull_policy": {"choices": ["Always", "IfNotPresent", "Never"]},
        "image_pull_type": {"choices": ["BuiltIn", "Custom", "CustomCcr"]}, "resource_config": {}, "resource_config_id": {},
        "catalog": {}, "advanced_options": {}, "priority": {"type": "int"},
        "tags": {"type": "list", "elements": "dict", "options": tag_options}, "allow_delete": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True}, "waiter_delay": {"type": "int", "default": 10}, "waiter_timeout": {"type": "int", "default": 1800},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True); p = module.params
    if p.get("priority") is not None and not 1 <= p["priority"] <= 9: module.fail_json(msg="priority must be between 1 and 9")
    if p.get("resource_config") is not None and p.get("resource_config_id") is not None: module.fail_json(msg="resource_config and resource_config_id are mutually exclusive")
    for key in JSON_FIELDS:
        if p.get(key) is not None:
            try: json.loads(p[key])
            except (TypeError, ValueError): module.fail_json(msg="%s must be valid JSON" % key)
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["name"])
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, ray_cluster=None, ray_cluster_id=None)
            if not p["allow_delete"]: module.fail_json(msg="set allow_delete=true to authorize deleting the DLC Ray cluster", ray_cluster=current)
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteRayCluster, delete_request(models, current["Id"]))
                if p["wait"]: wait_cluster(module, client, models, p, absent=True)
            module.exit_json(changed=True, **(diff_value or {}), ray_cluster=None, ray_cluster_id=None)
        if not current:
            required = ("resource_partition_id", "queue", "image", "image_pull_type")
            missing = [key for key in required if not p.get(key)]
            if not p.get("resource_config") and not p.get("resource_config_id"): missing.append("resource_config or resource_config_id")
            if missing: module.fail_json(msg="creation parameters are required for a DLC Ray cluster", missing=missing)
            after, diff_value = desired(p), maybe_diff(module, None, desired(p)); cluster_id = None
            if not module.check_mode:
                cluster_id = module.sdk_call(client.CreateRayCluster, make_request(models, p)).Id
                if p["wait"]: wait_cluster(module, client, models, p, expected={k: v for k, v in after.items() if k != "Name"})
                current = find(module, client, models, p["name"])
            module.exit_json(changed=True, **(diff_value or {}), ray_cluster=current if not module.check_mode else after, ray_cluster_id=(current or {}).get("Id") or cluster_id)
        changes = drift(p, current)
        if not changes: module.exit_json(changed=False, ray_cluster=current, ray_cluster_id=current.get("Id"))
        after, diff_value = desired(p, current), maybe_diff(module, current, desired(p, current))
        if not module.check_mode:
            module.sdk_call(client.UpdateRayCluster, make_request(models, p, update=True, cluster_id=current["Id"]))
            if p["wait"]: wait_cluster(module, client, models, p, expected={k: v[1] for k, v in changes.items()})
            current = find(module, client, models, p["name"])
        module.exit_json(changed=True, **(diff_value or {}), ray_cluster=current if not module.check_mode else after, ray_cluster_id=current.get("Id"))
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
