#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: ckafka_acl_info
short_description: Gather Tencent Cloud CKafka ACL entries
version_added: "1.4.0"
description:
  - Returns observable ACL entries for one CKafka resource.
  - Optional filters use the same human-readable values as C(ckafka_acl).
options:
  instance_id: {description: CKafka instance ID., type: str, required: true}
  resource_type: {description: Kafka resource type., type: str, choices: [TOPIC, GROUP, CLUSTER, TRANSACTIONAL_ID], required: true}
  resource_name: {description: Kafka resource name., type: str, required: true}
  operation: {description: Kafka ACL operation., type: str, choices: [ALL, READ, WRITE, CREATE, DELETE, ALTER, DESCRIBE, CLUSTER_ACTION, DESCRIBE_CONFIGS, ALTER_CONFIGS, IDEMPOTENT_WRITE]}
  permission: {description: Permission type., type: str, choices: [ALLOW, DENY]}
  host: {description: Client host pattern., type: str}
  principal: {description: Kafka principal., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Read grants for an orders topic
  susunola.tencentcloud.ckafka_acl_info:
    region: ap-guangzhou
    instance_id: ckafka-xxxxxxxx
    resource_type: TOPIC
    resource_name: orders
'''

RETURN = r'''
acls: {description: Matching ACL entries., returned: always, type: list, elements: dict}
acl: {description: The single matching ACL when exactly one entry matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile, create_credential, sdk_call, serialize_sdk_object, tencentcloud_argument_spec,
)

RESOURCE_TYPES = {"TOPIC": 2, "GROUP": 3, "CLUSTER": 4, "TRANSACTIONAL_ID": 5}
OPERATIONS = {
    "ALL": 2, "READ": 3, "WRITE": 4, "CREATE": 5, "DELETE": 6, "ALTER": 7,
    "DESCRIBE": 8, "CLUSTER_ACTION": 9, "DESCRIBE_CONFIGS": 10,
    "ALTER_CONFIGS": 11, "IDEMPOTENT_WRITE": 12,
}
PERMISSIONS = {"DENY": 2, "ALLOW": 3}


def build_request(models, instance_id, resource_type, resource_name, offset=0, limit=100):
    request = models.DescribeACLRequest()
    request.InstanceId, request.ResourceType = instance_id, RESOURCE_TYPES[resource_type]
    request.ResourceName, request.Offset, request.Limit = resource_name, offset, limit
    return request


def matches(value, operation=None, permission=None, host=None, principal=None):
    return all((
        operation is None or value.get("Operation") == OPERATIONS[operation],
        permission is None or value.get("PermissionType") == PERMISSIONS[permission],
        host is None or value.get("Host") == host,
        principal is None or value.get("Principal") == principal,
    ))


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "instance_id": {"type": "str", "required": True},
        "resource_type": {"type": "str", "choices": list(RESOURCE_TYPES), "required": True},
        "resource_name": {"type": "str", "required": True},
        "operation": {"type": "str", "choices": list(OPERATIONS)},
        "permission": {"type": "str", "choices": list(PERMISSIONS)},
        "host": {"type": "str"},
        "principal": {"type": "str"},
    })
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    try:
        from tencentcloud.ckafka.v20190819 import ckafka_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-ckafka package is required.")
    p = module.params
    client = ckafka_client.CkafkaClient(create_credential(module), p["region"], create_client_profile(module, "ckafka.tencentcloudapi.com"))
    offset, acls, request_id = 0, [], None
    while True:
        response = sdk_call(module, client.DescribeACL, build_request(models, p["instance_id"], p["resource_type"], p["resource_name"], offset))
        request_id = getattr(response, "RequestId", None)
        result = getattr(response, "Result", None)
        page = list(getattr(result, "AclList", None) or [])
        acls.extend(serialize_sdk_object(item) for item in page)
        total = int(getattr(result, "TotalCount", 0) or 0)
        offset += len(page)
        if not page or offset >= total:
            break
    acls = [item for item in acls if matches(item, p.get("operation"), p.get("permission"), p.get("host"), p.get("principal"))]
    module.exit_json(changed=False, acls=acls, acl=acls[0] if len(acls) == 1 else None, request_id=request_id)


def main():
    run_module()


if __name__ == "__main__":
    main()
