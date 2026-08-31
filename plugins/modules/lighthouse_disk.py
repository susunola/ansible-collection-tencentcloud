#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: lighthouse_disk
short_description: Manage Tencent Cloud Lighthouse data disks
version_added: "0.14.0"
description: Creates, renames, attaches, detaches and terminates Lighthouse data disks.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  disk_id: {type: str, description: Existing disk ID; preferred for updates and deletion.}
  name: {type: str, description: "Disk name, also used for lookup when disk_id is omitted."}
  zone: {type: str, description: Availability zone; required for creation.}
  disk_size: {type: int, description: Disk size in GiB; required for creation.}
  disk_type: {type: str, choices: [CLOUD_PREMIUM, CLOUD_SSD], description: Disk media type; required for creation.}
  prepaid_period: {type: int, description: Subscription period in months; required for creation.}
  renew_flag:
    type: str
    choices: [NOTIFY_AND_AUTO_RENEW, NOTIFY_AND_MANUAL_RENEW, DISABLE_NOTIFY_AND_MANUAL_RENEW]
    default: NOTIFY_AND_MANUAL_RENEW
    description: Renewal policy.
  instance_id: {type: str, description: Exact Lighthouse instance attachment to enforce; omit to keep the disk detached.}
  force_replace: {type: bool, default: false, description: "Recreate when immutable size, type or zone differs."}
  force_detach: {type: bool, default: false, description: Allow detaching a disk before replacement or deletion.}
  wait: {type: bool, default: true, description: Wait for attachment and lifecycle operations to settle.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""

EXAMPLES = r"""
- name: Create and attach a Lighthouse data disk
  susunola.tencentcloud.lighthouse_disk:
    region: ap-guangzhou
    name: app-data
    zone: ap-guangzhou-3
    disk_size: 100
    disk_type: CLOUD_SSD
    prepaid_period: 12
    instance_id: lhins-xxxxxxxx

- name: Delete a disk, detaching it first
  susunola.tencentcloud.lighthouse_disk:
    region: ap-guangzhou
    disk_id: lhdisk-xxxxxxxx
    state: absent
    force_detach: true
"""

RETURN = r"""disk: {description: Lighthouse disk metadata., type: dict, returned: always}"""

import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.lighthouse.v20200324 import models, lighthouse_client

    return models, lighthouse_client


def describe_request(models, p, offset=0):
    request = models.DescribeDisksRequest()
    request.Offset, request.Limit = offset, 100
    if p.get("disk_id"):
        request.DiskIds = [p["disk_id"]]
    elif p.get("name"):
        item = models.Filter()
        item.Name, item.Values = "disk-name", [p["name"]]
        request.Filters = [item]
    return request


def create_request(models, p):
    request = models.CreateDisksRequest()
    request.Zone, request.DiskSize, request.DiskType = p["zone"], p["disk_size"], p["disk_type"]
    request.DiskName, request.DiskCount = p["name"], 1
    prepaid = models.DiskChargePrepaid()
    prepaid.Period, prepaid.RenewFlag = p["prepaid_period"], p["renew_flag"]
    request.DiskChargePrepaid = prepaid
    return request


def update_request(models, disk_id, name):
    request = models.ModifyDisksAttributeRequest()
    request.DiskIds, request.DiskName = [disk_id], name
    return request


def attach_request(models, disk_id, instance_id, renew_flag):
    request = models.AttachDisksRequest()
    request.DiskIds, request.InstanceId, request.RenewFlag = [disk_id], instance_id, renew_flag
    return request


def detach_request(models, disk_id):
    request = models.DetachDisksRequest()
    request.DiskIds = [disk_id]
    return request


def delete_request(models, disk_id):
    request = models.TerminateDisksRequest()
    request.DiskIds = [disk_id]
    return request


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeDisks, describe_request(models, p, offset))
        values = list(response.DiskSet or [])
        matches.extend(item._serialize(allow_none=True) for item in values)
        offset += len(values)
        if offset >= int(response.TotalCount or 0) or not values:
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple Lighthouse disks matched; specify disk_id")
    return matches[0] if matches else None


