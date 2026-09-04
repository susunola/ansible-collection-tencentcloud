#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tcm_mesh
short_description: Manage Tencent Cloud Mesh instances
version_added: "0.14.0"
description: Creates, updates and deletes Tencent Cloud Mesh instances.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  mesh_id: {type: str, description: Existing mesh ID.}
  name: {type: str, description: Mesh display name.}
  mesh_version: {type: str, description: Creation-time service mesh version.}
  mesh_type: {type: str, description: Creation-time mesh type.}
  config: {type: dict, description: SDK MeshConfig payload.}
  clusters: {type: list, elements: dict, description: Creation-time SDK Cluster payloads.}
  tags: {type: dict, description: Creation-time tags.}
  delete_cls: {type: bool, default: false, description: Delete associated CLS resources with the mesh.}
  delete_tmp: {type: bool, default: false, description: Delete associated TMP resources with the mesh.}
  delete_apm: {type: bool, default: false, description: Delete associated APM resources with the mesh.}
  delete_grafana: {type: bool, default: false, description: Delete associated Grafana resources with the mesh.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tcm_mesh:
    name: production-mesh
    mesh_version: 1.20.5
    mesh_type: HOSTED
    config: {Istio: {DisablePolicyChecks: false}}
"""
RETURN = r"""mesh: {description: Effective service mesh metadata., type: dict, returned: always}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.tcm.v20210413 import models, tcm_client

    return models, tcm_client


def _model(cls, value):
    if value is None:
        return None
    x = cls()
    x.from_json_string(json.dumps(value))
    return x


def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        x = models.Tag()
        x.Key, x.Value = str(key), str(value)
        result.append(x)
    return result


def list_request(models, offset=0):
    r = models.DescribeMeshListRequest()
    r.Offset, r.Limit = offset, 100
    return r


def describe_request(models, mesh_id):
    r = models.DescribeMeshRequest()
    r.MeshId = mesh_id
    return r


def create_request(models, p):
    r = models.CreateMeshRequest()
    r.DisplayName, r.MeshVersion, r.Type = p["name"], p["mesh_version"], p["mesh_type"]
    r.Config = _model(models.MeshConfig, p.get("config"))
    r.ClusterList = [_model(models.Cluster, x) for x in p.get("clusters") or []]
    r.TagList = _tags(models, p.get("tags"))
    return r


def update_request(models, mesh_id, target):
    r = models.ModifyMeshRequest()
    r.MeshId, r.DisplayName = mesh_id, target["DisplayName"]
    r.Config = _model(models.MeshConfig, target.get("Config"))
    return r


def delete_request(models, p, mesh_id):
    r = models.DeleteMeshRequest()
    r.MeshId = mesh_id
    r.NeedDeleteCLS, r.NeedDeleteTMP, r.NeedDeleteAPM, r.NeedDeleteGrafana = p["delete_cls"], p["delete_tmp"], p["delete_apm"], p["delete_grafana"]
    return r


def find(module, client, models, p):
    if p.get("mesh_id"):
        try:
            value = module.sdk_call(client.DescribeMesh, describe_request(models, p["mesh_id"])).Mesh
        except Exception:
            raise
        return value._serialize(allow_none=True) if value else None
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeMeshList, list_request(models, offset))
        page = response.MeshList or []
        for item in page:
            value = item._serialize(allow_none=True)
            if value.get("DisplayName") == p.get("name"):
                matches.append(value)
        offset += len(page)
        if not page or offset >= int(response.Total or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple TCM meshes matched; specify mesh_id")
    return matches[0] if matches else None


def comparable(v):
    return {"DisplayName": v.get("DisplayName"), "MeshVersion": v.get("Version"), "Type": v.get("Type"), "Config": v.get("Config")}


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and contains(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(contains(a, e) for a, e in zip(actual, expected))
    return actual == expected


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "mesh_id": {},
        "name": {},
        "mesh_version": {},
        "mesh_type": {},
        "config": {"type": "dict"},
        "clusters": {"type": "list", "elements": "dict"},
        "tags": {"type": "dict"},
        "delete_cls": {"type": "bool", "default": False},
        "delete_tmp": {"type": "bool", "default": False},
        "delete_apm": {"type": "bool", "default": False},
        "delete_grafana": {"type": "bool", "default": False},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("mesh_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TcmClient, "tcm.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, mesh=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteMesh, delete_request(models, p, current["MeshId"]))
            module.exit_json(changed=True, **(diff or {}), mesh=None)
        if not current:
            missing = [x for x in ("name", "mesh_version", "mesh_type") if not p.get(x)]
            if missing:
                module.fail_json(msg="creation parameters are required for a TCM mesh", missing=missing)
            target = {"DisplayName": p["name"], "MeshVersion": p["mesh_version"], "Type": p["mesh_type"], "Config": p.get("config")}
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                p["mesh_id"] = module.sdk_call(client.CreateMesh, create_request(models, p)).MeshId
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), mesh=current if not module.check_mode else target)
        before = comparable(current)
        desired_config = p.get("config")
        target = {
            "DisplayName": p.get("name") or before["DisplayName"],
            "MeshVersion": p.get("mesh_version") or before["MeshVersion"],
            "Type": p.get("mesh_type") or before["Type"],
            "Config": before["Config"] if desired_config is None or contains(before["Config"], desired_config) else desired_config,
        }
        if before == target:
            module.exit_json(changed=False, mesh=current)
        require_immutable_unchanged(module, before, target, ("MeshVersion", "Type"), "TCM mesh")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyMesh, update_request(models, current["MeshId"], target))
            p["mesh_id"] = current["MeshId"]
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), mesh=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
