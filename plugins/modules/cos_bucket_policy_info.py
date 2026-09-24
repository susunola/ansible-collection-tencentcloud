#!/usr/bin/python
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: cos_bucket_policy_info
short_description: Gather Tencent Cloud COS bucket policy
version_added: "1.4.0"
description: Returns the effective normalized access policy of a COS bucket.
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
- susunola.tencentcloud.cos_bucket_policy_info:
    region: ap-guangzhou
    name: application-data
'''
RETURN = r'''
policies: {description: Bucket policy as an empty or single-element list., returned: always, type: list, elements: dict}
policy: {description: Effective normalized bucket policy or null., returned: always, type: dict}
'''

import json

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def normalize(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = json.loads(value)
    if isinstance(value, dict) and "Policy" in value:
        value = value["Policy"]
    if isinstance(value, str):
        value = json.loads(value)
    return value


def read_policy(client, bucket):
    try:
        return normalize(client.get_bucket_policy(Bucket=bucket))
    except Exception as exc:
        if cos.is_not_found(exc):
            return None
        raise


def run_module():
    module = TencentCloudModule(argument_spec={"name": {"required": True}, "appid": {}}, supports_check_mode=True)
    cos.require_cos_sdk(module)
    bucket = cos.bucket_full_name(module.params["name"], cos.resolve_appid(module))
    try:
        policy = read_policy(cos.create_cos_client(module), bucket)
        module.exit_json(changed=False, policies=[policy] if policy else [], policy=policy)
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
