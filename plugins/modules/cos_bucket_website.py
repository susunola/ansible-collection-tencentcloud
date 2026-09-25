#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cos_bucket_website
short_description: Manage Tencent Cloud COS static website configuration
version_added: "0.14.0"
description: Reconciles the complete static website configuration of a COS bucket.
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
  configuration:
    description:
      - Complete COS SDK-compatible WebsiteConfiguration document.
    type: dict

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
  - module: susunola.tencentcloud.cos_bucket_website_info
    description: Gather Tencent Cloud COS static website configuration.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cos_bucket_website:
    name: public-site
    configuration:
      IndexDocument: {Suffix: index.html}
      ErrorDocument: {Key: error.html}

- name: Delete the website
  susunola.tencentcloud.cos_bucket_website:
    state: absent
    name: public-site
"""
RETURN = r"""website:
  description:
    - Effective website configuration.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    IndexDocument:
      Suffix: index.html
    ErrorDocument:
      Key: error.html
"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def normalize(value):
    if not value:
        return None
    return value.get("WebsiteConfiguration", value)


def get_website(client, bucket):
    try:
        return normalize(client.get_bucket_website(Bucket=bucket))
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
            "configuration": {"type": "dict"},
        },
        required_if=[("state", "present", ["configuration"])],
        supports_check_mode=True,
    )
    cos.require_cos_sdk(module)
    bucket = cos.bucket_full_name(module.params["name"], cos.resolve_appid(module))
    client = cos.create_cos_client(module)
    try:
        current = get_website(client, bucket)
        target = normalize(module.params.get("configuration"))
        if module.params["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, website=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                client.delete_bucket_website(Bucket=bucket)
            module.exit_json(changed=True, **(diff or {}), website=current if module.check_mode else None)
        if current == target:
            module.exit_json(changed=False, website=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            client.put_bucket_website(Bucket=bucket, WebsiteConfiguration=target)
        module.exit_json(changed=True, **(diff or {}), website=target)
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
