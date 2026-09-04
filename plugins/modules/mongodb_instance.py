#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: mongodb_instance
short_description: Manage Tencent Cloud MongoDB instances
version_added: "0.13.0"
description:
  - Create, rename and isolate Tencent Cloud MongoDB instances through the
    C(mongodb.v20190725) API.
  - This module is idempotent. Running it twice leaves the instance
    unchanged and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
  - An instance is identified by O(instance_id) or by O(name). Instance
    configuration (memory, volume, version, VPC, cluster layout) is only
    applied at creation; scaling is out of scope for this module.
options:
  state:
    description:
      - C(present) creates the instance when it does not exist and renames
        it when O(name) differs.
      - C(absent) isolates the instance (the billing is stopped and the
        instance moves to the recycle bin; postpaid instances are then
        destroyed automatically after the retention period).
    type: str
    choices: [present, absent]
    default: present
  instance_id:
    description:
      - ID of an existing instance, e.g. C(cmgo-xxxxxxxx).
      - When given, the module operates on that instance; otherwise it is
        matched by O(name).
    type: str
  name:
    description:
      - Name of the instance, written to V(CreateDBInstanceRequest.
        InstanceName) and V(RenameInstanceRequest.NewName).
    type: str
  memory:
    description:
      - Memory size of the instance in GiB, written to
        V(CreateDBInstanceRequest.Memory).
      - Required when creating the instance.
    type: int
  volume:
    description:
      - Disk size of the instance in GiB, written to
        V(CreateDBInstanceRequest.Volume).
      - Required when creating the instance.
    type: int
  mongo_version:
    description:
      - MongoDB version of the instance, e.g. C(4.4) or C(5.0), written to
        V(CreateDBInstanceRequest.MongoVersion).
      - Required when creating the instance.
    type: str
  zone:
    description:
      - Availability zone of the instance, e.g. C(ap-guangzhou-3), written
        to V(CreateDBInstanceRequest.Zone).
      - Required when creating the instance.
    type: str
  cluster_type:
    description:
      - Architecture of the instance, written to
        V(CreateDBInstanceRequest.ClusterType).
      - C(REPLSET) is a replica set, C(SHARD) is a sharded cluster.
      - Required when creating the instance.
    type: str
    choices: [REPLSET, SHARD]
  node_num:
    description:
      - Number of nodes per replica set, written to
        V(CreateDBInstanceRequest.NodeNum).
      - Required for C(cluster_type=REPLSET) when creating.
    type: int
  replicate_set_num:
    description:
      - Number of shards for C(cluster_type=SHARD), written to
        V(CreateDBInstanceRequest.ReplicateSetNum).
      - Required for C(cluster_type=SHARD) when creating.
    type: int
  password:
    description:
      - Password of the instance, written to
        V(CreateDBInstanceRequest.Password).
      - Only applied at creation; the value is masked from output.
    type: str
  vpc_id:
    description:
      - ID of the VPC, written to V(CreateDBInstanceRequest.VpcId).
      - Only applied at creation.
    type: str
  subnet_id:
    description:
      - ID of the subnet, written to V(CreateDBInstanceRequest.SubnetId).
      - Only applied at creation.
    type: str
  project_id:
    description:
      - Project the instance belongs to, written to
        V(CreateDBInstanceRequest.ProjectId).
      - Only applied at creation.
    type: int
  period_months:
    description:
      - Prepaid period in months, written to
        V(CreateDBInstanceRequest.Period).
      - When given the instance is billed prepaid through
        V(CreateDBInstance); otherwise it is created postpaid through
        V(CreateDBInstanceHour).
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
  - Requires the C(tencentcloud-sdk-python-mongodb) package on the
    controller.
  - MongoDB instances are billed while present; isolate them as soon as
    they are no longer needed to avoid unnecessary charges.
  - Creation takes several minutes; the module returns as soon as the
    creation order is accepted.
  - The creation APIs size memory and disk in GiB, while V(DescribeDBInstances)
    reports them in MiB; the returned instance carries the raw API values.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a 4C8G MongoDB 5.0 replica set
  susunola.tencentcloud.mongodb_instance:
    region: ap-guangzhou
    state: present
    name: prod-mongo
    memory: 8
    volume: 100
    mongo_version: "5.0"
    zone: ap-guangzhou-3
    cluster_type: REPLSET
    node_num: 3
    password: "{{ mongo_password }}"
    tags:
      env: prod

- name: Rename it
  susunola.tencentcloud.mongodb_instance:
    region: ap-guangzhou
    state: present
    name: prod-mongo-v2

- name: Isolate it (stop billing)
  susunola.tencentcloud.mongodb_instance:
    region: ap-guangzhou
    state: absent
    name: prod-mongo-v2
'''

RETURN = r'''
instance:
  description: The instance as reported by V(DescribeDBInstances) after the
    operation.
  returned: success
  type: dict
  sample:
    InstanceId: cmgo-xxxxxxxx
    InstanceName: prod-mongo
    Status: 2
    Memory: 8192
    Volume: 102400
    MongoVersion: "5.0"
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_mongodb():
    from tencentcloud.mongodb.v20190725 import models, mongodb_client
    return models, mongodb_client


def build_describe_request(models, instance_id, name):
    request = models.DescribeDBInstancesRequest()
    request.Limit = 100
    if instance_id:
        request.InstanceIds = [instance_id]
    elif name:
        request.SearchKey = name
    return request


def _first(collection):
    return collection[0] if collection else None


