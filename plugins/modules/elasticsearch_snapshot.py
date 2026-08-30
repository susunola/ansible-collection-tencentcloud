#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: elasticsearch_snapshot
short_description: Manage Tencent Cloud Elasticsearch cluster snapshots
version_added: "0.14.0"
description: Creates and deletes a named Elasticsearch snapshot with explicit replacement for immutable configuration drift.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: Elasticsearch instance ID.}
  repository_name: {type: str, required: true, description: Snapshot repository name used for lookup and deletion.}
  name: {type: str, required: true, description: Snapshot name.}
  indices: {type: list, elements: str, default: ['*'], description: Exact index selection captured by the snapshot.}
  repository_type: {type: int, choices: [0, 1], default: 0, description: Tencent-managed or customer repository.}
  storage_days: {type: int, default: 7, description: Snapshot storage duration in days.}
  lock_retention: {type: bool, default: false, description: Enable COS backup lock.}
  retain_until: {type: str, description: ISO timestamp through which the snapshot is locked.}
  retention_grace_days: {type: int, default: 0, description: Backup-lock grace period in days.}
  remote_cos: {type: bool, default: false, description: Enable cross-region snapshot storage.}
  remote_region: {type: str, description: Cross-region snapshot destination.}
  multi_az: {type: bool, default: false, description: Use multi-AZ COS storage.}
  max_snapshot_per_sec: {type: str, description: Maximum per-node snapshot write rate.}
  force_replace: {type: bool, default: false, description: Delete and recreate a snapshot whose immutable configuration differs.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.elasticsearch_snapshot:
    instance_id: es-xxxxxxxx
    repository_name: es-xxxxxxxx
    name: before-upgrade
    indices: [orders, customers]
    storage_days: 30
'''
RETURN = r'''snapshot: {description: Elasticsearch snapshot metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.es.v20180416 import es_client, models
    return models, es_client
def describe_request(models, p):
    request = models.DescribeClusterSnapshotRequest(); request.InstanceId, request.RepositoryName, request.SnapshotName = p["instance_id"], p["repository_name"], p["name"]; return request
def create_request(models, p):
    request = models.CreateClusterSnapshotRequest(); request.InstanceId, request.SnapshotName, request.Indices = p["instance_id"], p["name"], ",".join(sorted(set(p["indices"])))
    request.EsRepositoryType, request.UserEsRepository, request.StorageDuration = p["repository_type"], p["repository_name"] if p["repository_type"] == 1 else None, p["storage_days"]
    request.CosRetention, request.RetainUntilDate, request.RetentionGraceTime = int(p["lock_retention"]), p.get("retain_until"), p["retention_grace_days"]
    request.RemoteCos, request.RemoteCosRegion, request.MultiAz, request.MaxSnapshotPerSec = int(p["remote_cos"]), p.get("remote_region"), int(p["multi_az"]), p.get("max_snapshot_per_sec"); return request
def delete_request(models, p):
    request = models.DeleteClusterSnapshotRequest(); request.InstanceId, request.RepositoryName, request.SnapshotName = p["instance_id"], p["repository_name"], p["name"]; return request


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeClusterSnapshot, describe_request(models, p))
    for item in response.Snapshots or []:
        value = item._serialize(allow_none=True)
        if value.get("SnapshotName") == p["name"]: return value
    return None
def comparable(value):
    return {"SnapshotName": value.get("SnapshotName"), "Indices": sorted(set(value.get("Indices") or [])), "EsRepositoryType": int(value.get("EsRepositoryType") or 0), "StorageDuration": int(value.get("StorageDuration") or 7), "CosRetention": int(value.get("CosRetention") or 0), "RetainUntilDate": value.get("RetainUntilDate"), "RetentionGraceTime": int(value.get("RetentionGraceTime") or 0), "RemoteCos": int(value.get("RemoteCos") or 0), "RemoteCosRegion": value.get("RemoteCosRegion"), "MultiAz": int(value.get("MultiAz") or 0), "MaxSnapshotPerSec": value.get("MaxSnapshotPerSec")}
def desired(p):
    return {"SnapshotName": p["name"], "Indices": sorted(set(p["indices"])), "EsRepositoryType": p["repository_type"], "StorageDuration": p["storage_days"], "CosRetention": int(p["lock_retention"]), "RetainUntilDate": p.get("retain_until"), "RetentionGraceTime": p["retention_grace_days"], "RemoteCos": int(p["remote_cos"]), "RemoteCosRegion": p.get("remote_region"), "MultiAz": int(p["multi_az"]), "MaxSnapshotPerSec": p.get("max_snapshot_per_sec")}


def run_module():
    spec = {"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True}, "repository_name": {"required": True}, "name": {"required": True}, "indices": {"type": "list", "elements": "str", "default": ["*"]}, "repository_type": {"type": "int", "choices": [0, 1], "default": 0}, "storage_days": {"type": "int", "default": 7}, "lock_retention": {"type": "bool", "default": False}, "retain_until": {}, "retention_grace_days": {"type": "int", "default": 0}, "remote_cos": {"type": "bool", "default": False}, "remote_region": {}, "multi_az": {"type": "bool", "default": False}, "max_snapshot_per_sec": {}, "force_replace": {"type": "bool", "default": False}}
    module = TencentCloudModule(argument_spec=spec, required_if=[("lock_retention", True, ["retain_until"]), ("remote_cos", True, ["remote_region"])], supports_check_mode=True); p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.EsClient, "es.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, snapshot=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteClusterSnapshot, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), snapshot=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target: module.exit_json(changed=False, snapshot=current)
        diff = maybe_diff(module, before, target)
        if current and not p["force_replace"]: module.fail_json(msg="Elasticsearch snapshot configuration is immutable; set force_replace=true to recreate it", current=before, desired=target)
        if not module.check_mode:
            if current: module.sdk_call(client.DeleteClusterSnapshot, delete_request(models, p))
            module.sdk_call(client.CreateClusterSnapshot, create_request(models, p)); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), snapshot=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
