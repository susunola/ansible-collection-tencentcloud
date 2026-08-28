#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cdb_instance
short_description: Manage Tencent Cloud CDB MySQL instances
version_added: "0.12.0"
description:
  - Create, rename, restart and isolate CDB MySQL instances through the
    C(cdb.v20170320) API.
  - This module is idempotent. Running it twice leaves the instance
    unchanged and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
  - An instance is identified by O(instance_id) or by O(name). Zone,
    engine version, VPC and password are only applied at creation; when
    O(memory) or O(volume) drift from the running instance the module
    changes the specification with V(UpgradeDBInstance) and waits for
    the asynchronous spec-change task to report C(SUCCESS).
options:
  state:
    description:
      - C(present) creates the instance when it does not exist and renames
        it when O(name) differs. After creation the module waits for the
        instance to be delivered (Status 1 with TaskStatus 0) before
        returning, bounded by O(waiter_timeout).
      - C(absent) isolates the instance (the billing is stopped and the
        instance moves to the recycle bin; postpaid instances are then
        destroyed automatically after the retention period). The module
        waits for the isolation to complete (Status 5) before returning,
        bounded by O(waiter_timeout).
      - C(restarted) restarts a running instance with
        V(RestartDBInstances) and waits for the asynchronous restart task
        to report C(SUCCESS).
      - Restart is a one-shot action - every run with C(state=restarted)
        issues a restart; the instance must be running (Status 1) with no
        other async task in progress.
    type: str
    choices: [present, absent, restarted]
    default: present
  instance_id:
    description:
      - ID of an existing instance, e.g. C(cdb-xxxxxxxx).
      - When given, the module operates on that instance; otherwise it is
        matched by O(name).
    type: str
  name:
    description:
      - Name of the instance, written to V(CreateDBInstanceRequest.
        InstanceName) and V(ModifyDBInstanceNameRequest.InstanceName).
    type: str
  zone:
    description:
      - Availability zone of the instance, e.g. C(ap-guangzhou-3), written
        to V(CreateDBInstanceRequest.Zone).
      - Required when creating the instance.
    type: str
  engine_version:
    description:
      - MySQL version of the instance, e.g. C(5.7) or C(8.0), written to
        V(CreateDBInstanceRequest.EngineVersion).
      - Required when creating the instance.
    type: str
  memory:
    description:
      - Memory size of the instance in MiB, written to
        V(CreateDBInstanceRequest.Memory) at creation and to
        V(UpgradeDBInstanceRequest.Memory) when it drifts from an
        existing instance.
      - Required when creating the instance; optional on an existing
        instance, where it triggers a specification change when it
        differs from the current value.
    type: int
  volume:
    description:
      - Disk size of the instance in GiB, written to
        V(CreateDBInstanceRequest.Volume) at creation and to
        V(UpgradeDBInstanceRequest.Volume) when it drifts from an
        existing instance.
      - Required when creating the instance; optional on an existing
        instance, where it triggers a specification change when it
        differs from the current value.
    type: int
  password:
    description:
      - Root password of the instance, written to
        V(CreateDBInstanceRequest.Password).
      - Only applied at creation; the value is masked from output.
    type: str
  vpc_id:
    description:
      - ID of the VPC, written to V(CreateDBInstanceRequest.UniqVpcId).
      - Only applied at creation.
    type: str
  subnet_id:
    description:
      - ID of the subnet, written to V(CreateDBInstanceRequest.UniqSubnetId).
      - Only applied at creation.
    type: str
  project_id:
    description:
      - Project the instance belongs to, written to
        V(CreateDBInstanceRequest.ProjectId) and
        V(ModifyDBInstanceNameRequest) via the project attribute.
    type: int
  period_months:
    description:
      - Prepaid period in months, written to V(CreateDBInstanceRequest.
        Period).
      - When given the instance is billed prepaid; otherwise it is created
        postpaid.
    type: int
  auto_renew:
    description:
      - Auto-renew the prepaid instance, written to
        V(CreateDBInstanceRequest.AutoRenewFlag).
    type: int
  security_group:
    description:
      - Security groups to bind at creation, written to
        V(CreateDBInstanceRequest.SecurityGroup).
    type: list
    elements: str
  tags:
    description:
      - Tags to apply to the instance as a dict, for example I(env=prod).
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
    description:
      - Overall timeout in seconds for lifecycle state polling; it bounds
        creation delivery (Status 1 with TaskStatus 0), isolation
        (Status 5), the restart task and the spec-change task.
      - Database creation and specification changes take several minutes,
        so the default is 900 seconds; lower it when the playbook only
        renames an existing instance.
    type: int
    default: 900
  user_agent:
    description:
      - Value appended to the SDK User-Agent header so API usage can be
        attributed to this collection.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-cdb) package on the controller.
  - CDB instances are billed while present; isolate them as soon as they
    are no longer needed to avoid unnecessary charges.
  - Creation takes several minutes; after the creation order is accepted
    the module waits for the instance to be delivered (Status 1 with
    TaskStatus 0) before returning.
  - Restart is asynchronous on the CDB side; the module polls
    V(DescribeAsyncRequestInfo) until the task reports C(SUCCESS) or
    fails, bounded by O(waiter_timeout).
  - Specification changes (V(UpgradeDBInstance)) are also asynchronous;
    the module waits for the C(SUCCESS) task outcome before returning.
    The API supports both upgrade and downgrade of the specification;
    note that disk capacity can only be expanded, never reduced. For
    valid Memory and Volume values use the DescribeDBInstanceConfig
    salesable-spec API.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a 4C8G MySQL 8.0 instance
  susunola.tencentcloud.cdb_instance:
    region: ap-guangzhou
    state: present
    name: prod-mysql
    zone: ap-guangzhou-3
    engine_version: "8.0"
    memory: 8000
    volume: 100
    password: "{{ mysql_root_password }}"
    tags:
      env: prod

