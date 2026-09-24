#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cos_bucket_domain
short_description: Manage Tencent Cloud COS custom domains
version_added: "0.14.0"
description: Reconciles the complete custom-domain rule set of a COS bucket.
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
  rules:
    description:
      - Complete COS SDK-compatible DomainRule list.
    type: list
    elements: dict

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
  idempotency:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cos_bucket_domain:
    name: public-site
    rules:
      - {Name: static.example.com, Type: REST, Status: ENABLED, ForcedReplacement: CNAME}
"""
RETURN = r"""
domains: {description: Effective custom-domain configuration., type: dict, returned: always}
txt_verification: {description: DNS TXT verification value returned by COS., type: str, returned: when available}
"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.cos_bucket_read import normalize_domains as normalize, get_domains
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "name": {"required": True},
            "appid": {},
            "rules": {"type": "list", "elements": "dict"},
        },
        required_if=[("state", "present", ["rules"])],
        supports_check_mode=True,
    )
    cos.require_cos_sdk(module)
    bucket = cos.bucket_full_name(module.params["name"], cos.resolve_appid(module))
    client = cos.create_cos_client(module)
    try:
        current, verification = get_domains(client, bucket)
        target = normalize({"DomainRule": module.params.get("rules") or []})
        if module.params["state"] == "absent":
            target = None
        if current == target:
            module.exit_json(changed=False, domains=current, txt_verification=verification)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            if target is None:
                client.delete_bucket_domain(Bucket=bucket)
            else:
                client.put_bucket_domain(Bucket=bucket, DomainConfiguration=target)
        module.exit_json(changed=True, **(diff or {}), domains=current if module.check_mode else target, txt_verification=verification)
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
