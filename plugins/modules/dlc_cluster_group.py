#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_cluster_group
short_description: Manage Tencent Cloud DLC compute cluster groups
version_added: "0.14.0"
description:
  - Creates, updates and deletes DLC compute cluster groups used by persistent Ray clusters and laboratories.
  - Uses exact-name discovery, stable ID mutations, semantic JSON comparison and reference-aware deletion.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired lifecycle state.}
  name: {type: str, required: true, description: Exact cluster-group name and identity.}
  description: {type: str, description: Cluster-group description.}
  config: {type: str, description: Cluster-group configuration as a JSON document.}
  allow_delete: {type: bool, default: false, description: Explicitly authorize cluster-group deletion.}
  force_detach: {type: bool, default: false, description: Explicitly detach active clusters while deleting the group.}
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
- susunola.tencentcloud.dlc_cluster_group:
    name: shared-ray-compute
    description: Shared managed compute group
    config: '{"dispatchStrategy":"RANDOM"}'

- susunola.tencentcloud.dlc_cluster_group:
    name: shared-ray-compute
    state: absent
    allow_delete: true
"""
RETURN = r"""
cluster_group:
  description: Effective DLC cluster-group metadata.
  type: dict
  returned: always
cluster_group_id:
  description: DLC cluster-group ID.
  type: str
  returned: when present
active_clusters:
  description: Active cluster count and samples observed before deletion.
  type: dict
  returned: when deletion is considered
"""

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def canonical(value):
    if value is None:
        return None
    try:
        return json.dumps(json.loads(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError):
        return value


def normalize(value):
    result = dict(value or {})
    if "Config" in result:
        result["Config"] = canonical(result["Config"])
    return result


def list_request(models, page=1):
    request = models.ListClusterGroupsRequest()
    request.Page, request.PageSize = page, 200
    return request


def find(module, client, models, name):
    page, matches = 1, []
    while True:
        response = module.sdk_call(client.ListClusterGroups, list_request(models, page))
        items = response.Items or []
        matches.extend(x._serialize(allow_none=True) for x in items if x.Name == name and not x.Deleted)
        if not items or page >= int(response.TotalPages or 1):
            break
        page += 1
    if len(matches) > 1:
        module.fail_json(msg="Multiple active DLC cluster groups matched the exact name", name=name)
    return normalize(matches[0]) if matches else None


def desired(p, current=None):
    result = dict(current or {})
    result["Name"] = p["name"]
    if p.get("description") is not None:
        result["Description"] = p["description"]
    if p.get("config") is not None:
        result["Config"] = canonical(p["config"])
    return result


def drift(p, current):
    target, changes = desired(p, current), {}
    for source, key in (("description", "Description"), ("config", "Config")):
        if p.get(source) is not None and current.get(key) != target.get(key):
            changes[key] = (current.get(key), target.get(key))
    return changes


def make_request(models, p, update=False, group_id=None):
    request = models.UpdateClusterGroupRequest() if update else models.CreateClusterGroupRequest()
    payload = {"Name": p["name"]}
    if group_id:
        payload["Id"] = group_id
    if p.get("description") is not None:
        payload["Description"] = p["description"]
    if p.get("config") is not None:
        payload["Config"] = canonical(p["config"])
    request.from_json_string(json.dumps(payload))
    return request


def cluster_request(models, group_id):
    request = models.DescribeClusterGroupClustersRequest()
    request.Id, request.SampleLimit = group_id, 20
    return request


def active_clusters(module, client, models, group_id):
    response = module.sdk_call(client.DescribeClusterGroupClusters, cluster_request(models, group_id))
    return {
        "count": int(response.Count or 0),
        "samples": [x._serialize(allow_none=True) for x in (response.SampleClusters or [])],
    }


def delete_request(models, group_id, force=False):
    request = models.DeleteClusterGroupRequest()
    request.Id, request.Force = group_id, force
    return request


def wait_group(module, client, models, p, absent=False, expected=None):
    def poll():
        current = find(module, client, models, p["name"])
        if absent:
            return "absent" if current is None else "pending"
        if current is None:
            return "absent"
        if expected and any(current.get(key) != value for key, value in expected.items()):
            return "pending"
        return "ready"

    wait_for_state(module, poll, ["absent" if absent else "ready"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "name": {"required": True},
        "description": {},
        "config": {},
        "allow_delete": {"type": "bool", "default": False},
        "force_detach": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 5},
        "waiter_timeout": {"type": "int", "default": 300},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if p.get("config") is not None:
        try:
            json.loads(p["config"])
        except (TypeError, ValueError):
            module.fail_json(msg="config must be valid JSON")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["name"])
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, cluster_group=None, cluster_group_id=None)
            if not p["allow_delete"]:
                module.fail_json(msg="set allow_delete=true to authorize deleting the DLC cluster group", cluster_group=current)
            refs = active_clusters(module, client, models, current["Id"])
            if refs["count"] and not p["force_detach"]:
                module.fail_json(
                    msg="DLC cluster group still has active clusters; set force_detach=true to detach them", cluster_group=current, active_clusters=refs
                )
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteClusterGroup, delete_request(models, current["Id"], p["force_detach"]))
                if p["wait"]:
                    wait_group(module, client, models, p, absent=True)
            module.exit_json(changed=True, **(diff_value or {}), cluster_group=None, cluster_group_id=None, active_clusters=refs)
        if not current:
            after, diff_value, group_id = desired(p), maybe_diff(module, None, desired(p)), None
            if not module.check_mode:
                group_id = module.sdk_call(client.CreateClusterGroup, make_request(models, p)).Id
                if p["wait"]:
                    wait_group(module, client, models, p, expected={k: v for k, v in after.items() if k != "Name"})
                current = find(module, client, models, p["name"])
            module.exit_json(
                changed=True,
                **(diff_value or {}),
                cluster_group=current if not module.check_mode else after,
                cluster_group_id=(current or {}).get("Id") or group_id,
            )
        changes = drift(p, current)
        if not changes:
            module.exit_json(changed=False, cluster_group=current, cluster_group_id=current.get("Id"))
        after, diff_value = desired(p, current), maybe_diff(module, current, desired(p, current))
        if not module.check_mode:
            module.sdk_call(client.UpdateClusterGroup, make_request(models, p, update=True, group_id=current["Id"]))
            if p["wait"]:
                wait_group(module, client, models, p, expected={k: v[1] for k, v in changes.items()})
            current = find(module, client, models, p["name"])
        module.exit_json(changed=True, **(diff_value or {}), cluster_group=current if not module.check_mode else after, cluster_group_id=current.get("Id"))
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
