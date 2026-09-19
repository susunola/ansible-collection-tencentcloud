#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cloudaudit_audit_info
short_description: Gather Tencent Cloud account-level CloudAudit delivery configuration
version_added: "1.4.0"
description: Returns the complete observable account-level CloudAudit configuration by audit name.
options:
  audit_name: {description: Account-level audit name., type: str, required: true}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Read account-level CloudAudit delivery
  susunola.tencentcloud.cloudaudit_audit_info:
    region: ap-guangzhou
    audit_name: default
'''

RETURN = r'''
audits: {description: Matching account-level audit configurations., returned: always, type: list, elements: dict}
audit: {description: Account-level audit configuration., returned: always, type: dict}
request_id: {description: Request ID returned by the API., returned: always, type: str}
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile, create_credential, sdk_call, serialize_sdk_object, tencentcloud_argument_spec,
)


def build_request(models, audit_name):
    request = models.DescribeAuditRequest()
    request.AuditName = audit_name
    return request


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({"audit_name": {"type": "str", "required": True}})
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    try:
        from tencentcloud.cloudaudit.v20190319 import cloudaudit_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-cloudaudit package is required.")
    p = module.params
    client = cloudaudit_client.CloudauditClient(create_credential(module), p["region"], create_client_profile(module, "cloudaudit.tencentcloudapi.com"))
    try:
        response = sdk_call(module, client.DescribeAudit, build_request(models, p["audit_name"]))
    except Exception as exc:
        if is_not_found(exc):
            module.exit_json(changed=False, audits=[], audit=None, request_id=getattr(exc, "request_id", None))
        raise
    audit = serialize_sdk_object(response)
    request_id = audit.pop("RequestId", getattr(response, "RequestId", None))
    module.exit_json(changed=False, audits=[audit], audit=audit, request_id=request_id)


def main():
    run_module()


if __name__ == "__main__":
    main()
