#!/usr/bin/python
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: cos_bucket_domain_info
short_description: Gather Tencent Cloud COS custom domains
version_added: "1.4.0"
description: Returns the effective normalized custom-domain rule set and DNS TXT verification value of a COS bucket.
options:
  name:
    description:
      - Bucket short name or full name.
    type: str
    required: true
  appid:
    description:
      - Tencent Cloud AppId used in the bucket suffix.
    type: str
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
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cos_bucket_domain_info:
    region: ap-guangzhou
    name: public-site
'''
RETURN = r'''
domain_configurations: {description: Domain configuration as an empty or single-element list., returned: always, type: list, elements: dict}
domains: {description: Effective custom-domain configuration or null., returned: always, type: dict}
txt_verification: {description: DNS TXT verification value returned by COS., returned: always, type: str}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.cos_bucket_read import get_domains


def run_module():
    module = TencentCloudModule(argument_spec={"name": {"required": True}, "appid": {}}, supports_check_mode=True)
    cos.require_cos_sdk(module)
    bucket = cos.bucket_full_name(module.params["name"], cos.resolve_appid(module))
    try:
        value, verification = get_domains(cos.create_cos_client(module), bucket)
        module.exit_json(changed=False, domain_configurations=[value] if value else [], domains=value, txt_verification=verification)
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
