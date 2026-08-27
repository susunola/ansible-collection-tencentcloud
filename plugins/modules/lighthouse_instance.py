#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: lighthouse_instance
short_description: Manage Tencent Cloud Lighthouse instances
version_added: "0.12.0"
description:
  - Create, start, stop and isolate Tencent Cloud Lighthouse instances
    through the C(lighthouse.v20200324) API.
  - This module is idempotent. Running it twice leaves the instance
    unchanged and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the instance with V(CreateInstances) when it does
        not exist, and updates its display name when it does.
      - C(absent) isolates the instance with V(IsolateInstances) (the
        Lighthouse deletion flow starts with isolation; the instance becomes
        unavailable and can no longer be started).
      - C(running) starts a stopped instance with V(StartInstances) and waits
        for the V(RUNNING) state.
      - C(stopped) stops a running instance with V(StopInstances) and waits
        for the V(STOPPED) state.
    type: str
    choices: [present, absent, running, stopped]
    default: present
  instance_id:
    description:
      - ID of an existing instance, e.g. C(lhins-xxxxxxxx).
      - When given, the module operates on that instance; otherwise the
        instance is matched by O(instance_name) through the C(instance-name)
        filter and the first match is used.
    type: str
  instance_name:
    description:
      - Display name of the instance.
      - Used to look up the instance when O(instance_id) is not given, and as
        the desired name to enforce on an existing instance.
    type: str
  bundle_id:
    description:
      - Instance bundle (套餐) ID, e.g. C(bundle_xxx).
      - Required when the instance does not exist yet; only applied at
        creation.
    type: str
  blueprint_id:
    description:
      - Blueprint (镜像) ID, e.g. C(lhbp-xxxxxxxx).
      - Required when the instance does not exist yet; only applied at
        creation.
    type: str
  zones:
    description:
      - Availability zone(s) for creation, e.g. C([ap-guangzhou-3]).
      - Written to V(CreateInstancesRequest.Zones). Only applied at creation.
    type: list
    elements: str
  instance_count:
    description:
      - Number of instances to create in one V(CreateInstances) call.
      - Only applied at creation.
    type: int
    default: 1
  password:
    description:
      - Login password written to V(LoginConfiguration.Password).
      - Only applied at creation; changing it on an existing instance fails
        with a message asking to reset the password manually.
    type: str
  prepaid_period:
    description:
      - Prepaid period in months written to V(InstanceChargePrepaid.Period).
      - Only applied at creation; leave unset for postpaid (按量) instances.
    type: int
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
  - Requires the C(tencentcloud-sdk-python-lighthouse) package on the
    controller.
  - Lighthouse has no synchronous delete API; C(state=absent) isolates the
    instance, which is the first and irreversible step of the refund/delete
    flow. Isolated instances cannot be started again.
  - Changing O(bundle_id), O(blueprint_id), O(zones), O(password) or
    O(instance_count) on an existing instance is not supported; the module
    fails with a message asking to recreate the instance.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a Lighthouse instance
  susunola.tencentcloud.lighthouse_instance:
    region: ap-guangzhou
    state: present
    instance_name: blog-01
    bundle_id: bundle_2022_std_1c1g
    blueprint_id: lhbp-xxxxxxxx
    zones:
      - ap-guangzhou-3
    password: "{{ vault_lh_password }}"

- name: Stop an instance
  susunola.tencentcloud.lighthouse_instance:
    region: ap-guangzhou
    state: stopped
    instance_name: blog-01

- name: Start an instance
  susunola.tencentcloud.lighthouse_instance:
    region: ap-guangzhou
    state: running
    instance_name: blog-01

- name: Isolate (delete) an instance
  susunola.tencentcloud.lighthouse_instance:
    region: ap-guangzhou
    state: absent
    instance_name: blog-01
'''

RETURN = r'''
instance:
  description: The instance as reported by V(DescribeInstances) after the operation.
  returned: success
  type: dict
  sample:
    InstanceId: lhins-xxxxxxxx
    InstanceName: blog-01
    InstanceState: RUNNING
    BundleId: bundle_2022_std_1c1g
    BlueprintId: lhbp-xxxxxxxx
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load_lighthouse():
    from tencentcloud.lighthouse.v20200324 import models, lighthouse_client
    return models, lighthouse_client


