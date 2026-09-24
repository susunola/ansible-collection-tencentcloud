#!/usr/bin/python
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: cos_bucket_referer_info
short_description: Gather Tencent Cloud COS hotlink protection
version_added: "1.4.0"
description: Returns the effective normalized referer protection configuration of a COS bucket.
options:
  name: {description: Bucket short name or full name., type: str, required: true}
  appid: {description: Tencent Cloud AppId used in the bucket suffix., type: str}
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cos_bucket_referer_info:
    region: ap-guangzhou
    name: public-assets
'''
RETURN = r'''
referers: {description: Referer configuration as an empty or single-element list., returned: always, type: list, elements: dict}
referer: {description: Effective referer configuration or null., returned: always, type: dict}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules.cos_bucket_referer import get_referer


def run_module():
    module = TencentCloudModule(argument_spec={"name": {"required": True}, "appid": {}}, supports_check_mode=True)
    cos.require_cos_sdk(module)
    bucket = cos.bucket_full_name(module.params["name"], cos.resolve_appid(module))
    try:
        referer = get_referer(cos.create_cos_client(module), bucket)
        module.exit_json(changed=False, referers=[referer] if referer else [], referer=referer)
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