def find_instance(module, client, models, instance_id, name):
    """Return the matching instance dict or None."""
    request = build_describe_request(models, instance_id, name)
    response = module.sdk_call(client.DescribeDBInstances, request)
    if instance_id:
        instance = _first(response.InstanceDetails or [])
        return instance._serialize(allow_none=True) if instance is not None else None
    for instance in response.InstanceDetails or []:
        current = instance._serialize(allow_none=True)
        if current.get("InstanceName") == name:
            return current
    return None


def _tag_models(models, tags):
    sdk_tags = []
    for key, value in sorted(tags.items()):
        sdk_tag = models.TagInfo()
        sdk_tag.TagKey = key
        sdk_tag.TagValue = value
        sdk_tags.append(sdk_tag)
    return sdk_tags


def build_create_request(models, params):
    request = models.CreateDBInstanceRequest()
    if params["node_num"]:
        request.NodeNum = params["node_num"]
    request.Memory = params["memory"]
    request.Volume = params["volume"]
    request.MongoVersion = params["mongo_version"]
    request.Zone = params["zone"]
    request.ClusterType = params["cluster_type"]
    request.GoodsNum = 1
    if params["name"]:
        request.InstanceName = params["name"]
    if params["period_months"] is not None:
        request.Period = params["period_months"]
    if params["replicate_set_num"] is not None:
        request.ReplicateSetNum = params["replicate_set_num"]
    if params["project_id"] is not None:
        request.ProjectId = params["project_id"]
    if params["vpc_id"]:
        request.VpcId = params["vpc_id"]
    if params["subnet_id"]:
        request.SubnetId = params["subnet_id"]
    if params["password"]:
        request.Password = params["password"]
    if params["auto_renew"] is not None:
        request.AutoRenewFlag = params["auto_renew"]
    if params["security_group"]:
        request.SecurityGroup = params["security_group"]
    if params["tags"]:
        request.Tags = _tag_models(models, params["tags"])
    return request


def _create(module, client, models, params):
    request = build_create_request(models, params)
    # Prepaid instances go through CreateDBInstance, postpaid through
    # CreateDBInstanceHour; both take the same request shape.
    operation = client.CreateDBInstance if params["period_months"] is not None else client.CreateDBInstanceHour
    response = module.sdk_call(operation, request)
    return _first(response.InstanceIds or [])


def _rename(module, client, models, instance_id, name):
    request = models.RenameInstanceRequest()
    request.InstanceId = instance_id
    request.NewName = name
    module.sdk_call(client.RenameInstance, request)


def _delete(module, client, models, instance_id):
    request = models.IsolateDBInstanceRequest()
    request.InstanceId = instance_id
    module.sdk_call(client.IsolateDBInstance, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "instance_id": {"type": "str"},
            "name": {"type": "str"},
            "memory": {"type": "int"},
            "volume": {"type": "int"},
            "mongo_version": {"type": "str"},
            "zone": {"type": "str"},
            "cluster_type": {"type": "str", "choices": ["REPLSET", "SHARD"]},
            "node_num": {"type": "int"},
            "replicate_set_num": {"type": "int"},
            "password": {"type": "str", "no_log": True},
            "vpc_id": {"type": "str"},
            "subnet_id": {"type": "str"},
            "project_id": {"type": "int"},
            "period_months": {"type": "int"},
            "auto_renew": {"type": "int"},
            "security_group": {"type": "list", "elements": "str"},
            "tags": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    instance_id = module.params["instance_id"]
    name = module.params["name"]

    if not instance_id and not name:
        module.fail_json(msg="instance_id or name is required to identify the instance")

    models, mongodb_client = _load_mongodb()
    client = module.create_client(
        mongodb_client.MongodbClient, "mongodb.tencentcloudapi.com"
    )

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
            module.exit_json(changed=False, msg="MongoDB instance already absent")
        target_id = current["InstanceId"]
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would isolate MongoDB instance")
        _delete(module, client, models, target_id)
        module.exit_json(changed=True, **(diff or {}), instance=None, msg="MongoDB instance isolated")

    # state == present
    if current is None:
        missing = [key for key in ("zone", "mongo_version", "memory", "volume", "cluster_type") if not module.params[key]]
        if missing:
            module.fail_json(msg="%s is required when creating a MongoDB instance" % ", ".join(missing))
        if module.params["cluster_type"] == "REPLSET" and not module.params["node_num"]:
            module.fail_json(msg="node_num is required when creating a REPLSET instance")
        if module.params["cluster_type"] == "SHARD" and not module.params["replicate_set_num"]:
            module.fail_json(msg="replicate_set_num is required when creating a SHARD instance")
        desired = {
            "InstanceName": name,
            "Zone": module.params["zone"],
            "MongoVersion": module.params["mongo_version"],
            "Memory": module.params["memory"],
            "Volume": module.params["volume"],
            "ClusterType": module.params["cluster_type"],
        }
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create MongoDB instance")
        created_id = _create(module, client, models, module.params)
        current = find_instance(module, client, models, created_id, None)
        module.exit_json(changed=True, **(diff or {}), instance=current, msg="MongoDB instance created")

    target_id = current["InstanceId"]
    if name and current.get("InstanceName") != name:
        diff = maybe_diff(module, current, {"InstanceName": name})
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would rename MongoDB instance")
        _rename(module, client, models, target_id, name)
        updated = find_instance(module, client, models, target_id, None)
        module.exit_json(changed=True, **(diff or {}), instance=updated, msg="MongoDB instance renamed")

    module.exit_json(changed=False, instance=current, msg="MongoDB instance is up to date")


def main():
    run_module()


if __name__ == "__main__":
    main()
