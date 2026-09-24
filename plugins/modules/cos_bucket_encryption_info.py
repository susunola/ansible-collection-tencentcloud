#!/usr/bin/python
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: cos_bucket_encryption_info
short_description: Gather Tencent Cloud COS bucket default encryption
version_added: "1.4.0"
description: Returns the effective server-side encryption configuration of a COS bucket.
options:
  name: {description: Bucket short name or full name., type: str, required: true}
  appid: {description: Tencent Cloud AppId used in the bucket suffix., type: str}
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
- susunola.tencentcloud.cos_bucket_encryption_info:
    region: ap-guangzhou
    name: application-data
'''
RETURN = r'''
encryptions: {description: Encryption configuration as an empty or single-element list., returned: always, type: list, elements: dict}
encryption: {description: Effective encryption configuration or null., returned: always, type: dict}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def normalize(value):
    if not value:
        return None
    root = value.get("ServerSideEncryptionConfiguration", value)
    return {"Rule": root.get("Rule") or []}


def read_encryption(client, bucket):
    try:
        return normalize(client.get_bucket_encryption(Bucket=bucket))
    except Exception as exc:
        if cos.is_not_found(exc):
            return None
        raise


def run_module():
    module = TencentCloudModule(argument_spec={"name": {"required": True}, "appid": {}}, supports_check_mode=True)
    cos.require_cos_sdk(module)
    bucket = cos.bucket_full_name(module.params["name"], cos.resolve_appid(module))
    try:
        encryption = read_encryption(cos.create_cos_client(module), bucket)
        module.exit_json(changed=False, encryptions=[encryption] if encryption else [], encryption=encryption)
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
