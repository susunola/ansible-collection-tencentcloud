#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: ssm_rotation_info
short_description: Gather Tencent Cloud Secrets Manager rotation state
version_added: "0.14.0"
description: Returns current rotation configuration and optionally the visible recent rotation history.
options:
  secret_name: {type: str, required: true, description: Secret name.}
  include_history: {type: bool, default: true, description: Include recent rotation version IDs and account metadata.}
  retries: {type: int, default: 5, description: Retries for transient API failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.ssm_rotation_info:
    secret_name: prod/database
"""
RETURN = r"""
rotation: {description: Rotation configuration and schedule., type: dict, returned: always}
history: {description: Recent rotation history., type: dict, returned: when include_history is true}
request_id: {description: Request ID from the final API call., type: str, returned: always}
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.ssm.v20190923 import models, ssm_client

    return models, ssm_client


def request(cls, name):
    value = cls()
    value.SecretName = name
    return value


def run_module():
    module = TencentCloudModule(
        argument_spec={"secret_name": {"required": True}, "include_history": {"type": "bool", "default": True}}, supports_check_mode=True
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.SsmClient, "ssm.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeRotationDetail, request(models.DescribeRotationDetailRequest, p["secret_name"]))
        rotation = response._serialize(allow_none=True)
        request_id = rotation.pop("RequestId", response.RequestId)
        result = {"changed": False, "rotation": rotation, "request_id": request_id}
        if p["include_history"]:
            response = module.sdk_call(client.DescribeRotationHistory, request(models.DescribeRotationHistoryRequest, p["secret_name"]))
            history = response._serialize(allow_none=True)
            result["request_id"] = history.pop("RequestId", response.RequestId)
            result["history"] = history
        module.exit_json(**result)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
