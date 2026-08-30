#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: cbs_snapshot_share
short_description: Manage Tencent Cloud CBS snapshot sharing permissions
version_added: "0.14.0"
description: Reconciles the exact set of Tencent Cloud account IDs allowed to use a data-disk snapshot in the same region.
options:
  snapshot_id: {type: str, required: true, description: CBS data-disk snapshot ID.}
  account_ids: {type: list, elements: str, default: [], description: Exact set of recipient Tencent Cloud account IDs.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cbs_snapshot_share:
    snapshot_id: snap-xxxxxxxx
    account_ids: ['100001122000', '100001133000']

- name: Revoke every share from the snapshot
  susunola.tencentcloud.cbs_snapshot_share:
    snapshot_id: snap-xxxxxxxx
    account_ids: []
'''
RETURN = r'''share_permissions: {description: Effective sorted recipient account IDs., type: list, elements: str, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cbs.v20170312 import models, cbs_client
    return models, cbs_client
def describe_request(models, snapshot_id):
    request = models.DescribeSnapshotSharePermissionRequest(); request.SnapshotId = snapshot_id; return request
def modify_request(models, snapshot_id, account_ids, permission):
    request = models.ModifySnapshotsSharePermissionRequest(); request.SnapshotIds, request.AccountIds, request.Permission = [snapshot_id], sorted(account_ids), permission; return request
def describe(module, client, models, snapshot_id):
    response = module.sdk_call(client.DescribeSnapshotSharePermission, describe_request(models, snapshot_id))
    return sorted(item.AccountId for item in (response.SharePermissionSet or []) if item.AccountId)


def run_module():
    module = TencentCloudModule(argument_spec={"snapshot_id": {"required": True}, "account_ids": {"type": "list", "elements": "str", "default": []}}, supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.CbsClient, "cbs.tencentcloudapi.com")
    try:
        current = describe(module, client, models, p["snapshot_id"]); target = sorted(set(p["account_ids"])); add = sorted(set(target) - set(current)); remove = sorted(set(current) - set(target))
        if not add and not remove: module.exit_json(changed=False, share_permissions=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            if remove: module.sdk_call(client.ModifySnapshotsSharePermission, modify_request(models, p["snapshot_id"], remove, "CANCEL"))
            if add: module.sdk_call(client.ModifySnapshotsSharePermission, modify_request(models, p["snapshot_id"], add, "SHARE"))
            current = describe(module, client, models, p["snapshot_id"])
        module.exit_json(changed=True, **(diff or {}), share_permissions=current if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
