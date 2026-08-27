#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cbs_disk
short_description: Manage Tencent Cloud CBS cloud disks
version_added: "0.12.0"
description:
  - Create, resize, attach, detach and delete CBS cloud disks through the
    C(cbs.v20170312) API.
  - This module is idempotent. Running it twice leaves the disk unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
  - Attachment changes wait for the disk to reach the target state
    (C(ATTACHED)/C(UNATTACHED)) using O(waiter_delay) and O(waiter_timeout).
options:
  state:
    description:
      - C(present) creates the disk when it does not exist and reconciles its
        name, size and attachment when it does.
      - C(absent) terminates the disk.
    type: str
    choices: [present, absent]
    default: present
  disk_id:
    description:
      - ID of an existing disk, e.g. C(disk-xxxxxxxx).
      - When given, the module operates on that disk; otherwise the disk is
        matched by O(name) (optionally scoped by O(zone)).
    type: str
  name:
    description:
      - Name of the disk, written to V(CreateDisksRequest.DiskName) and
        V(ModifyDiskAttributesRequest.DiskName).
    type: str
  zone:
    description:
      - Availability zone of the disk, e.g. C(ap-guangzhou-3).
      - Required when creating the disk and used to narrow O(name) matches.
    type: str
  disk_type:
    description:
      - Media type of the disk, written to V(CreateDisksRequest.DiskType).
      - Only applied at creation.
    type: str
    choices:
      - CLOUD_BASIC
      - CLOUD_PREMIUM
      - CLOUD_SSD
      - CLOUD_HSSD
      - CLOUD_TSSD
  disk_size:
    description:
      - Capacity of the disk in GiB, written to V(CreateDisksRequest.DiskSize).
      - When the disk exists and O(disk_size) is larger than the current size,
        the disk is resized with V(ResizeDisk) (resize only grows, never
        shrinks).
    type: int
  charge_type:
    description:
      - Billing mode of the disk, written to V(CreateDisksRequest.DiskChargeType).
      - Only applied at creation.
    type: str
    choices: [PREPAID, POSTPAID_BY_HOUR]
    default: POSTPAID_BY_HOUR
  prepaid_period_months:
    description:
      - Prepaid period in months, written to
        V(CreateDisksRequest.DiskChargePrepaid.Period).
      - Only applied when O(charge_type=PREPAID).
    type: int
  instance_id:
    description:
      - ID of the CVM instance to attach the disk to, e.g. C(ins-xxxxxxxx),
        written to V(AttachDisksRequest.InstanceId).
      - When given and the disk is attached elsewhere, the disk is detached
        first, then attached and waited into C(ATTACHED) state.
    type: str
  detach:
    description:
      - When true and the disk is attached, the disk is detached and waited
        into C(UNATTACHED) state.
      - Mutually exclusive with O(instance_id) in effect; when both are given
        O(instance_id) wins.
    type: bool
    default: false
  delete_with_instance:
    description:
      - When true, the disk is deleted together with the instance it is
        attached to, written to V(AttachDisksRequest.DeleteWithInstance).
    type: bool
  encrypt:
    description:
      - Encrypt the disk at creation, written to V(CreateDisksRequest.Encrypt).
      - Only applied at creation.
    type: bool
  snapshot_id:
    description:
      - Create the disk from this snapshot, written to
        V(CreateDisksRequest.SnapshotId).
      - Only applied at creation.
    type: str
  delete_snapshot:
    description:
      - Delete snapshots of the disk together with the disk, written to
        V(TerminateDisksRequest.DeleteSnapshot).
    type: bool
    default: false
  tags:
    description:
      - Tags to apply to the disk as a dict, for example I(env=prod).
      - Only applied at creation.
    type: dict
    default: {}
  retries:
    description: Number of retries for transient SDK failures.
    type: int
    default: 5
  waiter_delay:
    description: Seconds to wait between state-polling attempts.
    type: int
    default: 5
  waiter_timeout:
    description: Overall timeout in seconds for state polling.
    type: int
    default: 120
  user_agent:
    description:
      - Value appended to the SDK User-Agent header so API usage can be
        attributed to this collection.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-cbs) package on the controller.
  - POSTPAID_BY_HOUR disks are billed per hour while present; terminate them
    as soon as they are no longer needed to avoid unnecessary charges.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a 50 GiB SSD disk
  susunola.tencentcloud.cbs_disk:
    region: ap-guangzhou
    state: present
    name: data-disk
    zone: ap-guangzhou-3
    disk_type: CLOUD_SSD
    disk_size: 50
    tags:
      env: prod

