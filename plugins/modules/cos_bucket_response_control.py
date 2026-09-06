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
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  name: {type: str, required: true, description: Bucket short name or full name.}
  appid: {type: str, description: Tencent Cloud AppId used in the bucket suffix.}
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
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cos_bucket_response_control:
    region: ap-guangzhou
    name: downloads
    parameters: [response-content-type, response-content-disposition]
"""
RETURN = r"""response_control: {description: Effective response-control configuration., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
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


def normalize(value):
    if not value:
        return None
    root = value.get("ResponseControlConfiguration", value)
    params = (root.get("ControlParamList") or {}).get("Param") or []
    if isinstance(params, str):
        params = [params]
    return {"ControlParamList": {"Param": sorted(params)}}


def get_control(client, bucket):
    try:
        return normalize(client.get_bucket_response_control(Bucket=bucket))
    except Exception as exc:
        if cos.is_not_found(exc):
            return None
        raise


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
