#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: ckafka_acl
short_description: Manage Tencent Cloud CKafka ACL entries
version_added: "0.14.0"
description: Creates and deletes exact CKafka ACL grants idempotently.
options:

  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  instance_id:
    description:
      - CKafka instance ID.
    type: str
    required: true
  resource_type:
    description:
      - Kafka resource type.
    type: str
    required: true
    choices: [TOPIC, GROUP, CLUSTER, TRANSACTIONAL_ID]
  resource_name:
    description:
      - Kafka resource name.
    type: str
    required: true
  operation:
    description:
      - Kafka ACL operation.
    type: str
    required: true
  permission:
    description:
      - Permission type.
    type: str
    choices: [ALLOW, DENY]
    default: ALLOW
  host:
    description:
      - Client host pattern.
    type: str
    default: '*'
  principal:
    description:
      - Kafka principal.
    type: str
    required: true
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
  - module: susunola.tencentcloud.ckafka_acl_info
    description: Gather information about Tencent Cloud CKAFKA acls.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.ckafka_acl:
    instance_id: ckafka-xxxxxxxx
    resource_type: TOPIC
    resource_name: orders
    operation: READ
    principal: User:analytics

- name: Delete the acl
  susunola.tencentcloud.ckafka_acl:
    state: absent
    instance_id: ckafka-xxxxxxxx
    operation: READ
    principal: User:analytics
    resource_name: orders
    resource_type: TOPIC
"""
RETURN = r"""acl:
  description:
    - CKafka ACL metadata.
  returned: always
  type: dict"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.ckafka.v20190819 import ckafka_client, models

    return models, ckafka_client


def wanted(p):
    return {
        "ResourceType": _RESOURCE_TYPES[p["resource_type"]],
        "ResourceName": p["resource_name"],
        "Operation": _OPERATIONS[p["operation"]],
        "PermissionType": _PERMISSIONS[p["permission"]],
        "Host": p["host"],
        "Principal": p["principal"],
    }


# The CKafka ACL API encodes resource type, operation and permission as
# integers (see the CreateAclRequest field documentation); the module
# accepts human-readable strings and maps them here.
_RESOURCE_TYPES = {"TOPIC": 2, "GROUP": 3, "CLUSTER": 4, "TRANSACTIONAL_ID": 5}
_OPERATIONS = {
    "ALL": 2, "READ": 3, "WRITE": 4, "CREATE": 5, "DELETE": 6, "ALTER": 7,
    "DESCRIBE": 8, "CLUSTER_ACTION": 9, "DESCRIBE_CONFIGS": 10,
    "ALTER_CONFIGS": 11, "IDEMPOTENT_WRITE": 12,
}
_PERMISSIONS = {"DENY": 2, "ALLOW": 3}


def find(module, client, models, p):
    request = models.DescribeACLRequest()
    request.InstanceId = p["instance_id"]
    request.ResourceType = _RESOURCE_TYPES[p["resource_type"]]
    request.ResourceName, request.Offset, request.Limit = p["resource_name"], 0, 100
    result = module.sdk_call(client.DescribeACL, request).Result
    target = wanted(p)
    return next((x._serialize(allow_none=True) for x in (result.AclList or []) if all(getattr(x, k) == v for k, v in target.items())), None)


def request_for(models, p, deleting=False):
    request = models.DeleteAclRequest() if deleting else models.CreateAclRequest()
    request.InstanceId, request.ResourceType, request.ResourceName = p["instance_id"], _RESOURCE_TYPES[p["resource_type"]], p["resource_name"]
    request.Operation = _OPERATIONS[p["operation"]]
    request.PermissionType = _PERMISSIONS[p["permission"]]
    request.Host, request.Principal = p["host"], p["principal"]
    return request


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "instance_id": {"required": True},
            "resource_type": {"choices": ["TOPIC", "GROUP", "CLUSTER", "TRANSACTIONAL_ID"], "required": True},
            "resource_name": {"required": True},
            "operation": {"required": True},
            "permission": {"choices": ["ALLOW", "DENY"], "default": "ALLOW"},
            "host": {"default": "*"},
            "principal": {"required": True},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CkafkaClient, "ckafka.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, acl=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteAcl, request_for(models, p, True))
            module.exit_json(changed=True, **(diff or {}), acl=current if module.check_mode else None)
        if current:
            module.exit_json(changed=False, acl=current)
        target = wanted(p)
        diff = maybe_diff(module, None, target)
        if not module.check_mode:
            module.sdk_call(client.CreateAcl, request_for(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), acl=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
