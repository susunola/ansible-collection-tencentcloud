#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cdwdoris_instance
short_description: Manage Tencent Cloud CDW Doris instances
version_added: "0.14.0"
description: Creates, renames, waits for and destroys CDW Doris instances.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  instance_id:
    description:
      - Existing instance ID.
    type: str
  name:
    description:
      - Instance name used for lookup and rename.
    type: str
  zone:
    description:
      - Creation-time availability zone.
    type: str
  fe_spec:
    description:
      - SDK CreateInstanceSpec payload for FE nodes.
    type: dict
  be_spec:
    description:
      - SDK CreateInstanceSpec payload for BE nodes.
    type: dict
  ha:
    description:
      - Creation-time high-availability flag.
    type: bool
  vpc_id:
    description:
      - Creation-time VPC ID.
    type: str
  subnet_id:
    description:
      - Creation-time subnet ID.
    type: str
  product_version:
    description:
      - Creation-time product version.
    type: str
  charge_properties:
    description:
      - SDK ChargeProperties payload.
    type: dict
  admin_password:
    description:
      - Initial Doris administrator password.
    type: str
  tags:
    description:
      - Creation-time tags.
    type: dict
  ha_type:
    description:
      - Creation-time HA type.
    type: int
  case_sensitive:
    description:
      - Whether table names are case-sensitive.
    type: int
  enable_multi_zones:
    description:
      - Whether multi-zone deployment is enabled.
    type: bool
  multi_zone_infos:
    description:
      - SDK NetworkInfo payloads for multi-zone deployment.
    type: list
    elements: dict
  is_ssc:
    description:
      - Whether storage-compute separation is enabled.
    type: bool
  ssc_cu:
    description:
      - Compute units for storage-compute separation.
    type: int
  cache_data_disk_size:
    description:
      - Size of the cache data disk attached to the instance, in GB.
    type: int
  wait:
    description:
      - Wait for serving or absent convergence.
    type: bool
    default: true

  waiter_delay:
    description:
      - Seconds between polling attempts.
    type: int
    default: 10
  waiter_timeout:
    description:
      - Overall polling timeout in seconds.
    type: int
    default: 1800

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
attributes:
  check_mode:
    description:
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  diff_mode:
    description:
      - Returns the difference between the observed and the requested state
        when the task runs with C(--diff).
    support: full
  idempotent:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
seealso:
  - module: susunola.tencentcloud.cdwdoris_instance_info
    description: Gather information about Tencent Cloud CDWDORIS instances.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cdwdoris_instance:
    name: analytics-doris
    zone: ap-guangzhou-3
    fe_spec: {SpecName: S_4_16_H, Count: 3, DiskSize: 100}
    be_spec: {SpecName: S_8_32_H, Count: 3, DiskSize: 500}
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    product_version: 2.1
    charge_properties: {ChargeType: POSTPAID_BY_HOUR}
    admin_password: "{{ vault_doris_password }}"

- name: Delete the instance
  susunola.tencentcloud.cdwdoris_instance:
    state: absent
    name: analytics-doris
    wait: true
"""
RETURN = r"""instance:
  description:
    - Effective CDW Doris instance metadata.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    InstanceId: doris-new-001
    InstanceName: doris-a
    Zone: ap-guangzhou-3
    Version: '2.1'
"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state, wait_for_task


def _load():
    from tencentcloud.cdwdoris.v20211228 import models, cdwdoris_client

    return models, cdwdoris_client


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
        x.TagKey, x.TagValue = str(key), str(value)
        result.append(x)
    return result


def describe_request(models, p, offset=0):
    r = models.DescribeInstancesRequest()
    r.SearchInstanceId = p.get("instance_id")
    r.SearchInstanceName = None if p.get("instance_id") else p.get("name")
    r.Offset, r.Limit = offset, 100
    return r


def state_request(models, instance_id):
    r = models.DescribeInstanceStateRequest()
    r.InstanceId = instance_id
    return r


def create_request(models, p):
    r = models.CreateInstanceNewRequest()
    r.Zone = p["zone"]
    r.FeSpec = _model(models.CreateInstanceSpec, p["fe_spec"])
    r.BeSpec = _model(models.CreateInstanceSpec, p["be_spec"])
    r.HaFlag = p.get("ha")
    r.UserVPCId, r.UserSubnetId = p["vpc_id"], p["subnet_id"]
    r.ProductVersion = p["product_version"]
    r.ChargeProperties = _model(models.ChargeProperties, p["charge_properties"])
    r.InstanceName, r.DorisUserPwd = p["name"], p["admin_password"]
    r.Tags = _tags(models, p.get("tags"))
    r.HaType, r.CaseSensitive = p.get("ha_type"), p.get("case_sensitive")
    r.EnableMultiZones = p.get("enable_multi_zones")
    r.UserMultiZoneInfoArr = [_model(models.NetworkInfo, x) for x in p.get("multi_zone_infos") or []]
    r.IsSSC, r.SSCCU = p.get("is_ssc"), p.get("ssc_cu")
    r.CacheDataDiskSize = p.get("cache_data_disk_size")
    return r


