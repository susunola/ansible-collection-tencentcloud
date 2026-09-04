#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cbs_snapshot
short_description: Manage Tencent Cloud CBS disk snapshots
version_added: "0.14.0"
description:
  - Create, wait for and delete Cloud Block Storage (CBS) disk snapshots
    through the C(cbs.v20170312) API.
  - A snapshot is identified either by its C(snapshot_id) or by the
    combination of the source C(disk_id) and C(snapshot_name); the module
    is idempotent, so running it twice with the same parameters leaves
    the snapshot unchanged and the second run reports C(changed=false).
  - Snapshot creation is asynchronous. When O(wait=true) (the default),
    the module polls DescribeSnapshots until the snapshot reaches the
    C(NORMAL) state, bounded by O(waiter_timeout).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the snapshot when it does not exist.
      - C(absent) deletes the snapshot when it exists.
    type: str
    choices: [present, absent]
    default: present
  disk_id:
    description:
      - ID of the disk the snapshot is taken from, e.g. C(disk-xxxxxxxx).
      - Required together with O(snapshot_name) to create a snapshot or to
        look one up by name.
    type: str
  snapshot_name:
    description:
      - Name of the snapshot, written to
        V(CreateSnapshotRequest.SnapshotName).
      - Required together with O(disk_id) to create a snapshot or to look
        one up by name.
    type: str
  snapshot_id:
    description:
      - ID of an existing snapshot, e.g. C(snap-xxxxxxxx).
      - When given, the module addresses the snapshot by ID instead of by
        disk and name; it is the only way to delete a snapshot whose name
        is unknown.
    type: str
  wait:
    description:
      - When C(true) (the default), O(state=present) waits until the
        snapshot reaches the C(NORMAL) state before returning.
      - When C(false), the module returns as soon as the snapshot exists,
        still in C(CREATING).
    type: bool
    default: true
  retries:
    description: Number of retries for transient SDK failures.
    type: int
    default: 5
  waiter_timeout:
    description:
      - Maximum time in seconds to wait for the snapshot to reach the
        desired state.
    type: int
    default: 120
  waiter_delay:
    description: Interval in seconds between state polls while waiting.
    type: int
    default: 5
  user_agent:
    description:
      - Value appended to the SDK User-Agent header so API usage can be
        attributed to this collection.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-cbs) package on the controller.
  - Only disks with snapshot ability can be snapshotted; the error
    C(InvalidDisk.NotSupportSnapshot) is reported by the API otherwise.
  - The quota of snapshots per disk is limited; the error
    C(InsufficientSnapshotQuota) is reported by the API when the quota is
    exhausted.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a snapshot of a disk and wait for it to be available
  susunola.tencentcloud.cbs_snapshot:
    region: ap-guangzhou
    disk_id: disk-xxxxxxxx
    snapshot_name: prod-before-upgrade

- name: Create a snapshot without waiting for it to finish
  susunola.tencentcloud.cbs_snapshot:
    region: ap-guangzhou
    disk_id: disk-xxxxxxxx
    snapshot_name: nightly
    wait: false

- name: Delete a snapshot by ID
  susunola.tencentcloud.cbs_snapshot:
    region: ap-guangzhou
    snapshot_id: snap-xxxxxxxx
    state: absent
'''

RETURN = r'''
snapshot:
  description: The snapshot as reported by DescribeSnapshots after the
    operation, or None when it was deleted.
  returned: success
  type: dict
  sample:
    SnapshotId: snap-xxxxxxxx
    SnapshotName: prod-before-upgrade
    SnapshotState: NORMAL
    DiskId: disk-xxxxxxxx
    DiskSize: 100
    Percent: 100
    IsPermanent: true
    CreateTime: "2026-08-28 10:00:00"
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_cbs():
    from tencentcloud.cbs.v20170312 import models, cbs_client
    return models, cbs_client


def _first(collection):
    return collection[0] if collection else None


