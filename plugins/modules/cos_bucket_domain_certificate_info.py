#!/usr/bin/python
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: cos_bucket_domain_certificate_info
short_description: Gather a Tencent Cloud COS custom-domain certificate
version_added: "1.4.0"
description: Returns the effective certificate status and managed certificate ID for one COS custom domain.
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
  domain_name:
    description:
      - Custom domain bound to the bucket.
    type: str
    required: true
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cos_bucket_domain_certificate_info:
    region: ap-guangzhou
    name: public-site
    domain_name: static.example.com
'''
RETURN = r'''
domain_certificates: {description: Certificate configuration as an empty or single-element list., returned: always, type: list, elements: dict}
domain_certificate: {description: Effective certificate configuration or null., returned: always, type: dict}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.cos import (
    get_bucket_domain_certificate,
)

def run_module():
    module = TencentCloudModule(argument_spec={"name": {"required": True}, "appid": {}, "domain_name": {"required": True}}, supports_check_mode=True)
    cos.require_cos_sdk(module)
    bucket = cos.bucket_full_name(module.params["name"], cos.resolve_appid(module))
    try:
        value = get_bucket_domain_certificate(cos.create_cos_client(module), bucket, module.params["domain_name"])
        module.exit_json(changed=False, domain_certificates=[value] if value else [], domain_certificate=value)
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
