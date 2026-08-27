#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cos_bucket
short_description: Manage Tencent Cloud COS buckets
version_added: "0.5.0"
description:
  - Create, update, and delete Tencent Cloud Object Storage (COS) buckets.
  - COS is not part of the Tencent Cloud API 3.0 family; this module uses the
    C(qcloud_cos) SDK (C(cos-python-sdk-v5) package) instead.
  - This module is idempotent. Running it twice leaves the bucket unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the bucket if it does not exist and updates its
        ACL, versioning and tags to match the task.
      - C(absent) deletes the bucket if it exists. Deleting a bucket that is
        not empty fails with a C(BucketNotEmpty) error; empty it first.
    type: str
    choices: [present, absent]
    default: present
  name:
    description:
      - Name of the bucket without the AppId suffix, for example C(mybucket).
      - The module appends the account AppId to form the full bucket name
        C(<name>-<appid>) that the COS API expects; a name already ending in
        C(-<appid>) is used unchanged.
    type: str
    required: true
  appid:
    description:
      - Tencent Cloud account AppId used as the bucket name suffix.
      - When omitted, the AppId is resolved via the STS GetCallerIdentity
        API, which additionally requires the C(tencentcloud-sdk-python-sts)
        package.
    type: str
  acl:
    description:
      - Canned ACL applied to the bucket. Applied at creation and reconciled
        on updates.
    type: str
    choices: [private, public-read, public-read-write]
    default: private
  versioning:
    description:
      - Whether object versioning is enabled on the bucket.
      - When omitted, the versioning configuration is left unmanaged.
    type: bool
  tags:
    description:
      - Tags to apply to the bucket as a dict, for example I(env=prod).
      - Uses native COS bucket tagging (C(put_bucket_tagging)), not the
        Tencent Cloud tag service.
      - Existing tags not listed are removed; listed tags with a different
        value are updated.
    type: dict
    default: {}
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
  - O(role_arn) is honoured; the temporary credentials obtained via STS
    C(AssumeRole) additionally require the C(tencentcloud-sdk-python-sts)
    package.
extends_documentation_fragment: tencentcloud.cloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a COS bucket
  tencentcloud.cloud.cos_bucket:
    region: ap-guangzhou
    state: present
    name: mybucket
    appid: "1300000000"
    acl: private
    versioning: true
    tags:
      env: prod

- name: Check whether the bucket would be updated (no changes applied)
  tencentcloud.cloud.cos_bucket:
    region: ap-guangzhou
    state: present
    name: mybucket
    appid: "1300000000"
    acl: public-read
  check_mode: true

- name: Delete a COS bucket
  tencentcloud.cloud.cos_bucket:
    region: ap-guangzhou
    state: absent
    name: mybucket
    appid: "1300000000"
'''

RETURN = r'''
bucket:
  description: The bucket as reported by COS after the operation.
  returned: success
  type: dict
  sample:
    name: mybucket
    full_name: mybucket-1300000000
    location: ap-guangzhou
    acl: private
    versioning: true
    tags:
      env: prod
'''

from ansible_collections.tencentcloud.cloud.plugins.module_utils import cos
from ansible_collections.tencentcloud.cloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.tencentcloud.cloud.plugins.module_utils.comparison import maybe_diff


def normalize_tags(tags):
    """Return tags as a str-to-str dict; COS tag values are strings."""
    return {str(key): str(value) for key, value in (tags or {}).items()}


def set_bucket_acl(client, full_name, acl):
    """Apply a canned ACL via request headers."""
    client.put_bucket_acl(Bucket=full_name, ACL=acl)


def set_bucket_versioning(client, full_name, enabled):
    client.put_bucket_versioning(Bucket=full_name, Status="Enabled" if enabled else "Suspended")


def set_bucket_tags(client, full_name, tags):
    """Replace the bucket's tag set, or clear it when ``tags`` is empty."""
    if tags:
        tagging = {
            "TagSet": {
                "Tag": [
                    {"Key": key, "Value": value}
                    for key, value in sorted(tags.items())
                ]
            }
        }
        client.put_bucket_tagging(Bucket=full_name, Tagging=tagging)
    else:
        client.delete_bucket_tagging(Bucket=full_name)


def create_bucket(client, full_name, acl):
    client.create_bucket(Bucket=full_name, ACL=acl)


def desired_state(name, acl, versioning, tags):
    desired = {"name": name, "acl": acl, "tags": normalize_tags(tags)}
    if versioning is not None:
        desired["versioning"] = versioning
    return desired


def bucket_changes(current, acl, versioning, tags):
    """Return the list of attributes differing from the desired state."""
    changes = []
    if current.get("acl") != acl:
        changes.append("acl")
    if versioning is not None and current.get("versioning") != versioning:
        changes.append("versioning")
    if current.get("tags") != normalize_tags(tags):
        changes.append("tags")
    return changes


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "name": {"type": "str", "required": True},
            "appid": {"type": "str"},
            "acl": {
                "type": "str",
                "choices": ["private", "public-read", "public-read-write"],
                "default": "private",
            },
            "versioning": {"type": "bool"},
            "tags": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )
    cos.require_cos_sdk(module)

    state = module.params["state"]
    name = module.params["name"]
    acl = module.params["acl"]
    versioning = module.params["versioning"]
    tags = module.params["tags"]

    appid = cos.resolve_appid(module)
    full_name = cos.bucket_full_name(name, appid)
    client = cos.create_cos_client(module)

    try:
        current = cos.describe_bucket(client, full_name, short_name=name)

        if state == "absent":
            if current is None:
                module.exit_json(changed=False, msg="Bucket already absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would delete bucket")
            try:
                client.delete_bucket(Bucket=full_name)
            except Exception as exc:
                if cos.is_idempotent_success(exc):
                    module.exit_json(changed=True, **(diff or {}), msg="Bucket deleted")
                raise
            module.exit_json(changed=True, **(diff or {}), bucket=None, msg="Bucket deleted")

        # state == present
        desired = desired_state(name, acl, versioning, tags)
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would create bucket")
            create_bucket(client, full_name, acl)
            if versioning:
                set_bucket_versioning(client, full_name, True)
            if tags:
                set_bucket_tags(client, full_name, normalize_tags(tags))
            bucket = cos.describe_bucket(client, full_name, short_name=name)
            module.exit_json(changed=True, **(diff or {}), bucket=bucket, msg="Bucket created")

        changes = bucket_changes(current, acl, versioning, tags)
        if not changes:
            module.exit_json(changed=False, bucket=current, msg="Bucket is up to date")

        if module.check_mode:
            module.exit_json(
                changed=True, **(maybe_diff(module, current, desired) or {}),
                msg="Would update bucket",
            )

        if "acl" in changes:
            set_bucket_acl(client, full_name, acl)
        if "versioning" in changes:
            set_bucket_versioning(client, full_name, versioning)
        if "tags" in changes:
            set_bucket_tags(client, full_name, normalize_tags(tags))

        updated = cos.describe_bucket(client, full_name, short_name=name)
        module.exit_json(
            changed=True,
            **(maybe_diff(module, current, desired) or {}),
            bucket=updated,
            msg="Bucket updated",
        )
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
