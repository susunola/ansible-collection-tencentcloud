#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: cos_bucket_website
short_description: Manage Tencent Cloud COS static website configuration
version_added: "0.14.0"
description: Reconciles the complete static website configuration of a COS bucket.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  name: {type: str, required: true, description: Bucket short name or full name.}
  appid: {type: str, description: Tencent Cloud AppId used in the bucket suffix.}
  configuration: {type: dict, description: Complete COS SDK-compatible WebsiteConfiguration document.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cos_bucket_website:
    name: public-site
    configuration:
      IndexDocument: {Suffix: index.html}
      ErrorDocument: {Key: error.html}
'''
RETURN = r'''website: {description: Effective website configuration., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def normalize(value):
    if not value: return None
    return value.get("WebsiteConfiguration", value)


def get_website(client, bucket):
    try: return normalize(client.get_bucket_website(Bucket=bucket))
    except Exception as exc:
        if cos.is_not_found(exc): return None
        raise


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "name": {"required": True}, "appid": {}, "configuration": {"type": "dict"}}, required_if=[("state", "present", ["configuration"])], supports_check_mode=True)
    cos.require_cos_sdk(module); bucket = cos.bucket_full_name(module.params["name"], cos.resolve_appid(module)); client = cos.create_cos_client(module)
    try:
        current = get_website(client, bucket); target = normalize(module.params.get("configuration"))
        if module.params["state"] == "absent":
            if current is None: module.exit_json(changed=False, website=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: client.delete_bucket_website(Bucket=bucket)
            module.exit_json(changed=True, **(diff or {}), website=current if module.check_mode else None)
        if current == target: module.exit_json(changed=False, website=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode: client.put_bucket_website(Bucket=bucket, WebsiteConfiguration=target)
        module.exit_json(changed=True, **(diff or {}), website=target)
    except Exception as exc: cos.fail_on_cos_error(module, exc)


def main(): run_module()
if __name__ == "__main__": main()
