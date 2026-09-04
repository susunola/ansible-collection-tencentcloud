#!/usr/bin/python
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: tcr_replication_instance
short_description: Manage Tencent Cloud TCR replication instances
version_added: "0.14.0"
description: Creates and deletes cross-region TCR enterprise replication instances.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  registry_id: {description: Source TCR enterprise instance ID., type: str, required: true}
  replication_region_id: {description: Numeric destination region ID., type: int, required: true}
  replication_region_name: {description: Destination region name., type: str, required: true}
  sync_tag: {description: Whether to synchronize TCR tags to the backing bucket., type: bool, default: false}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r"""
- susunola.tencentcloud.tcr_replication_instance:
    registry_id: tcr-xxxxxxxx
    replication_region_id: 1
    replication_region_name: ap-shanghai
"""
RETURN = r"""replication_instance: {description: Replication instance metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
import time


def _load_tcr():
    from tencentcloud.tcr.v20190924 import models, tcr_client

    return models, tcr_client


def build_describe_request(models, registry_id):
    r = models.DescribeReplicationInstancesRequest()
    r.RegistryId = registry_id
    r.Offset = 0
    r.Limit = 100
    return r


def build_create_request(models, p):
    r = models.CreateReplicationInstanceRequest()
    r.RegistryId = p["registry_id"]
    r.ReplicationRegionId = p["replication_region_id"]
    r.ReplicationRegionName = p["replication_region_name"]
    r.SyncTag = p["sync_tag"]
    return r


def build_delete_request(models, registry_id, replication_registry_id, region_id):
    r = models.DeleteReplicationInstanceRequest()
    r.RegistryId = registry_id
    r.ReplicationRegistryId = replication_registry_id
    r.ReplicationRegionId = region_id
    return r


def _find(items, region_id):
    return next((x._serialize(allow_none=True) for x in items if x.ReplicationRegionId == region_id), None)


def wait_for_replication(module, client, models, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        response = module.sdk_call(
            client.DescribeReplicationInstances,
            build_describe_request(models, module.params["registry_id"]),
        )
        current = _find(response.ReplicationRegistries or [], module.params["replication_region_id"])
        if absent and current is None:
            return None
        if current and str(current.get("Status", "")).lower() in ("failed", "createfailed", "deletefailed"):
            module.fail_json(msg="TCR replication instance entered a failed state", replication_instance=current)
        if not absent and current and str(current.get("Status", "")).lower() in ("running", "normal", "ready"):
            if not desired or current.get("ReplicationRegionName") == desired["ReplicationRegionName"]:
                return current
        if time.time() >= deadline:
            module.fail_json(
                msg="Timed out waiting for TCR replication instance convergence",
                replication_instance=current,
                expected="absent" if absent else desired,
            )
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "registry_id": {"type": "str", "required": True},
            "replication_region_id": {"type": "int", "required": True},
            "replication_region_name": {"type": "str", "required": True},
            "sync_tag": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load_tcr()
    client = module.create_client(cm.TcrClient, "tcr.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeReplicationInstances, build_describe_request(models, p["registry_id"]))
        current = _find(response.ReplicationRegistries or [], p["replication_region_id"])
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, replication_instance=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(
                    client.DeleteReplicationInstance,
                    build_delete_request(models, p["registry_id"], current["ReplicationRegistryId"], p["replication_region_id"]),
                )
                wait_for_replication(module, client, models, absent=True)
            module.exit_json(changed=True, **(diff or {}), replication_instance=current if module.check_mode else None)
        if current:
            module.exit_json(changed=False, replication_instance=current)
        desired = {"RegistryId": p["registry_id"], "ReplicationRegionId": p["replication_region_id"], "ReplicationRegionName": p["replication_region_name"]}
        diff = maybe_diff(module, None, desired)
        if not module.check_mode:
            module.sdk_call(client.CreateReplicationInstance, build_create_request(models, p))
            current = wait_for_replication(module, client, models, desired=desired)
        module.exit_json(changed=True, **(diff or {}), replication_instance=None if module.check_mode else current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
