#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tcm_mesh_clusters
short_description: Reconcile Tencent Cloud Mesh cluster links
version_added: "0.14.0"
description: Reconciles the exact cluster set linked to a Tencent Cloud Mesh instance.
options:
  mesh_id: {type: str, required: true, description: Mesh ID.}
  clusters: {type: list, elements: dict, required: true, description: "Exact desired SDK Cluster payload set, keyed by ClusterId."}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tcm_mesh_clusters:
    mesh_id: mesh-xxxxxxxx
    clusters:
      - {ClusterId: cls-xxxxxxxx, Region: ap-guangzhou, Role: REMOTE}
"""
RETURN = r"""clusters: {description: Effective linked cluster metadata., type: list, elements: dict, returned: always}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tcm.v20210413 import models, tcm_client

    return models, tcm_client


def _model(models, value):
    x = models.Cluster()
    x.from_json_string(json.dumps(value))
    return x


def describe_request(models, mesh_id):
    r = models.DescribeMeshRequest()
    r.MeshId = mesh_id
    return r


def link_request(models, mesh_id, clusters):
    r = models.LinkClusterListRequest()
    r.MeshId = mesh_id
    r.ClusterList = [_model(models, x) for x in clusters]
    return r


def unlink_request(models, mesh_id, cluster_id):
    r = models.UnlinkClusterRequest()
    r.MeshId, r.ClusterId = mesh_id, cluster_id
    return r


def describe(module, client, models, mesh_id):
    value = module.sdk_call(client.DescribeMesh, describe_request(models, mesh_id)).Mesh
    if not value:
        module.fail_json(msg="TCM mesh was not found", mesh_id=mesh_id)
    return [x._serialize(allow_none=True) for x in (value.ClusterList or [])]


def normalized(values):
    return sorted(values, key=lambda x: x.get("ClusterId") or "")


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and contains(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(contains(a, e) for a, e in zip(actual, expected))
    return actual == expected


def run_module():
    module = TencentCloudModule(
        argument_spec={"mesh_id": {"required": True}, "clusters": {"type": "list", "elements": "dict", "required": True}}, supports_check_mode=True
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TcmClient, "tcm.tencentcloudapi.com")
    try:
        ids = [x.get("ClusterId") for x in p["clusters"]]
        if any(not x for x in ids) or len(ids) != len(set(ids)):
            module.fail_json(msg="Each desired TCM cluster must have a unique ClusterId")
        current = describe(module, client, models, p["mesh_id"])
        current_by_id = {x["ClusterId"]: x for x in current}
        desired_by_id = {x["ClusterId"]: x for x in p["clusters"]}
        before = sorted(current_by_id)
        target = sorted(desired_by_id)
        replace = {x for x in set(before) & set(target) if not contains(current_by_id[x], desired_by_id[x])}
        if before == target and not replace:
            module.exit_json(changed=False, clusters=normalized(current))
        diff = maybe_diff(module, normalized(current), normalized(p["clusters"]))
        remove = sorted((set(before) - set(target)) | replace)
        add = [desired_by_id[x] for x in sorted((set(target) - set(before)) | replace)]
        if not module.check_mode:
            for cluster_id in remove:
                module.sdk_call(client.UnlinkCluster, unlink_request(models, p["mesh_id"], cluster_id))
            if add:
                module.sdk_call(client.LinkClusterList, link_request(models, p["mesh_id"], add))
            current = describe(module, client, models, p["mesh_id"])
        module.exit_json(changed=True, **(diff or {}), clusters=normalized(current) if not module.check_mode else normalized(p["clusters"]))
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