- name: Rename it
  susunola.tencentcloud.cdb_instance:
    region: ap-guangzhou
    state: present
    name: prod-mysql-v2

- name: Resize it (waits for the async spec-change task)
  susunola.tencentcloud.cdb_instance:
    region: ap-guangzhou
    state: present
    instance_id: cdb-xxxxxxxx
    memory: 16000
    volume: 200

- name: Restart it (waits for the async restart task)
  susunola.tencentcloud.cdb_instance:
    region: ap-guangzhou
    state: restarted
    instance_id: cdb-xxxxxxxx

- name: Isolate it (stop billing)
  susunola.tencentcloud.cdb_instance:
    region: ap-guangzhou
    state: absent
    name: prod-mysql-v2
'''

RETURN = r'''
instance:
  description: The instance as reported by V(DescribeDBInstances) after the
    operation.
  returned: success
  type: dict
  sample:
    InstanceId: cdb-xxxxxxxx
    InstanceName: prod-mysql
    Status: 1
    Memory: 8000
    Volume: 100
    EngineVersion: "8.0"
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import (
    wait_for_state,
    wait_for_task,
)


def _load_cdb():
    from tencentcloud.cdb.v20170320 import models, cdb_client
    return models, cdb_client


def build_describe_request(models, instance_id, name):
    request = models.DescribeDBInstancesRequest()
    request.Limit = 100
    if instance_id:
        request.InstanceIds = [instance_id]
    elif name:
        request.InstanceNames = [name]
    return request


def _first(collection):
    return collection[0] if collection else None


def find_instance(module, client, models, instance_id, name):
    """Return the matching instance dict or None."""
    request = build_describe_request(models, instance_id, name)
    response = module.sdk_call(client.DescribeDBInstances, request)
    if instance_id:
        instance = _first(response.Items or [])
        return instance._serialize(allow_none=True) if instance is not None else None
    for instance in response.Items or []:
        current = instance._serialize(allow_none=True)
        if current.get("InstanceName") == name:
            return current
    return None


def _create(module, client, models, params):
    request = models.CreateDBInstanceRequest()
    request.Zone = params["zone"]
    request.EngineVersion = params["engine_version"]
    request.Memory = params["memory"]
    request.Volume = params["volume"]
    request.GoodsNum = 1
    request.InstanceName = params["name"]
    if params["password"]:
        request.Password = params["password"]
    if params["vpc_id"]:
        request.UniqVpcId = params["vpc_id"]
    if params["subnet_id"]:
        request.UniqSubnetId = params["subnet_id"]
    if params["project_id"] is not None:
        request.ProjectId = params["project_id"]
    if params["period_months"] is not None:
        request.Period = params["period_months"]
    if params["auto_renew"] is not None:
        request.AutoRenewFlag = params["auto_renew"]
    if params["security_group"]:
        request.SecurityGroup = params["security_group"]
    if params["tags"]:
        sdk_tags = []
        for key, value in sorted(params["tags"].items()):
            sdk_tag = models.TagInfoUnit()
            sdk_tag.TagKey = key
            sdk_tag.TagValue = value
            sdk_tags.append(sdk_tag)
        request.ResourceTags = sdk_tags
    response = module.sdk_call(client.CreateDBInstance, request)
    return _first(response.InstanceIds or [])


