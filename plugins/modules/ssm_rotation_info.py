#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: ssm_rotation_info
short_description: Gather Tencent Cloud Secrets Manager rotation state
version_added: "0.14.0"
description: Returns current rotation configuration and optionally the visible recent rotation history.
options:
  secret_name:
    description:
      - Secret whose rotation configuration is returned.
    type: str
    required: true
  include_history:
    description:
      - Include recent rotation version IDs and account metadata.
    type: bool
    default: true

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
  idempotent:
    description:
      - Read-only, so every run returns the current state and never changes
        the target, and a repeated run reports C(changed=false).
    support: full
seealso:
  - module: susunola.tencentcloud.ssm_rotation
    description: Manage Tencent Cloud SSM secret rotation settings.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.ssm_rotation_info:
    secret_name: prod/database
"""
RETURN = r"""
rotation:
  description:
    - Rotation configuration and schedule.
  returned: always
  type: dict
history:
  description:
    - Recent rotation history.
  returned: when include_history is true
  type: dict
request_id:
  description:
    - Request ID from the final API call.
  returned: always
  type: str
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


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
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