def build_describe_request(models, instance_id, instance_name):
    request = models.DescribeInstancesRequest()
    request.Offset = 0
    request.Limit = 100
    if instance_id:
        request.InstanceIds = [instance_id]
    elif instance_name:
        name_filter = models.Filter()
        name_filter.Name = "instance-name"
        name_filter.Values = [instance_name]
        request.Filters = [name_filter]
    return request


def _first(collection):
    return collection[0] if collection else None


def find_instance(module, client, models, instance_id, instance_name):
    """Return the matching instance dict or None."""
    request = build_describe_request(models, instance_id, instance_name)
    response = module.sdk_call(client.DescribeInstances, request)
    instance = _first(response.InstanceSet or [])
    if instance is None:
        return None
    return instance._serialize(allow_none=True)


def build_create_request(models, params):
    request = models.CreateInstancesRequest()
    request.BundleId = params["bundle_id"]
    request.BlueprintId = params["blueprint_id"]
    request.InstanceCount = params["instance_count"]
    if params["instance_name"]:
        request.InstanceName = params["instance_name"]
    if params["zones"]:
        request.Zones = params["zones"]
    if params["password"]:
        login = models.LoginConfiguration()
        login.Password = params["password"]
        request.LoginConfiguration = login
    if params["prepaid_period"] is not None:
        prepaid = models.InstanceChargePrepaid()
        prepaid.Period = params["prepaid_period"]
        request.InstanceChargePrepaid = prepaid
    return request


def _create(module, client, models, params):
    request = build_create_request(models, params)
    return module.sdk_call(client.CreateInstances, request)


def _update_name(module, client, models, instance_id, instance_name):
    request = models.ModifyInstancesAttributeRequest()
    request.InstanceIds = [instance_id]
    request.InstanceName = instance_name
    module.sdk_call(client.ModifyInstancesAttribute, request)


def _start(module, client, models, instance_id):
    request = models.StartInstancesRequest()
    request.InstanceIds = [instance_id]
    module.sdk_call(client.StartInstances, request)


def _stop(module, client, models, instance_id):
    request = models.StopInstancesRequest()
    request.InstanceIds = [instance_id]
    module.sdk_call(client.StopInstances, request)


def _isolate(module, client, models, instance_id):
    request = models.IsolateInstancesRequest()
    request.InstanceIds = [instance_id]
    module.sdk_call(client.IsolateInstances, request)


def _state_poll(module, client, models, instance_id):
    def poll():
        current = find_instance(module, client, models, instance_id, None)
        if current is None:
            return "GONE"
        return current.get("InstanceState")
    return poll


def _wait_state(module, client, models, instance_id, desired_states):
    return wait_for_state(
        module,
        _state_poll(module, client, models, instance_id),
        desired_states,
        timeout=module.params["waiter_timeout"],
        delay=module.params["waiter_delay"],
    )


