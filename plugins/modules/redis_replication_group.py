#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: redis_replication_group
short_description: Create or remove a TencentDB for Redis replication group
version_added: "1.1.0"
description:
  - Creates or removes a TencentDB for Redis replication group, identified by
    its group name. Creating a group seeds it from an existing Redis instance
    (which becomes the group's master), so I(instance_id) is required on create.
    The module is idempotent; it reads the current replication groups before
    changing anything and matches on the group name.
  - Removal detaches the group and its member instances. Because a replication
    group is a multi-instance reconcile object, this module only manages the
    group's existence, not per-instance membership (use the instance-level
    add/remove replication instance operations for that).
options:
  state:
    description: Desired state of the replication group.
    type: str
    choices: [present, absent]
    default: present
  group_name:
    description: Replication group name, used to identify the group.
    type: str
    required: true
  instance_id:
    description: ID of an existing Redis instance used to seed the group on create.
    type: str
  remark:
    description: Optional remark stored on the replication group.
    type: str
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a Redis replication group seeded from an instance
  susunola.tencentcloud.redis_replication_group:
    group_name: app-cache-ha
    instance_id: crs-abc123
    remark: primary-ha-group-for-app-cache

- name: Remove the replication group
  susunola.tencentcloud.redis_replication_group:
    group_name: app-cache-ha
    state: absent
'''

RETURN = r'''
group_name:
  description: Replication group name the operation targeted.
  returned: always
  type: str
group_id:
  description: Server-assigned group ID after a create, or the matched group ID.
  returned: always
  type: str
exists:
  description: Whether the replication group exists after the operation.
  returned: always
  type: bool
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def _load_redis():
    from tencentcloud.redis.v20180412 import models, redis_client
    return models, redis_client


def find_group(module, client, models, group_name):
    request = models.DescribeReplicationGroupRequest()
    request.SearchKey = group_name
    request.Limit = 100
    request.Offset = 0
    response = module.sdk_call(client.DescribeReplicationGroup, request)
    groups = list(getattr(response, "Groups", None) or [])
    for item in groups:
        if getattr(item, "GroupName", None) == group_name:
            return item
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "group_name": {"type": "str", "required": True},
            "instance_id": {"type": "str"},
            "remark": {"type": "str"},
        },
        required_if=[("state", "present", ("instance_id",))],
        supports_check_mode=True,
    )
    p = module.params
    group_name = p["group_name"]
    instance_id = p["instance_id"]
    remark = p["remark"]
    desired_present = p["state"] == "present"
    module.require_sdk()
    models, redis_client = _load_redis()
    client = module.create_client(redis_client.RedisClient, "redis.tencentcloudapi.com")
    try:
        current = find_group(module, client, models, group_name)
        if bool(current) == desired_present:
            module.exit_json(
                changed=False,
                group_name=group_name,
                group_id=getattr(current, "GroupId", None),
                exists=bool(current),
                msg="Redis replication group already %s" % ("present" if desired_present else "absent"),
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                group_name=group_name,
                group_id=None,
                exists=desired_present,
                msg="Would %s Redis replication group" % ("create" if desired_present else "delete"),
            )
        if desired_present:
            request = models.CreateReplicationGroupRequest()
            request.GroupName = group_name
            request.InstanceId = instance_id
            request.Remark = remark
            response = module.sdk_call(client.CreateReplicationGroup, request)
            created_id = getattr(response, "GroupId", None)
        else:
            request = models.RemoveReplicationGroupRequest()
            request.GroupId = getattr(current, "GroupId", None)
            module.sdk_call(client.RemoveReplicationGroup, request)
            created_id = None
        final = find_group(module, client, models, group_name)
        module.exit_json(
            changed=True,
            group_name=group_name,
            group_id=created_id if desired_present else (getattr(final, "GroupId", None) if final else None),
            exists=bool(final),
            msg="Redis replication group %s" % ("created" if desired_present else "removed"),
        )
    except Exception as exc:
        module.fail_sdk_error(exc, "Tencent Cloud Redis replication group request failed")


def main():
    run_module()


if __name__ == "__main__":
    main()
