#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cos_bucket_response_control
short_description: Manage Tencent Cloud COS response-header controls
version_added: "0.14.0"
description: Reconciles the response query parameters allowed for a COS bucket.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  name:
    description:
      - Bucket short name or full name.
    type: str
    required: true
  appid:
    description:
      - Tencent Cloud AppId used in the bucket suffix.
    type: str
  parameters:
    type: list
    elements: str
    description: Response query parameters clients may override.
    choices:
      - response-content-type
      - response-content-disposition
      - response-cache-control
      - response-content-encoding
      - response-content-language
      - response-expires

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
  - module: susunola.tencentcloud.cos_bucket_response_control_info
    description: Gather Tencent Cloud COS response-header controls.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cos_bucket_response_control:
    region: ap-guangzhou
    name: downloads
    parameters: [response-content-type, response-content-disposition]
"""
RETURN = r"""response_control:
  description:
    - Effective response-control configuration.
  returned: always
  type: dict"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.cos_bucket_read import normalize_control as normalize, get_control
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff

PARAMETERS = [
    "response-content-type",
    "response-content-disposition",
    "response-cache-control",
    "response-content-encoding",
    "response-content-language",
    "response-expires",
]


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "name": {"required": True},
            "appid": {},
            "parameters": {"type": "list", "elements": "str", "choices": PARAMETERS},
        },
        required_if=[("state", "present", ["parameters"])],
        supports_check_mode=True,
    )
    p = module.params
    cos.require_cos_sdk(module)
    bucket = cos.bucket_full_name(p["name"], cos.resolve_appid(module))
    client = cos.create_cos_client(module)
    try:
        current = get_control(client, bucket)
        target = normalize({"ControlParamList": {"Param": p.get("parameters") or []}}) if p["state"] == "present" else None
        if current == target:
            module.exit_json(changed=False, response_control=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            if target is None:
                client.delete_bucket_response_control(Bucket=bucket)
            else:
                client.put_bucket_response_control(Bucket=bucket, ResponseControlConfiguration=target)
        module.exit_json(changed=True, **(diff or {}), response_control=target)
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