def build_describe_request(models, snapshot_ids, disk_id, snapshot_name):
    request = models.DescribeSnapshotsRequest()
    request.Limit = 100
    if snapshot_ids:
        request.SnapshotIds = snapshot_ids
        return request
    filters = []
    if snapshot_name:
        name_filter = models.Filter()
        name_filter.Name = "snapshot-name"
        name_filter.Values = [snapshot_name]
        filters.append(name_filter)
    if disk_id:
        disk_filter = models.Filter()
        disk_filter.Name = "disk-id"
        disk_filter.Values = [disk_id]
        filters.append(disk_filter)
    if filters:
        # Newest snapshot first so a name lookup returns the most recent
        # snapshot when several share the name.
        request.Filters = filters
        request.OrderField = "CREATE_TIME"
        request.Order = "DESC"
    return request


def find_snapshot(module, client, models, snapshot_ids, disk_id, snapshot_name):
    """Return the matching snapshot dict or None."""
    request = build_describe_request(models, snapshot_ids, disk_id, snapshot_name)
    response = module.sdk_call(client.DescribeSnapshots, request)
    snapshot = _first(response.SnapshotSet or [])
    if snapshot is None:
        return None
    return snapshot._serialize(allow_none=True)


def _wait_for_available(module, client, models, snapshot_id):
    """Poll DescribeSnapshots until the snapshot reaches NORMAL."""
    deadline = time.time() + module.params["waiter_timeout"]
    last_state = None
    while True:
        current = find_snapshot(module, client, models, [snapshot_id], None, None)
        last_state = current and current.get("SnapshotState")
        if current is not None and last_state == "NORMAL":
            return current
        if time.time() >= deadline:
            module.fail_json(
                msg="Timed out waiting for snapshot %s to become NORMAL (last state %s)"
                % (snapshot_id, last_state),
                snapshot=current,
            )
        time.sleep(module.params["waiter_delay"])


def _create(module, client, models, disk_id, snapshot_name):
    request = models.CreateSnapshotRequest()
    request.DiskId = disk_id
    request.SnapshotName = snapshot_name
    response = module.sdk_call(client.CreateSnapshot, request)
    return response.SnapshotId


def _delete(module, client, models, snapshot_ids):
    request = models.DeleteSnapshotsRequest()
    request.SnapshotIds = snapshot_ids
    module.sdk_call(client.DeleteSnapshots, request)


def _identify(module, snapshot_id, disk_id, snapshot_name):
    """Return the lookup triple; fail when nothing identifies the snapshot."""
    if not snapshot_id and not (disk_id and snapshot_name):
        module.fail_json(
            msg="snapshot_id or both disk_id and snapshot_name are required "
                "to identify the snapshot")
    return ([snapshot_id] if snapshot_id else None), disk_id, snapshot_name


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "disk_id": {"type": "str"},
            "snapshot_name": {"type": "str"},
            "snapshot_id": {"type": "str"},
            "wait": {"type": "bool", "default": True},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    snapshot_ids, disk_id, snapshot_name = _identify(
        module, module.params["snapshot_id"], module.params["disk_id"],
        module.params["snapshot_name"])

    models, cbs_client = _load_cbs()
    client = module.create_client(cbs_client.CbsClient, "cbs.tencentcloudapi.com")

    try:
        current = find_snapshot(module, client, models, snapshot_ids, disk_id, snapshot_name)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="Snapshot already absent")
        target_id = current["SnapshotId"]
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete snapshot")
        _delete(module, client, models, [target_id])
        module.exit_json(changed=True, **(diff or {}), snapshot=None, msg="Snapshot deleted")

    # state == present
    if current is None:
        if not (disk_id and snapshot_name):
            module.fail_json(
                msg="disk_id and snapshot_name are required to create a snapshot")
        desired = {
            "SnapshotName": snapshot_name,
            "DiskId": disk_id,
            "SnapshotState": "NORMAL",
        }
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create snapshot")
        created_id = _create(module, client, models, disk_id, snapshot_name)
        current = find_snapshot(module, client, models, [created_id], None, None)
        if module.params["wait"]:
            current = _wait_for_available(module, client, models, created_id)
        module.exit_json(changed=True, **(diff or {}), snapshot=current, msg="Snapshot created")

    if module.params["wait"] and current.get("SnapshotState") != "NORMAL":
        current = _wait_for_available(module, client, models, current["SnapshotId"])
    module.exit_json(changed=False, snapshot=current, msg="Snapshot is up to date")


def main():
    run_module()


if __name__ == "__main__":
    main()
