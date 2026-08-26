#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cos_bucket_info
short_description: Gather information about Tencent Cloud COS buckets
version_added: "0.5.0"
description:
  - Describe a single COS bucket by name, or list all buckets owned by the
    account.
  - COS is not part of the Tencent Cloud API 3.0 family; this module uses the
    C(qcloud_cos) SDK (C(cos-python-sdk-v5) package) instead.
options:
  name:
    description:
      - Name of a bucket without the AppId suffix, for example C(mybucket).
      - When given, the module describes that single bucket (including ACL,
        versioning and tags) and fails when it does not exist.
      - When omitted, all buckets owned by the account in the region are
        listed; per-bucket ACL/versioning/tags are not fetched in list mode.
    type: str
  appid:
    description:
      - Tencent Cloud account AppId used as the bucket name suffix. Only used
        together with O(name).
      - When omitted, the AppId is resolved via the STS GetCallerIdentity
        API, which additionally requires the C(tencentcloud-sdk-python-sts)
        package.
    type: str
  retries:
    description:
      - Maximum number of retry attempts for throttled or transient API
        failures, using exponential backoff with jitter.
    type: int
    default: 5
  waiter_timeout:
    description:
      - Maximum time in seconds to wait for an asynchronous resource to reach
        the desired state.
    type: int
    default: 120
  waiter_delay:
    description: Interval in seconds between state polls while waiting.
    type: int
    default: 5
  user_agent:
    description:
      - User-Agent string sent with API requests.
    type: str
    default: ansible-collection/tencentcloud.cloud
notes:
  - Requires the C(cos-python-sdk-v5) package on the controller.
  - O(role_arn) is not supported for COS modules; pass credentials that
    already have COS permissions.
extends_documentation_fragment: tencentcloud.cloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Describe a single bucket
  tencentcloud.cloud.cos_bucket_info:
    region: ap-guangzhou
    name: mybucket
    appid: "1300000000"

- name: List all buckets in a region
  tencentcloud.cloud.cos_bucket_info:
    region: ap-guangzhou
'''

RETURN = r'''
buckets:
  description:
    - Matching buckets. Contains a single detailed entry when O(name) is
      given, otherwise one summary entry per bucket owned by the account.
  returned: always
  type: list
  elements: dict
  sample:
    - name: mybucket
      full_name: mybucket-1300000000
      location: ap-guangzhou
      acl: private
      versioning: false
      tags: {}
'''

from ansible_collections.tencentcloud.cloud.plugins.module_utils import cos
from ansible_collections.tencentcloud.cloud.plugins.module_utils.base import TencentCloudModule


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "name": {"type": "str"},
            "appid": {"type": "str"},
        },
        supports_check_mode=True,
    )
    cos.require_cos_sdk(module)

    name = module.params["name"]
    client = cos.create_cos_client(module)

    try:
        if name:
            appid = cos.resolve_appid(module)
            full_name = cos.bucket_full_name(name, appid)
            bucket = cos.describe_bucket(client, full_name, short_name=name)
            if bucket is None:
                module.fail_json(msg="Bucket {0} not found".format(full_name))
            module.exit_json(changed=False, buckets=[bucket])
        buckets = cos.list_buckets(client, region=module.params["region"])
        module.exit_json(changed=False, buckets=buckets)
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
