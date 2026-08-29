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
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: CKafka instance ID.}
  resource_type: {type: str, choices: [TOPIC, GROUP, CLUSTER, TRANSACTIONAL_ID], required: true, description: Kafka resource type.}
  resource_name: {type: str, required: true, description: Kafka resource name.}
  operation: {type: str, required: true, description: Kafka ACL operation.}
  permission: {type: str, choices: [ALLOW, DENY], default: ALLOW, description: Permission type.}
  host: {type: str, default: '*', description: Client host pattern.}
  principal: {type: str, required: true, description: Kafka principal.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.ckafka_acl:
    instance_id: ckafka-xxxxxxxx
    resource_type: TOPIC
    resource_name: orders
    operation: READ
    principal: User:analytics
"""
RETURN = r"""acl: {description: CKafka ACL metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.ckafka.v20190819 import ckafka_client, models

    return models, ckafka_client


def wanted(p):
    return {
        "ResourceType": p["resource_type"],
        "ResourceName": p["resource_name"],
        "Operation": p["operation"],
        "PermissionType": p["permission"],
        "Host": p["host"],
        "Principal": p["principal"],
    }


def find(module, client, models, p):
    request = models.DescribeACLRequest()
    request.InstanceId, request.ResourceType, request.ResourceName = p["instance_id"], p["resource_type"], p["resource_name"]
    request.Offset, request.Limit = 0, 100
    result = module.sdk_call(client.DescribeACL, request).Result
    target = wanted(p)
    return next((x._serialize(allow_none=True) for x in (result.AclList or []) if all(getattr(x, k) == v for k, v in target.items())), None)


def request_for(models, p, deleting=False):
    request = models.DeleteAclRequest() if deleting else models.CreateAclRequest()
    request.InstanceId, request.ResourceType, request.ResourceName = p["instance_id"], p["resource_type"], p["resource_name"]
    request.Operation, request.PermissionType, request.Host, request.Principal = p["operation"], p["permission"], p["host"], p["principal"]
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
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