def _rename(module, client, models, instance_id, name):
    request = models.ModifyDBInstanceNameRequest()
    request.InstanceId = instance_id
    request.InstanceName = name
    module.sdk_call(client.ModifyDBInstanceName, request)


def _delete(module, client, models, instance_id):
    request = models.IsolateDBInstanceRequest()
    request.InstanceId = instance_id
    module.sdk_call(client.IsolateDBInstance, request)


def _delivered_poll(module, client, models, instance_id):
    """Poll returning ``(Status, TaskStatus)``; None while not yet visible."""
    def poll():
        current = find_instance(module, client, models, instance_id, None)
        if current is None:
            return None
        return current.get("Status"), current.get("TaskStatus")
    return poll


def _wait_delivered(module, client, models, instance_id):
    """Wait until the created instance is delivered.

    The CreateDBInstanceHour documentation defines delivery as Status 1
    (running) with TaskStatus 0 (no task in progress).
    """
    return wait_for_state(
        module,
        _delivered_poll(module, client, models, instance_id),
        [(1, 0)],
        timeout=module.params["waiter_timeout"],
        delay=module.params["waiter_delay"],
    )


def _status_poll(module, client, models, instance_id, gone_terminal=None):
    """Poll returning the instance Status; ``gone_terminal`` when missing.

    The destroy/isolate paths can end with the instance disappearing from
    the describe API once recycling completes; ``gone_terminal`` reports a
    missing instance as that terminal status instead of polling forever.
    """
    def poll():
        current = find_instance(module, client, models, instance_id, None)
        if current is None:
            return gone_terminal
        return current.get("Status")
    return poll


def _wait_status(module, client, models, instance_id, desired_states, gone_terminal=None):
    """Wait until the instance Status is one of ``desired_states``."""
    return wait_for_state(
        module,
        _status_poll(module, client, models, instance_id, gone_terminal),
        desired_states,
        timeout=module.params["waiter_timeout"],
        delay=module.params["waiter_delay"],
    )


def build_restart_request(models, instance_id):
    request = models.RestartDBInstancesRequest()
    request.InstanceIds = [instance_id]
    return request


def build_task_status_request(models, task_id):
    request = models.DescribeAsyncRequestInfoRequest()
    request.AsyncRequestId = task_id
    return request


def _restart(module, client, models, instance_id):
    """Restart the instance and wait for the async restart task.

    ``RestartDBInstances`` returns an ``AsyncRequestId`` that the official
    documentation says to query with ``DescribeAsyncRequestInfo``. Its
    ``Status`` is a string (INITIAL/RUNNING/SUCCESS/FAILED/KILLED/REMOVED/
    PAUSED), a different convention from the CLB task API, so the generic
    waiter is told which values are terminal.
    """
    response = module.sdk_call(client.RestartDBInstances, build_restart_request(models, instance_id))
    task_id = getattr(response, "AsyncRequestId", None)
    if task_id is None:
        module.fail_json(
            msg="RestartDBInstances returned no AsyncRequestId; cannot track "
                "the asynchronous restart task",
            instance_id=instance_id,
        )

    def poll():
        task_response = module.sdk_call(
            client.DescribeAsyncRequestInfo,
            build_task_status_request(models, task_id),
        )
        return task_response.Status, task_response.Info, task_response

    wait_for_task(
        module,
        poll,
        timeout=module.params["waiter_timeout"],
        delay=module.params["waiter_delay"],
        success_statuses=("SUCCESS",),
        failure_statuses=("FAILED", "KILLED", "REMOVED", "PAUSED"),
    )


def build_upgrade_request(models, instance_id, memory, volume):
    request = models.UpgradeDBInstanceRequest()
    request.InstanceId = instance_id
    request.Memory = memory
    request.Volume = volume
    return request