def _immutable_drift(current, params):
    """Return the creation-only fields that drifted on an existing instance."""
    drifted = []
    if params["bundle_id"] and current.get("BundleId") != params["bundle_id"]:
        drifted.append("bundle_id")
    if params["blueprint_id"] and current.get("BlueprintId") != params["blueprint_id"]:
        drifted.append("blueprint_id")
    if params["password"]:
        drifted.append("password")
    if params["instance_count"] != 1:
        drifted.append("instance_count")
    return drifted


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent", "running", "stopped"], "default": "present"},
            "instance_id": {"type": "str"},
            "instance_name": {"type": "str"},
            "bundle_id": {"type": "str"},
            "blueprint_id": {"type": "str"},
            "zones": {"type": "list", "elements": "str"},
            "instance_count": {"type": "int", "default": 1},
            "password": {"type": "str", "no_log": True},
            "prepaid_period": {"type": "int"},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    instance_id = module.params["instance_id"]
    instance_name = module.params["instance_name"]

    if state in ("absent", "running", "stopped") and not instance_id and not instance_name:
        module.fail_json(msg="instance_id or instance_name is required when state=%s" % state)

    models, lighthouse_client = _load_lighthouse()
    client = module.create_client(
        lighthouse_client.LighthouseClient, "lighthouse.tencentcloudapi.com"
    )

    try:
        current = find_instance(module, client, models, instance_id, instance_name)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None or current.get("InstanceState") in ("ISOLATED", "TERMINATED"):
            module.exit_json(changed=False, msg="Instance already absent")
        target_id = current["InstanceId"]
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would isolate instance")
        _isolate(module, client, models, target_id)
        module.exit_json(changed=True, **(diff or {}), instance=None, msg="Instance isolated")

    if state in ("running", "stopped"):
        if current is None:
            module.fail_json(
                msg="Instance not found; use state=present to create it",
                instance_id=instance_id,
                instance_name=instance_name,
            )
        target_id = current["InstanceId"]
        current_state = current.get("InstanceState")
        if state == "running":
            if current_state == "RUNNING":
                module.exit_json(changed=False, instance=current, msg="Instance already running")
            if current_state not in ("STOPPED", "STOPPING"):
                module.fail_json(
                    msg="Instance is in state %s; it must be STOPPED before starting" % current_state,
                    instance=current,
                )
            diff = maybe_diff(module, {"InstanceState": "STOPPED"}, {"InstanceState": "RUNNING"})
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would start instance")
            _start(module, client, models, target_id)
            _wait_state(module, client, models, target_id, ["RUNNING"])
            updated = find_instance(module, client, models, target_id, None)
            module.exit_json(changed=True, **(diff or {}), instance=updated, msg="Instance started")
        # state == "stopped"
        if current_state == "STOPPED":
            module.exit_json(changed=False, instance=current, msg="Instance already stopped")
        if current_state not in ("RUNNING", "STARTING"):
            module.fail_json(
                msg="Instance is in state %s; it must be RUNNING before stopping" % current_state,
                instance=current,
            )
        diff = maybe_diff(module, {"InstanceState": "RUNNING"}, {"InstanceState": "STOPPED"})
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would stop instance")
        _stop(module, client, models, target_id)
        _wait_state(module, client, models, target_id, ["STOPPED"])
        updated = find_instance(module, client, models, target_id, None)
        module.exit_json(changed=True, **(diff or {}), instance=updated, msg="Instance stopped")

    # state == present
    if current is None:
        if not module.params["bundle_id"] or not module.params["blueprint_id"]:
            module.fail_json(
                msg="bundle_id and blueprint_id are required when creating an instance"
            )
        desired = {
            "InstanceName": instance_name,
            "BundleId": module.params["bundle_id"],
            "BlueprintId": module.params["blueprint_id"],
            "Zones": module.params["zones"],
        }
        desired = {key: value for key, value in desired.items() if value is not None}
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create instance")
        response = _create(module, client, models, module.params)
        created_ids = response.InstanceIdSet or []
        if not created_ids:
            module.fail_json(msg="CreateInstances returned no instance IDs")
        new_id = created_ids[0]
        _wait_state(module, client, models, new_id, ["RUNNING"])
        created = find_instance(module, client, models, new_id, None)
        module.exit_json(changed=True, **(diff or {}), instance=created, msg="Instance created")

    target_id = current["InstanceId"]
    drifted = _immutable_drift(current, module.params)
    if drifted:
        module.fail_json(
            msg=(
                "Fields %s cannot be changed on an existing instance; "
                "recreate the instance to apply them" % ", ".join(drifted)
            ),
            instance=current,
        )

    if instance_name and current.get("InstanceName") != instance_name:
        diff = maybe_diff(
            module,
            {"InstanceName": current.get("InstanceName")},
            {"InstanceName": instance_name},
        )
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would update instance name")
        _update_name(module, client, models, target_id, instance_name)
        updated = find_instance(module, client, models, target_id, None)
        module.exit_json(changed=True, **(diff or {}), instance=updated, msg="Instance name updated")

    module.exit_json(changed=False, instance=current, msg="Instance is up to date")


def main():
    run_module()


if __name__ == "__main__":
    main()