- name: Attach it to an instance and wait until ATTACHED
  susunola.tencentcloud.cbs_disk:
    region: ap-guangzhou
    state: present
    name: data-disk
    zone: ap-guangzhou-3
    instance_id: ins-aaaaaaaa
    delete_with_instance: false

- name: Detach and wait until UNATTACHED
  susunola.tencentcloud.cbs_disk:
    region: ap-guangzhou
    state: present
    name: data-disk
    zone: ap-guangzhou-3
    detach: true

- name: Grow the disk to 100 GiB
  susunola.tencentcloud.cbs_disk:
    region: ap-guangzhou
    state: present
    name: data-disk
    zone: ap-guangzhou-3
    disk_size: 100

- name: Terminate the disk
  susunola.tencentcloud.cbs_disk:
    region: ap-guangzhou
    state: absent
    name: data-disk
    zone: ap-guangzhou-3
'''

RETURN = r'''
disk:
  description: The disk as reported by V(DescribeDisks) after the operation.
  returned: success
  type: dict
  sample:
    DiskId: disk-xxxxxxxx
    DiskName: data-disk
    DiskSize: 50
    DiskType: CLOUD_SSD
    DiskState: ATTACHED
    DiskChargeType: POSTPAID_BY_HOUR
    InstanceId: ins-aaaaaaaa
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff

import time


def _load_cbs():
    from tencentcloud.cbs.v20170312 import models, cbs_client
    return models, cbs_client


def build_describe_request(models, disk_id, name, zone):
    request = models.DescribeDisksRequest()
    request.Limit = 100
    if disk_id:
        request.DiskIds = [disk_id]
        return request
    filters = []
    if name:
        name_filter = models.Filter()
        name_filter.Name = "disk-name"
        name_filter.Values = [name]
        filters.append(name_filter)
    if zone:
        zone_filter = models.Filter()
        zone_filter.Name = "zone"
        zone_filter.Values = [zone]
        filters.append(zone_filter)
    if filters:
        request.Filters = filters
    return request


def _first(collection):
    return collection[0] if collection else None


def find_disk(module, client, models, disk_id, name, zone):
    """Return the matching disk dict or None."""
    request = build_describe_request(models, disk_id, name, zone)
    response = module.sdk_call(client.DescribeDisks, request)
    disk = _first(response.DiskSet or [])
    if disk is None:
        return None
    return disk._serialize(allow_none=True)


def _wait_for_state(module, client, models, disk_id, expected_states):
    """Poll DescribeDisks until the disk reaches one of expected_states."""
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_disk(module, client, models, disk_id, None, None)
        if current is not None and current.get("DiskState") in expected_states:
            return current
        if time.time() >= deadline:
            module.fail_json(
                msg="Timed out waiting for disk %s to reach %s (last state %s)"
                % (disk_id, expected_states, current and current.get("DiskState")),
                disk=current,
            )
        time.sleep(module.params["waiter_delay"])


def _create(module, client, models, params):
    request = models.CreateDisksRequest()
    request.DiskType = params["disk_type"]
    request.DiskSize = params["disk_size"]
    request.DiskChargeType = params["charge_type"]
    placement = models.Placement()
    placement.Zone = params["zone"]
    request.Placement = placement
    if params["name"]:
        request.DiskName = params["name"]
    if params["charge_type"] == "PREPAID" and params["prepaid_period_months"]:
        prepaid = models.DiskChargePrepaid()
        prepaid.Period = params["prepaid_period_months"]
        request.DiskChargePrepaid = prepaid
    if params["encrypt"]:
        request.Encrypt = True
    if params["snapshot_id"]:
        request.SnapshotId = params["snapshot_id"]
    if params["tags"]:
        request.Tags = [
            models.Tag(**{"Key": key, "Value": value})
            for key, value in sorted(params["tags"].items())
        ]
    response = module.sdk_call(client.CreateDisks, request)
    return response.DiskIdSet[0]


def _rename(module, client, models, disk_id, name):
    request = models.ModifyDiskAttributesRequest()
    request.DiskIds = [disk_id]
    request.DiskName = name
    module.sdk_call(client.ModifyDiskAttributes, request)


def _resize(module, client, models, disk_id, disk_size):
    request = models.ResizeDiskRequest()
    request.DiskId = disk_id
    request.DiskSize = disk_size
    module.sdk_call(client.ResizeDisk, request)


def _attach(module, client, models, disk_id, instance_id, delete_with_instance):
    request = models.AttachDisksRequest()
    request.DiskIds = [disk_id]
    request.InstanceId = instance_id
    if delete_with_instance is not None:
        request.DeleteWithInstance = delete_with_instance
    module.sdk_call(client.AttachDisks, request)