def _upgrade(module, client, models, instance_id, memory, volume):
    """Change the instance specification and wait for the async task.

    ``UpgradeDBInstance`` changes (upgrades or downgrades) the memory and
    disk of an existing instance. It returns an ``AsyncRequestId`` that
    the official documentation says to query with
    ``DescribeAsyncRequestInfo`` - the same polling pattern as the
    restart path, so the string-status waiter is reused verbatim.
    """
    response = module.sdk_call(
        client.UpgradeDBInstance,
        build_upgrade_request(models, instance_id, memory, volume),
    )
    task_id = getattr(response, "AsyncRequestId", None)
    if task_id is None:
        module.fail_json(
            msg="UpgradeDBInstance returned no AsyncRequestId; cannot track "
                "the asynchronous spec-change task",
            instance_id=instance_id,
        )

    def poll():
        task_response = module.sdk_call(
            client.DescribeAsyncRequestInfo,
            build_task_status_request(models, task_id),
        )
        return task_response.Status, task_response.Info, task_response

    wait_for_task(
        module,
        poll,
        timeout=module.params["waiter_timeout"],
        delay=module.params["waiter_delay"],
        success_statuses=("SUCCESS",),
        failure_statuses=("FAILED", "KILLED", "REMOVED", "PAUSED"),
    )


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent", "restarted"], "default": "present"},
            "instance_id": {"type": "str"},
            "name": {"type": "str"},
            "zone": {"type": "str"},
            "engine_version": {"type": "str"},
            "memory": {"type": "int"},
            "volume": {"type": "int"},
            "password": {"type": "str", "no_log": True},
            "vpc_id": {"type": "str"},
            "subnet_id": {"type": "str"},
            "project_id": {"type": "int"},
            "period_months": {"type": "int"},
            "auto_renew": {"type": "int"},
            "security_group": {"type": "list", "elements": "str"},
            "tags": {"type": "dict", "default": {}},
            "waiter_timeout": {"type": "int", "default": 900},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    instance_id = module.params["instance_id"]
    name = module.params["name"]

    if not instance_id and not name:
        module.fail_json(msg="instance_id or name is required to identify the instance")

    models, cdb_client = _load_cdb()
    client = module.create_client(cdb_client.CdbClient, "cdb.tencentcloudapi.com")

    try:
        current = find_instance(module, client, models, instance_id, name)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="CDB instance already absent")
        target_id = current["InstanceId"]
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would isolate CDB instance")
        _delete(module, client, models, target_id)
        _wait_status(module, client, models, target_id, [5])
        isolated = find_instance(module, client, models, target_id, None)
        module.exit_json(changed=True, **(diff or {}), instance=isolated, msg="CDB instance isolated")

    if state == "restarted":
        if current is None:
            module.fail_json(
                msg="CDB instance not found; use state=present to create it",
                instance_id=instance_id,
                name=name,
            )
        target_id = current["InstanceId"]
        current_status = current.get("Status")
        if current_status != 1:
            module.fail_json(
                msg="Restart requires a running instance (Status 1) with no "
                    "async task in progress; current Status is %s" % current_status,
                instance=current,
            )
        diff = maybe_diff(module, {"Status": 1}, {"Status": 1, "Restarted": True})
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would restart CDB instance")
        _restart(module, client, models, target_id)
        updated = find_instance(module, client, models, target_id, None)
        module.exit_json(changed=True, **(diff or {}), instance=updated, msg="CDB instance restarted")

    # state == present
    if current is None:
        missing = [key for key in ("zone", "engine_version", "memory", "volume", "name") if not module.params[key]]
        if missing:
            module.fail_json(msg="%s is required when creating a CDB instance" % ", ".join(missing))
        desired = {
            "InstanceName": name,
            "Zone": module.params["zone"],
            "EngineVersion": module.params["engine_version"],
            "Memory": module.params["memory"],
            "Volume": module.params["volume"],
        }
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create CDB instance")
        created_id = _create(module, client, models, module.params)
        _wait_delivered(module, client, models, created_id)
        current = find_instance(module, client, models, created_id, None)
        module.exit_json(changed=True, **(diff or {}), instance=current, msg="CDB instance created")

    target_id = current["InstanceId"]
    if name and current.get("InstanceName") != name:
        diff = maybe_diff(module, current, {"InstanceName": name})
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would rename CDB instance")
        _rename(module, client, models, target_id, name)
        updated = find_instance(module, client, models, target_id, None)
        module.exit_json(changed=True, **(diff or {}), instance=updated, msg="CDB instance renamed")

    memory = module.params["memory"]
    volume = module.params["volume"]
    if memory is not None or volume is not None:
        desired = {}
        if memory is not None and current.get("Memory") != memory:
            desired["Memory"] = memory
        if volume is not None and current.get("Volume") != volume:
            desired["Volume"] = volume
        if desired:
            diff = maybe_diff(module, current, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would resize CDB instance")
            _upgrade(
                module,
                client,
                models,
                target_id,
                memory if memory is not None else current.get("Memory"),
                volume if volume is not None else current.get("Volume"),
            )
            updated = find_instance(module, client, models, target_id, None)
            module.exit_json(changed=True, **(diff or {}), instance=updated, msg="CDB instance resized")

    module.exit_json(changed=False, instance=current, msg="CDB instance is up to date")


def main():
    run_module()


if __name__ == "__main__":
    main()
