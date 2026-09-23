#!/usr/bin/python
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: cos_bucket_origin_info
short_description: Gather Tencent Cloud COS bucket origin rules
version_added: "1.4.0"
description: Returns the effective normalized origin-rule set of a COS bucket.
options:
  name: {description: Bucket short name or full name., type: str, required: true}
  appid: {description: Tencent Cloud AppId used in the bucket suffix., type: str}
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cos_bucket_origin_info:
    region: ap-guangzhou
    name: media
'''
RETURN = r'''
origins: {description: Origin configuration as an empty or single-element list., returned: always, type: list, elements: dict}
origin: {description: Effective origin configuration or null., returned: always, type: dict}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules.cos_bucket_origin import get_origin


def run_module():
    module = TencentCloudModule(argument_spec={"name": {"required": True}, "appid": {}}, supports_check_mode=True)
    cos.require_cos_sdk(module)
    bucket = cos.bucket_full_name(module.params["name"], cos.resolve_appid(module))
    try:
        value = get_origin(cos.create_cos_client(module), bucket)
        module.exit_json(changed=False, origins=[value] if value else [], origin=value)
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
