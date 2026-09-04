#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cos_object_info
short_description: Gather information about Tencent Cloud COS objects
version_added: "0.14.0"
description:
  - List objects in a Tencent Cloud Object Storage (COS) bucket, optionally
    filtered by key prefix.
  - COS is not part of the Tencent Cloud API 3.0 family; this module uses the
    C(qcloud_cos) SDK (C(cos-python-sdk-v5) package) instead.
  - This is a read-only module; it always reports C(changed=false).
options:
  bucket:
    description:
      - Bucket name, with or without the C(-<appid>) suffix, for example
        C(mybucket) or C(mybucket-1300000000).
      - The module appends the account AppId to a short name to form the full
        bucket name C(<name>-<appid>) that the COS API expects.
    type: str
    required: true
  appid:
    description:
      - Tencent Cloud account AppId used as the bucket name suffix.
      - When omitted, the AppId is resolved via the STS GetCallerIdentity
        API, which additionally requires the C(tencentcloud-sdk-python-sts)
        package.
    type: str
  prefix:
    description:
      - Object key prefix to filter on, for example C(images/).
      - When omitted, all objects in the bucket are listed.
    type: str
  marker:
    description:
      - Object key to start listing from, resuming a truncated listing.
      - When omitted, the listing starts at the beginning of the bucket.
    type: str
  max_keys:
    description:
      - Maximum number of keys returned in a single listing call.
      - COS caps this at 1000; set a smaller value together with O(marker) to
        page through a large bucket manually.
    type: int
    default: 1000
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
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(cos-python-sdk-v5) package on the controller.
  - O(role_arn) is honoured; the temporary credentials obtained via STS
    C(AssumeRole) additionally require the C(tencentcloud-sdk-python-sts)
    package.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: List every object in a bucket
  susunola.tencentcloud.cos_object_info:
    region: ap-guangzhou
    bucket: mybucket
    appid: "1300000000"

- name: List objects under a prefix
  susunola.tencentcloud.cos_object_info:
    region: ap-guangzhou
    bucket: mybucket
    appid: "1300000000"
    prefix: images/

- name: Page through a large bucket
  susunola.tencentcloud.cos_object_info:
    region: ap-guangzhou
    bucket: mybucket
    appid: "1300000000"
    max_keys: 500
    marker: "{{ page_result.next_marker | default(omit) }}"
'''

RETURN = r'''
objects:
  description:
    - One entry per object on the current listing page, sorted by key.
  returned: always
  type: list
  elements: dict
  sample:
    - key: images/logo.png
      etag: 9f86d081884c7d659a2feaa0c55ad015
      size: 11
      last_modified: "2026-08-31T12:00:00.000Z"
      storage_class: STANDARD
is_truncated:
  description: Whether more keys remain after this page (COS max 1000 keys).
  returned: always
  type: bool
next_marker:
  description: The O(marker) to pass for the next page, when truncated.
  returned: when the listing is truncated
  type: str
key_count:
  description: Number of objects on the returned page.
  returned: always
  type: int
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "bucket": {"type": "str", "required": True},
            "appid": {"type": "str"},
            "prefix": {"type": "str"},
            "marker": {"type": "str"},
            "max_keys": {"type": "int", "default": 1000, "no_log": False},
        },
        supports_check_mode=True,
    )
    cos.require_cos_sdk(module)

    bucket_short = module.params["bucket"]
    prefix = module.params["prefix"]
    marker = module.params["marker"]
    max_keys = module.params["max_keys"]

    appid = cos.resolve_appid(module)
    bucket = cos.bucket_full_name(bucket_short, appid)
    client = cos.create_cos_client(module)

    try:
        page = cos.list_objects(client, bucket, prefix=prefix, marker=marker, max_keys=max_keys)
        module.exit_json(changed=False, **page)
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