def update_request(models, instance_id, name):
    r = models.ModifyInstanceRequest()
    r.InstanceId, r.InstanceName = instance_id, name
    return r


def delete_request(models, instance_id):
    r = models.DestroyInstanceRequest()
    r.InstanceId = instance_id
    return r


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeInstances, describe_request(models, p, offset))
        page = response.InstancesList or []
        for item in page:
            value = item._serialize(allow_none=True)
            if (p.get("instance_id") and value.get("InstanceId") == p["instance_id"]) or (
                not p.get("instance_id") and value.get("InstanceName") == p.get("name")
            ):
                matches.append(value)
        offset += len(page)
        if not page or offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple CDW Doris instances matched; specify instance_id")
    return matches[0] if matches else None


def wait_present(module, client, models, p, name):
    def poll():
        current = find(module, client, models, p)
        if not current:
            return "RUNNING", None, current
        state = module.sdk_call(client.DescribeInstanceState, state_request(models, current["InstanceId"]))
        value = state.InstanceState
        if value == "Serving" and current.get("InstanceName") == name:
            return "SUCCESS", None, current
        if value in ("CreateFailed", "Failed"):
            return "FAILED", state.FlowMsg, current
        return "RUNNING", None, current

    return wait_for_task(module, poll, timeout=p["waiter_timeout"], delay=p["waiter_delay"], success_statuses=("SUCCESS",), failure_statuses=("FAILED",))


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "instance_id": {},
        "name": {},
        "zone": {},
        "fe_spec": {"type": "dict"},
        "be_spec": {"type": "dict"},
        "ha": {"type": "bool"},
        "vpc_id": {},
        "subnet_id": {},
        "product_version": {},
        "charge_properties": {"type": "dict"},
        "admin_password": {"no_log": True},
        "tags": {"type": "dict"},
        "ha_type": {"type": "int"},
        "case_sensitive": {"type": "int"},
        "enable_multi_zones": {"type": "bool"},
        "multi_zone_infos": {"type": "list", "elements": "dict"},
        "is_ssc": {"type": "bool"},
        "ssc_cu": {"type": "int"},
        "cache_data_disk_size": {"type": "int"},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 10},
        "waiter_timeout": {"type": "int", "default": 1800},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("instance_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CdwdorisClient, "cdwdoris.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, instance=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                p["instance_id"] = current["InstanceId"]
                module.sdk_call(client.DestroyInstance, delete_request(models, p["instance_id"]))
                (
                    wait_for_state(
                        module,
                        lambda: "absent" if find(module, client, models, p) is None else "present",
                        {"absent"},
                        timeout=p["waiter_timeout"],
                        delay=p["waiter_delay"],
                    )
                    if p["wait"]
                    else None
                )
            module.exit_json(changed=True, **(diff or {}), instance=None)
        if not current:
            required = ("name", "zone", "fe_spec", "be_spec", "vpc_id", "subnet_id", "product_version", "charge_properties", "admin_password")
            missing = [x for x in required if not p.get(x)]
            if missing:
                module.fail_json(msg="creation parameters are required for a CDW Doris instance", missing=missing)
            target = {"InstanceName": p["name"], "Zone": p["zone"], "Version": p["product_version"]}
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                response = module.sdk_call(client.CreateInstanceNew, create_request(models, p))
                if response.ErrorMsg:
                    module.fail_json(msg=response.ErrorMsg)
                p["instance_id"] = response.InstanceId
                current = wait_present(module, client, models, p, p["name"]) if p["wait"] else find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), instance=current if not module.check_mode else target)
        name = p.get("name") or current.get("InstanceName")
        if name == current.get("InstanceName"):
            module.exit_json(changed=False, instance=current)
        diff = maybe_diff(module, {"InstanceName": current.get("InstanceName")}, {"InstanceName": name})
        if not module.check_mode:
            p["instance_id"] = current["InstanceId"]
            module.sdk_call(client.ModifyInstance, update_request(models, p["instance_id"], name))
            current = wait_present(module, client, models, p, name) if p["wait"] else find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), instance=current if not module.check_mode else {"InstanceName": name})
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