def _detach(module, client, models, disk_id, instance_id):
    request = models.DetachDisksRequest()
    request.DiskIds = [disk_id]
    request.InstanceId = instance_id
    module.sdk_call(client.DetachDisks, request)


def _delete(module, client, models, disk_id, delete_snapshot):
    request = models.TerminateDisksRequest()
    request.DiskIds = [disk_id]
    if delete_snapshot:
        request.DeleteSnapshot = True
    module.sdk_call(client.TerminateDisks, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "disk_id": {"type": "str"},
            "name": {"type": "str"},
            "zone": {"type": "str"},
            "disk_type": {
                "type": "str",
                "choices": ["CLOUD_BASIC", "CLOUD_PREMIUM", "CLOUD_SSD", "CLOUD_HSSD", "CLOUD_TSSD"],
            },
            "disk_size": {"type": "int"},
            "charge_type": {"type": "str", "choices": ["PREPAID", "POSTPAID_BY_HOUR"], "default": "POSTPAID_BY_HOUR"},
            "prepaid_period_months": {"type": "int"},
            "instance_id": {"type": "str"},
            "detach": {"type": "bool", "default": False},
            "delete_with_instance": {"type": "bool"},
            "encrypt": {"type": "bool"},
            "snapshot_id": {"type": "str"},
            "delete_snapshot": {"type": "bool", "default": False},
            "tags": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    disk_id = module.params["disk_id"]
    name = module.params["name"]
    zone = module.params["zone"]

    if not disk_id and not name:
        module.fail_json(msg="disk_id or name is required to identify the disk")

    models, cbs_client = _load_cbs()
    client = module.create_client(cbs_client.CbsClient, "cbs.tencentcloudapi.com")

    try:
        current = find_disk(module, client, models, disk_id, name, zone)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="Disk already absent")
        target_id = current["DiskId"]
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete disk")
        _delete(module, client, models, target_id, module.params["delete_snapshot"])
        module.exit_json(changed=True, **(diff or {}), disk=None, msg="Disk deleted")

    # state == present
    if current is None:
        missing = [key for key in ("zone", "disk_type", "disk_size") if not module.params[key]]
        if missing:
            module.fail_json(msg="%s is required when creating a disk" % ", ".join(missing))
        desired = {
            "DiskName": name,
            "Zone": zone,
            "DiskType": module.params["disk_type"],
            "DiskSize": module.params["disk_size"],
            "DiskChargeType": module.params["charge_type"],
        }
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create disk")
        created_id = _create(module, client, models, module.params)
        current = find_disk(module, client, models, created_id, None, None)
        module.exit_json(changed=True, **(diff or {}), disk=current, msg="Disk created")

    target_id = current["DiskId"]
    changes = []
    if name and current.get("DiskName") != name:
        changes.append("name")
    disk_size = module.params["disk_size"]
    if disk_size is not None and disk_size > current.get("DiskSize", 0):
        changes.append("size")
    current_instance = current.get("InstanceId") or ""
    instance_id = module.params["instance_id"]
    if instance_id and current_instance != instance_id:
        changes.append("attachment")
    elif module.params["detach"] and current_instance:
        changes.append("detachment")

    if not changes:
        module.exit_json(changed=False, disk=current, msg="Disk is up to date")

    diff = maybe_diff(module, current, {
        "DiskName": name or current.get("DiskName"),
        "DiskSize": max(disk_size or 0, current.get("DiskSize", 0)),
        "InstanceId": instance_id or ("" if module.params["detach"] else current_instance),
    })
    if module.check_mode:
        module.exit_json(changed=True, **(diff or {}), msg="Would update disk")

    if "name" in changes:
        _rename(module, client, models, target_id, name)
    if "size" in changes:
        _resize(module, client, models, target_id, disk_size)
    if "detachment" in changes:
        _detach(module, client, models, target_id, current_instance)
        current = _wait_for_state(module, client, models, target_id, ["UNATTACHED", "TORECYCLE"])
    if "attachment" in changes:
        if current_instance and current_instance != instance_id:
            _detach(module, client, models, target_id, current_instance)
            _wait_for_state(module, client, models, target_id, ["UNATTACHED", "TORECYCLE"])
        _attach(module, client, models, target_id, instance_id, module.params["delete_with_instance"])
        current = _wait_for_state(module, client, models, target_id, ["ATTACHED"])

    updated = find_disk(module, client, models, target_id, None, None)
    module.exit_json(changed=True, **(diff or {}), disk=updated, msg="Disk updated")


def main():
    run_module()


if __name__ == "__main__":
    main()
