#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cos_object_sync
short_description: Mirror a local directory tree into a Tencent Cloud COS bucket
version_added: "0.14.0"
description:
  - Synchronise a local directory tree into a Tencent Cloud Object Storage
    (COS) bucket prefix, uploading files that are new or changed and
    optionally deleting remote objects that no longer exist locally.
  - COS is not part of the Tencent Cloud API 3.0 family; this module uses the
    C(qcloud_cos) SDK (C(cos-python-sdk-v5) package) instead.
  - This module is idempotent. A second run with an unchanged tree reports
    C(changed=false).
  - Upload change detection compares each local file's MD5 digest against the
    remote object's ETag, which is exact for single-part uploads.
  - Supports check mode; no API write happens in check mode, only reads.
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
  src:
    description:
      - Local directory tree to mirror into the bucket.
    type: path
    required: true
  prefix:
    description:
      - Bucket key prefix the local tree is mirrored under, for example
        C(assets/). The bucket prefix, not the module's C(prefix) option.
      - When omitted, the tree is mirrored at the bucket root.
    type: str
  delete:
    description:
      - Delete remote objects under O(prefix) that have no corresponding
        local file.
      - When false (default), extra remote objects are left in place and the
        module reports them as C(skipped_remote).
    type: bool
    default: false
  force:
    description:
      - Re-upload every local file even when its MD5 matches the remote ETag.
    type: bool
    default: false
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
  - Files are uploaded with single-part C(put_object) calls so the ETag
    comparison stays exact; very large files are better handled by a
    dedicated streaming module.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Mirror a local tree into a bucket prefix
  susunola.tencentcloud.cos_object_sync:
    region: ap-guangzhou
    bucket: mybucket
    appid: "1300000000"
    src: /var/www/assets
    prefix: assets/

- name: Mirror and delete remote objects that no longer exist locally
  susunola.tencentcloud.cos_object_sync:
    region: ap-guangzhou
    bucket: mybucket
    appid: "1300000000"
    src: /var/www/assets
    prefix: assets/
    delete: true
'''

RETURN = r'''
changed:
  description: Whether any object was uploaded or deleted.
  returned: always
  type: bool
summary:
  description:
    - Counts of uploads and deletions performed, and objects skipped because
      they were unchanged or left in place when O(delete=false).
  returned: always
  type: dict
  sample:
    uploaded: 3
    deleted: 0
    unchanged: 12
    skipped_remote: 2
uploaded:
  description: Object keys uploaded by this run.
  returned: always
  type: list
  elements: str
deleted:
  description: Object keys deleted by this run.
  returned: always
  type: list
  elements: str
'''

import os

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def relkey(root, path):
    """Return the object key for a local file under ``root`` (POSIX separators)."""
    return os.path.relpath(path, root).replace(os.sep, "/")


def walk_local(src):
    """Return {relative_key: md5_hex} for every regular file under ``src``."""
    files = {}
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if not os.path.isfile(full):
                continue
            key = relkey(src, full)
            files[key] = cos_object_md5(full)
    return files


def cos_object_md5(path):
    import hashlib
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "bucket": {"type": "str", "required": True},
            "appid": {"type": "str"},
            "src": {"type": "path", "required": True},
            "prefix": {"type": "str"},
            "delete": {"type": "bool", "default": False},
            "force": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    cos.require_cos_sdk(module)

    bucket_short = module.params["bucket"]
    src = module.params["src"]
    prefix = module.params["prefix"] or ""
    delete = module.params["delete"]
    force = module.params["force"]

    if not os.path.isdir(src):
        module.fail_json(msg="src {0} is not a directory".format(src))

    appid = cos.resolve_appid(module)
    bucket = cos.bucket_full_name(bucket_short, appid)
    client = cos.create_cos_client(module)

    try:
        local = walk_local(src)
        remote = {}
        for item in cos.iter_objects(client, bucket, prefix=prefix):
            remote[item["key"]] = item["etag"]

        def key_for(rel):
            return prefix + rel if prefix else rel

        to_upload = []
        unchanged = 0
        for rel, digest in sorted(local.items()):
            key = key_for(rel)
            if force or remote.get(key) != digest:
                to_upload.append((key, rel))
            else:
                unchanged += 1

        skipped_remote = []
        remote_prefix = set()
        for key in remote:
            if key.startswith(prefix):
                remote_prefix.add(key)
        to_delete = []
        for key in sorted(remote_prefix):
            rel = key[len(prefix):] if prefix else key
            if rel not in local:
                if delete:
                    to_delete.append(key)
                else:
                    skipped_remote.append(key)

        changed = bool(to_upload or to_delete)
        summary = {
            "uploaded": len(to_upload),
            "deleted": len(to_delete),
            "unchanged": unchanged,
            "skipped_remote": len(skipped_remote),
        }
        if module.check_mode:
            module.exit_json(
                changed=changed,
                summary=summary,
                uploaded=[k for k, _rel in to_upload],
                deleted=to_delete,
                msg="Would upload {0}, delete {1}".format(len(to_upload), len(to_delete)),
            )

        uploaded = []
        for key, rel in to_upload:
            with open(os.path.join(src, rel.replace("/", os.sep)), "rb") as handle:
                client.put_object(Bucket=bucket, Key=key, Body=handle.read())
            uploaded.append(key)
        deleted = []
        for key in to_delete:
            client.delete_object(Bucket=bucket, Key=key)
            deleted.append(key)

        module.exit_json(
            changed=changed,
            summary=summary,
            uploaded=uploaded,
            deleted=deleted,
            msg="Uploaded {0}, deleted {1}".format(len(uploaded), len(deleted)),
        )
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
