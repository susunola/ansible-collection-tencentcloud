#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: redis_instance
short_description: Manage Tencent Cloud Redis instances
version_added: "0.12.0"
description:
  - Create, rename and destroy Redis instances through the
    C(redis.v20180412) API.
  - This module is idempotent. Running it twice leaves the instance
    unchanged and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
  - An instance is identified by O(instance_id) or by O(name). Instance
    configuration (size, shards, replicas) is only applied at creation;
    use the console or a separate scaling module to change it afterwards.
options:
  state:
    description:
      - C(present) creates the instance when it does not exist and renames
        it when O(name) differs.
      - C(absent) destroys the instance (postpaid instances immediately,
        prepaid instances via the prepaid destroy flow).
    type: str
    choices: [present, absent]
    default: present
  instance_id:
    description:
      - ID of an existing instance, e.g. C(crs-xxxxxxxx).
      - When given, the module operates on that instance; otherwise it is
        matched by O(name).
    type: str
  name:
    description:
      - Name of the instance, written to V(CreateInstancesRequest.
        InstanceName) and V(ModifyInstanceRequest.InstanceName).
    type: str
  zone_name:
    description:
      - Availability zone of the instance, e.g. C(ap-guangzhou-3), written
        to V(CreateInstancesRequest.ZoneName).
      - Required when creating the instance.
    type: str
  type_id:
    description:
      - Instance type of the instance. C(1) is the standard edition and
        C(2) is the cluster edition, written to V(CreateInstancesRequest.
        TypeId).
      - Required when creating the instance.
    type: int
    choices: [1, 2]
  mem_size:
    description:
      - Memory size of the instance in MiB (multiples of 1024), written to
        V(CreateInstancesRequest.MemSize).
      - Required when creating the instance.
    type: int
  redis_shard_num:
    description:
      - Number of shards, written to V(CreateInstancesRequest.
        RedisShardNum).
      - Only applied at creation.
    type: int
    default: 1
  redis_replicas_num:
    description:
      - Number of read-only replicas per shard, written to
        V(CreateInstancesRequest.RedisReplicasNum).
      - Only applied at creation.
    type: int
    default: 1
  vpc_id:
    description:
      - ID of the VPC, written to V(CreateInstancesRequest.VpcId).
      - Only applied at creation.
    type: str
  subnet_id:
    description:
      - ID of the subnet, written to V(CreateInstancesRequest.SubnetId).
      - Only applied at creation.
    type: str
  password:
    description:
      - Password of the instance, written to V(CreateInstancesRequest.
        Password).
      - Only applied at creation; the value is masked from output
        automatically.
    type: str
  no_auth:
    description:
      - Disable password authentication when true, written to
        V(CreateInstancesRequest.NoAuth).
      - Only applied at creation.
    type: bool
    default: false
  project_id:
    description:
      - Project the instance belongs to, written to
        V(CreateInstancesRequest.ProjectId).
      - Only applied at creation.
    type: int
  security_group_id_list:
    description:
      - Security groups to bind at creation, written to
        V(CreateInstancesRequest.SecurityGroupIdList).
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
  - Requires the C(tencentcloud-sdk-python-redis) package on the controller.
  - Redis instances are billed while present; destroy them as soon as they
    are no longer needed to avoid unnecessary charges.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a 4 GiB standard Redis instance
  susunola.tencentcloud.redis_instance:
    region: ap-guangzhou
    state: present
    name: prod-cache
    zone_name: ap-guangzhou-3
    type_id: 1
    mem_size: 4096
    password: "{{ redis_password }}"
    tags:
      env: prod

- name: Rename it
  susunola.tencentcloud.redis_instance:
    region: ap-guangzhou
    state: present
    name: prod-cache-v2

- name: Destroy it
  susunola.tencentcloud.redis_instance:
    region: ap-guangzhou
    state: absent
    name: prod-cache-v2
'''

RETURN = r'''
instance:
  description: The instance as reported by V(DescribeInstances) after the
    operation.
  returned: success
  type: dict
  sample:
    InstanceId: crs-xxxxxxxx
    InstanceName: prod-cache
    Status: 0
    RedisShardSize: 4096
    ZoneId: 100003
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_redis():
    from tencentcloud.redis.v20180412 import models, redis_client
    return models, redis_client


def build_describe_request(models, instance_id, name):
    request = models.DescribeInstancesRequest()
    request.Limit = 100
    if instance_id:
        request.InstanceIds = [instance_id]
    elif name:
        request.InstanceName = name
    return request


def _first(collection):
    return collection[0] if collection else None