def wait_disk(module, client, models, p, desired_states, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find(module, client, models, p)
        if absent and not current:
            return None
        if current and current.get("DiskState") in desired_states:
            return current
        if current and current.get("LatestOperationState") == "FAILED":
            module.fail_json(msg="Lighthouse disk operation failed", disk=current)
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for Lighthouse disk operation", disk=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "disk_id": {},
            "name": {},
            "zone": {},
            "disk_size": {"type": "int"},
            "disk_type": {"choices": ["CLOUD_PREMIUM", "CLOUD_SSD"]},
            "prepaid_period": {"type": "int"},
            "renew_flag": {
                "choices": ["NOTIFY_AND_AUTO_RENEW", "NOTIFY_AND_MANUAL_RENEW", "DISABLE_NOTIFY_AND_MANUAL_RENEW"],
                "default": "NOTIFY_AND_MANUAL_RENEW",
            },
            "instance_id": {},
            "force_replace": {"type": "bool", "default": False},
            "force_detach": {"type": "bool", "default": False},
            "wait": {"type": "bool", "default": True},
        },
        required_one_of=[("disk_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.LighthouseClient, "lighthouse.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, disk=None)
            if current.get("Attached") and not p["force_detach"]:
                module.fail_json(msg="Disk is attached; set force_detach=true before deletion", disk=current)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                if current.get("Attached"):
                    module.sdk_call(client.DetachDisks, detach_request(models, current["DiskId"]))
                    if p["wait"]:
                        current = wait_disk(module, client, models, p, {"UNATTACHED"})
                module.sdk_call(client.TerminateDisks, delete_request(models, current["DiskId"]))
                current = wait_disk(module, client, models, p, set(), absent=True) if p["wait"] else None
            module.exit_json(changed=True, **(diff or {}), disk=current)
        if not current:
            missing = [key for key in ("name", "zone", "disk_size", "disk_type", "prepaid_period") if not p.get(key)]
            if missing:
                module.fail_json(msg="Required for disk creation: %s" % ", ".join(missing))
        immutable = current and any(
            p.get(key) is not None and current.get(field) != p[key] for key, field in (("zone", "Zone"), ("disk_size", "DiskSize"), ("disk_type", "DiskType"))
        )
        if immutable and not p["force_replace"]:
            module.fail_json(msg="Immutable disk attributes differ; set force_replace=true to recreate", disk=current)
        before = current
        target = {
            "DiskName": p.get("name"),
            "InstanceId": p.get("instance_id"),
            "Zone": p.get("zone"),
            "DiskSize": p.get("disk_size"),
            "DiskType": p.get("disk_type"),
        }
        needs_name = current and p.get("name") and current.get("DiskName") != p["name"]
        needs_attach = current and current.get("InstanceId") != p.get("instance_id")
        changed = not current or immutable or needs_name or needs_attach
        if not changed:
            module.exit_json(changed=False, disk=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if immutable:
                if current.get("Attached") and not p["force_detach"]:
                    module.fail_json(msg="Disk replacement requires force_detach=true", disk=current)
                if current.get("Attached"):
                    module.sdk_call(client.DetachDisks, detach_request(models, current["DiskId"]))
                    wait_disk(module, client, models, p, {"UNATTACHED"})
                module.sdk_call(client.TerminateDisks, delete_request(models, current["DiskId"]))
                wait_disk(module, client, models, p, set(), absent=True)
                current = None
            if not current:
                response = module.sdk_call(client.CreateDisks, create_request(models, p))
                p["disk_id"] = response.DiskIdSet[0]
                current = wait_disk(module, client, models, p, {"UNATTACHED", "ATTACHED"}) if p["wait"] else find(module, client, models, p)
            elif needs_name:
                module.sdk_call(client.ModifyDisksAttribute, update_request(models, current["DiskId"], p["name"]))
                current["DiskName"] = p["name"]
            if current.get("InstanceId") != p.get("instance_id"):
                if current.get("Attached"):
                    if not p["force_detach"]:
                        module.fail_json(msg="Changing disk attachment requires force_detach=true", disk=current)
                    module.sdk_call(client.DetachDisks, detach_request(models, current["DiskId"]))
                    current = wait_disk(module, client, models, p, {"UNATTACHED"}) if p["wait"] else current
                if p.get("instance_id"):
                    module.sdk_call(client.AttachDisks, attach_request(models, current["DiskId"], p["instance_id"], p["renew_flag"]))
                    current = wait_disk(module, client, models, p, {"ATTACHED"}) if p["wait"] else current
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), disk=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
