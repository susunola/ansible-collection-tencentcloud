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
        ACL, versioning, CORS, lifecycle and tags to match the task.
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
  cors:
    description:
      - List of CORS rules to configure on the bucket, replacing the full
        rule set (rules not listed are removed).
      - Each rule requires C(allowed_origins) and C(allowed_methods);
        C(id), C(allowed_headers), C(expose_headers) and C(max_age_seconds)
        are optional.
      - When omitted, the CORS configuration is left unmanaged. Pass an
        empty list to remove every rule.
    type: list
    elements: dict
    suboptions:
      id:
        description: Optional rule identifier.
        type: str
      allowed_origins:
        description:
          - Origins allowed to make cross-origin requests, for example
            C(http://www.example.com) or C(https://*.example.com).
        type: list
        elements: str
        required: true
      allowed_methods:
        description: HTTP methods allowed, for example C(GET), C(PUT).
        type: list
        elements: str
        required: true
      allowed_headers:
        description: Headers allowed in preflight requests.
        type: list
        elements: str
      expose_headers:
        description: Headers exposed to the browser in the actual response.
        type: list
        elements: str
      max_age_seconds:
        description: How long in seconds the browser caches the preflight result.
        type: int
  lifecycle:
    description:
      - List of lifecycle rules to configure on the bucket, replacing the
        full rule set (rules not listed are removed).
      - Each rule is matched by C(prefix); a rule with an empty prefix
        applies to the whole bucket. At least one of C(expiration_days),
        C(transitions), C(noncurrent_version_transitions) or
        C(abort_incomplete_multipart_upload_days) must be set per rule.
      - When omitted, the lifecycle configuration is left unmanaged. Pass
        an empty list to remove every rule.
    type: list
    elements: dict
    suboptions:
      id:
        description: Optional rule identifier.
        type: str
      prefix:
        description:
          - Object key prefix the rule applies to, for example C(logs/).
          - When omitted the rule applies to the whole bucket.
        type: str
      status:
        description: Whether the rule is enabled.
        type: str
        choices: [enabled, disabled]
        default: enabled
      expiration_days:
        description:
          - Delete objects this many days after they are created.
          - Mutually exclusive with date-based expiration, which this module
            does not manage; a date-based rule on the bucket is reported as
            a change and rewritten as a day-based one.
        type: int
      abort_incomplete_multipart_upload_days:
        description: Abort incomplete multipart uploads this many days after initiation.
        type: int
      transitions:
        description:
          - Storage class transitions for current versions, each with
            C(days) and C(storage_class).
        type: list
        elements: dict
        suboptions:
          days:
            description: Days after creation before the transition applies.
            type: int
            required: true
          storage_class:
            description:
              - Destination storage class, for example C(STANDARD_IA),
                C(ARCHIVE) or C(DEEP_ARCHIVE).
            type: str
            required: true
      noncurrent_version_transitions:
        description:
          - Storage class transitions for noncurrent versions, each with
            C(noncurrent_days) and C(storage_class).
          - Requires versioning to be enabled on the bucket.
        type: list
        elements: dict
        suboptions:
          noncurrent_days:
            description: Days after a version becomes noncurrent before the transition applies.
            type: int
            required: true
          storage_class:
            description: Destination storage class, for example C(STANDARD_IA) or C(ARCHIVE).
            type: str
            required: true
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
- name: Create a COS bucket
  susunola.tencentcloud.cos_bucket:
    region: ap-guangzhou
    state: present
    name: mybucket
    appid: "1300000000"
    acl: private
    versioning: true
    tags:
      env: prod

- name: Check whether the bucket would be updated (no changes applied)
  susunola.tencentcloud.cos_bucket:
    region: ap-guangzhou
    state: present
    name: mybucket
    appid: "1300000000"
    acl: public-read
  check_mode: true

- name: Delete a COS bucket
  susunola.tencentcloud.cos_bucket:
    region: ap-guangzhou
    state: absent
    name: mybucket
    appid: "1300000000"

- name: Configure CORS and lifecycle rules on a bucket
  susunola.tencentcloud.cos_bucket:
    region: ap-guangzhou
    state: present
    name: mybucket
    appid: "1300000000"
    cors:
      - id: web
        allowed_origins:
          - https://www.example.com
        allowed_methods: [GET, HEAD]
        allowed_headers: [x-cos-meta-test]
        expose_headers: [ETag]
        max_age_seconds: 600
    lifecycle:
      - id: logs-expire
        prefix: logs/
        expiration_days: 30
        transitions:
          - days: 7
            storage_class: STANDARD_IA
        abort_incomplete_multipart_upload_days: 7
      - id: archive-old
        prefix: archive/
        noncurrent_version_transitions:
          - noncurrent_days: 15
            storage_class: ARCHIVE
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
    cors:
      - ID: web
        AllowedOrigin: [https://www.example.com]
        AllowedMethod: [GET, HEAD]
        MaxAgeSeconds: 600
    lifecycle:
      - ID: logs-expire
        Status: Enabled
        Filter:
          Prefix: logs/
        Expiration:
          Days: 30
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


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


def set_bucket_cors(client, full_name, rules):
    """Replace the bucket's CORS rules, or remove them when ``rules`` is empty.

    Deleting a CORS configuration that does not exist returns 404 and is
    treated as an idempotent success.
    """
    if rules:
        client.put_bucket_cors(
            Bucket=full_name,
            CORSConfiguration={"CORSRule": cos.cors_rules_desired(rules)},
        )
    else:
        try:
            client.delete_bucket_cors(Bucket=full_name)
        except Exception as exc:
            if not cos.is_not_found(exc):
                raise


def set_bucket_lifecycle(client, full_name, rules):
    """Replace the bucket's lifecycle rules, or remove them when empty."""
    if rules:
        client.put_bucket_lifecycle(
            Bucket=full_name,
            LifecycleConfiguration={"Rule": cos.lifecycle_rules_desired(rules)},
        )
    else:
        try:
            client.delete_bucket_lifecycle(Bucket=full_name)
        except Exception as exc:
            if not cos.is_not_found(exc):
                raise


def create_bucket(client, full_name, acl):
    client.create_bucket(Bucket=full_name, ACL=acl)


def desired_state(name, acl, versioning, tags, cors, lifecycle):
    desired = {"name": name, "acl": acl, "tags": normalize_tags(tags)}
    if versioning is not None:
        desired["versioning"] = versioning
    if cors is not None:
        desired["cors"] = cos.cors_rules_desired(cors)
    if lifecycle is not None:
        desired["lifecycle"] = cos.lifecycle_rules_desired(lifecycle)
    return desired


def bucket_changes(current, acl, versioning, tags, cors, lifecycle):
    """Return the list of attributes differing from the desired state."""
    changes = []
    if current.get("acl") != acl:
        changes.append("acl")
    if versioning is not None and current.get("versioning") != versioning:
        changes.append("versioning")
    if current.get("tags") != normalize_tags(tags):
        changes.append("tags")
    if cors is not None and current.get("cors") != cos.cors_rules_desired(cors):
        changes.append("cors")
    if lifecycle is not None and current.get("lifecycle") != cos.lifecycle_rules_desired(lifecycle):
        changes.append("lifecycle")
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
            "cors": {
                "type": "list",
                "elements": "dict",
                "suboptions": {
                    "id": {"type": "str"},
                    "allowed_origins": {"type": "list", "elements": "str", "required": True},
                    "allowed_methods": {"type": "list", "elements": "str", "required": True},
                    "allowed_headers": {"type": "list", "elements": "str"},
                    "expose_headers": {"type": "list", "elements": "str"},
                    "max_age_seconds": {"type": "int"},
                },
            },
            "lifecycle": {
                "type": "list",
                "elements": "dict",
                "suboptions": {
                    "id": {"type": "str"},
                    "prefix": {"type": "str"},
                    "status": {"type": "str", "choices": ["enabled", "disabled"], "default": "enabled"},
                    "expiration_days": {"type": "int"},
                    "abort_incomplete_multipart_upload_days": {"type": "int"},
                    "transitions": {
                        "type": "list",
                        "elements": "dict",
                        "suboptions": {
                            "days": {"type": "int", "required": True},
                            "storage_class": {"type": "str", "required": True},
                        },
                    },
                    "noncurrent_version_transitions": {
                        "type": "list",
                        "elements": "dict",
                        "suboptions": {
                            "noncurrent_days": {"type": "int", "required": True},
                            "storage_class": {"type": "str", "required": True},
                        },
                    },
                },
            },
            "tags": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )
    cos.require_cos_sdk(module)

    state = module.params["state"]
    name = module.params["name"]
    acl = module.params["acl"]
    versioning = module.params["versioning"]
    cors = module.params["cors"]
    lifecycle = module.params["lifecycle"]
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
        desired = desired_state(name, acl, versioning, tags, cors, lifecycle)
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would create bucket")
            create_bucket(client, full_name, acl)
            if versioning:
                set_bucket_versioning(client, full_name, True)
            if cors is not None:
                set_bucket_cors(client, full_name, cors)
            if lifecycle is not None:
                set_bucket_lifecycle(client, full_name, lifecycle)
            if tags:
                set_bucket_tags(client, full_name, normalize_tags(tags))
            bucket = cos.describe_bucket(client, full_name, short_name=name)
            module.exit_json(changed=True, **(diff or {}), bucket=bucket, msg="Bucket created")

        changes = bucket_changes(current, acl, versioning, tags, cors, lifecycle)
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
        if "cors" in changes:
            set_bucket_cors(client, full_name, cors)
        if "lifecycle" in changes:
            set_bucket_lifecycle(client, full_name, lifecycle)
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