def find_instance(module, client, models, instance_id, name):
    """Return the matching instance dict or None."""
    request = build_describe_request(models, instance_id, name)
    response = module.sdk_call(client.DescribeInstances, request)
    if instance_id:
        instance = _first(response.InstanceSet or [])
        return instance._serialize(allow_none=True) if instance is not None else None
    for instance in response.InstanceSet or []:
        current = instance._serialize(allow_none=True)
        if current.get("InstanceName") == name:
            return current
    return None


def _create(module, client, models, params):
    request = models.CreateInstancesRequest()
    request.ZoneName = params["zone_name"]
    request.TypeId = params["type_id"]
    request.MemSize = params["mem_size"]
    request.GoodsNum = 1
    request.InstanceName = params["name"]
    if params["redis_shard_num"] is not None:
        request.RedisShardNum = params["redis_shard_num"]
    if params["redis_replicas_num"] is not None:
        request.RedisReplicasNum = params["redis_replicas_num"]
    if params["vpc_id"]:
        request.VpcId = params["vpc_id"]
    if params["subnet_id"]:
        request.SubnetId = params["subnet_id"]
    if params["password"]:
        request.Password = params["password"]
    if params["no_auth"]:
        request.NoAuth = True
    if params["project_id"] is not None:
        request.ProjectId = params["project_id"]
    if params["security_group_id_list"]:
        request.SecurityGroupIdList = params["security_group_id_list"]
    if params["tags"]:
        sdk_tags = []
        for key, value in sorted(params["tags"].items()):
            sdk_tag = models.ResourceTag()
            sdk_tag.TagKey = key
            sdk_tag.TagValue = value
            sdk_tags.append(sdk_tag)
        request.ResourceTags = sdk_tags
    response = module.sdk_call(client.CreateInstances, request)
    return _first(response.InstanceIds or [])


def _rename(module, client, models, instance_id, name):
    request = models.ModifyInstanceRequest()
    request.InstanceId = instance_id
    request.InstanceName = name
    module.sdk_call(client.ModifyInstance, request)


def _destroy(module, client, models, instance_id, billing_mode):
    if billing_mode == "PREPAID":
        request = models.DestroyPrepaidInstanceRequest()
    else:
        request = models.DestroyPostpaidInstanceRequest()
    request.InstanceId = instance_id
    module.sdk_call(client.DestroyPrepaidInstance if billing_mode == "PREPAID" else client.DestroyPostpaidInstance, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "instance_id": {"type": "str"},
            "name": {"type": "str"},
            "zone_name": {"type": "str"},
            "type_id": {"type": "int", "choices": [1, 2]},
            "mem_size": {"type": "int"},
            "redis_shard_num": {"type": "int", "default": 1},
            "redis_replicas_num": {"type": "int", "default": 1},
            "vpc_id": {"type": "str"},
            "subnet_id": {"type": "str"},
            "password": {"type": "str", "no_log": True},
            "no_auth": {"type": "bool", "default": False},
            "project_id": {"type": "int"},
            "security_group_id_list": {"type": "list", "elements": "str"},
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

    models, redis_client = _load_redis()
    client = module.create_client(redis_client.RedisClient, "redis.tencentcloudapi.com")

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
            module.exit_json(changed=False, msg="Redis instance already absent")
        target_id = current["InstanceId"]
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would destroy Redis instance")
        _destroy(module, client, models, target_id, current.get("BillingMode") or "POSTPAID")
        module.exit_json(changed=True, **(diff or {}), instance=None, msg="Redis instance destroyed")

    # state == present
    if current is None:
        missing = [key for key in ("zone_name", "type_id", "mem_size", "name") if not module.params[key]]
        if missing:
            module.fail_json(msg="%s is required when creating a Redis instance" % ", ".join(missing))
        desired = {
            "InstanceName": name,
            "MemSize": module.params["mem_size"],
            "ZoneName": module.params["zone_name"],
            "TypeId": module.params["type_id"],
        }
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create Redis instance")
        created_id = _create(module, client, models, module.params)
        current = find_instance(module, client, models, created_id, None)
        module.exit_json(changed=True, **(diff or {}), instance=current, msg="Redis instance created")

    target_id = current["InstanceId"]
    if name and current.get("InstanceName") != name:
        diff = maybe_diff(module, current, {"InstanceName": name})
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would rename Redis instance")
        _rename(module, client, models, target_id, name)
        updated = find_instance(module, client, models, target_id, None)
        module.exit_json(changed=True, **(diff or {}), instance=updated, msg="Redis instance renamed")

    module.exit_json(changed=False, instance=current, msg="Redis instance is up to date")


def main():
    run_module()


if __name__ == "__main__":
    main()
