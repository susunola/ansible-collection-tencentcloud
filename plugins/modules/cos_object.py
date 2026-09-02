#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cos_object
short_description: Manage objects in a Tencent Cloud COS bucket
version_added: "0.14.0"
description:
  - Upload, download, delete and presign objects in a Tencent Cloud Object
    Storage (COS) bucket.
  - COS is not part of the Tencent Cloud API 3.0 family; this module uses the
    C(qcloud_cos) SDK (C(cos-python-sdk-v5) package) instead.
  - This module is idempotent. An upload whose object already exists with the
    same size and content hash, and a download whose destination file already
    matches the remote object, report C(changed=false).
  - Supports check mode; no data is transferred in check mode, only reads.
options:
  state:
    description:
      - C(present) uploads the local file O(src) to the object O(key)
        (O(mode=sync)) or mints a pre-signed URL (O(mode=presign)).
      - C(absent) deletes the object O(key) when it exists; C(absent) only
        supports the default O(mode=sync).
    type: str
    choices: [present, absent]
    default: present
  bucket:
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
  key:
    description:
      - Object key inside the bucket, for example C(site/index.html).
    type: str
    required: true
  src:
    description:
      - Local file path uploaded when O(state=present).
      - Required when O(state=present) and O(mode=sync).
    type: path
  dest:
    description:
      - Local file path the object is downloaded to when O(mode=download).
      - Required when O(mode=download).
    type: path
  mode:
    description:
      - C(sync) uploads or deletes the object as described by O(state).
      - C(download) downloads the object O(key) to the local file O(dest),
        regardless of O(state); mirrors the C(mode) convention of
        M(amazon.aws.s3_object).
      - C(presign) generates a pre-signed URL for the object (method selected
        by O(method)) instead of transferring anything; the URL is returned
        as C(url), no bucket resource is changed and the task reports
        C(changed=false).
      - O(state=absent) only supports the default C(sync) mode; combining it
        with C(download) or C(presign) fails the task.
    type: str
    choices: [sync, presign, download]
    default: sync
  method:
    description:
      - HTTP method the pre-signed URL is signed for when O(mode=presign);
        C(GET) mints a download URL, C(PUT) an upload URL.
      - Only meaningful with O(mode=presign); passing a non-default value
        with any other mode fails the task.
    type: str
    choices: [GET, PUT]
    default: PUT
  expires:
    description:
      - Validity of the pre-signed URL in seconds when O(mode=presign).
    type: int
    default: 3600
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
  - Upload idempotency compares the object size and, for non-multipart
    objects, the ETag content hash. Multipart ETags carry a C(-) suffix and
    are compared by size only.
  - O(role_arn) is honoured; the temporary credentials obtained via STS
    C(AssumeRole) additionally require the C(tencentcloud-sdk-python-sts)
    package.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Upload a file to a COS bucket
  susunola.tencentcloud.cos_object:
    region: ap-guangzhou
    bucket: mybucket
    appid: "1300000000"
    key: site/index.html
    src: ./dist/index.html

- name: Download an object
  susunola.tencentcloud.cos_object:
    region: ap-guangzhou
    bucket: mybucket
    appid: "1300000000"
    key: site/index.html
    mode: download
    dest: ./downloads/index.html

- name: Delete an object
  susunola.tencentcloud.cos_object:
    region: ap-guangzhou
    bucket: mybucket
    appid: "1300000000"
    key: site/index.html
    state: absent

- name: Generate a pre-signed upload URL
  susunola.tencentcloud.cos_object:
    region: ap-guangzhou
    bucket: mybucket
    appid: "1300000000"
    key: uploads/new-asset.zip
    mode: presign
    expires: 600
  register: presigned

- name: Generate a pre-signed download URL
  susunola.tencentcloud.cos_object:
    region: ap-guangzhou
    bucket: mybucket
    appid: "1300000000"
    key: site/index.html
    mode: presign
    method: GET
    expires: 600
  register: download_url
'''

RETURN = r'''
bucket:
  description: The full bucket name the object lives in.
  returned: success
  type: str
  sample: mybucket-1300000000
key:
  description: The object key.
  returned: success
  type: str
  sample: site/index.html
dest:
  description: Local file the object was downloaded to.
  returned: when O(mode=download)
  type: str
  sample: /home/user/downloads/index.html
url:
  description: The pre-signed URL, signed with the module credentials.
  returned: when O(mode=presign)
  type: str
  sample: https://mybucket-1300000000.cos.ap-guangzhou.myqcloud.com/site/index.html?q-sign-algorithm=sha1&...
etag:
  description: ETag of the remote object after the operation, when available.
  returned: success
  type: str
  sample: '"d41d8cd98f00b204e9800998ecf8427e"'
'''

import hashlib
import os

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def local_md5(path):
    """Return the hex MD5 of a local file, reading it in chunks."""
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def head_object(client, full_name, key):
    """Return the object's HEAD metadata dict, or None when it is absent."""
    try:
        return client.head_object(Bucket=full_name, Key=key)
    except Exception as exc:
        if cos.is_not_found(exc):
            return None
        raise


def object_matches(head, local_path):
    """True when the remote object matches the local file in size and hash.

    The ETag of a simple upload is the hex MD5 of the content; multipart
    ETags carry a ``-`` suffix and are compared by size only.
    """
    if head is None:
        return False
    try:
        size = int(head.get("Content-Length"))
    except (TypeError, ValueError):
        return False
    if size != os.path.getsize(local_path):
        return False
    etag = (head.get("ETag") or "").strip('"')
    if etag and "-" not in etag:
        return etag == local_md5(local_path)
    return True


def download_matches(head, dest):
    """True when the local destination already mirrors the remote object."""
    if not os.path.isfile(dest):
        return False
    return object_matches(head, dest)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "bucket": {"type": "str", "required": True},
            "appid": {"type": "str"},
            # Object key, not a credential; the explicit no_log=False documents that.
            "key": {"type": "str", "required": True, "no_log": False},
            "src": {"type": "path"},
            "dest": {"type": "path"},
            "mode": {"type": "str", "choices": ["sync", "presign", "download"], "default": "sync"},
            "method": {"type": "str", "choices": ["GET", "PUT"], "default": "PUT"},
            "expires": {"type": "int", "default": 3600},
        },
        supports_check_mode=True,
    )
    cos.require_cos_sdk(module)

    state = module.params["state"]
    bucket = module.params["bucket"]
    key = module.params["key"]
    src = module.params["src"]
    dest = module.params["dest"]
    mode = module.params["mode"]
    method = module.params["method"]

    if state == "absent" and mode != "sync":
        module.fail_json(msg="state=absent only supports the default mode=sync")
    if method != "PUT" and mode != "presign":
        module.fail_json(msg="method only applies to mode=presign")

    appid = cos.resolve_appid(module)
    full_name = cos.bucket_full_name(bucket, appid)
    client = cos.create_cos_client(module)

    result = {"bucket": full_name, "key": key}

    try:
        if mode == "presign":
            url = client.get_presigned_url(
                Bucket=full_name, Key=key, Method=method,
                Expired=module.params["expires"],
            )
            module.exit_json(changed=False, **result, url=url, msg="Pre-signed URL generated")

        head = head_object(client, full_name, key)

        if state == "absent":
            if head is None:
                module.exit_json(changed=False, **result, msg="Object already absent")
            diff = maybe_diff(module, {"bucket": full_name, "key": key}, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), **result, msg="Would delete object")
            client.delete_object(Bucket=full_name, Key=key)
            module.exit_json(changed=True, **(diff or {}), **result, msg="Object deleted")

        if state == "present" and mode == "sync":
            if not src:
                module.fail_json(msg="src is required when state=present and mode=sync")
            if not os.path.isfile(src):
                module.fail_json(msg="src does not exist or is not a file: {0}".format(src))
            desired = {"bucket": full_name, "key": key, "size": os.path.getsize(src)}
            if object_matches(head, src):
                module.exit_json(changed=False, **result, etag=(head.get("ETag") or ""), msg="Object is up to date")
            current = None
            if head is not None:
                current = {"bucket": full_name, "key": key, "size": int(head.get("Content-Length") or 0)}
            diff = maybe_diff(module, current, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), **result, msg="Would upload object")
            response = client.upload_file(Bucket=full_name, Key=key, LocalFilePath=src)
            module.exit_json(
                changed=True, **(diff or {}), **result,
                etag=((response or {}).get("ETag") or ""),
                msg="Object uploaded",
            )

        # mode == download
        if not dest:
            module.fail_json(msg="dest is required when mode=download")
        if head is None:
            module.fail_json(msg="Object does not exist: cos://{0}/{1}".format(full_name, key))
        result["etag"] = head.get("ETag") or ""
        if download_matches(head, dest):
            module.exit_json(changed=False, **result, dest=dest, msg="Local file is up to date")
        diff = maybe_diff(
            module,
            {"dest": dest} if os.path.isfile(dest) else None,
            {"dest": dest},
        )
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), **result, dest=dest, msg="Would download object")
        client.download_file(Bucket=full_name, Key=key, DestFilePath=dest)
        module.exit_json(changed=True, **(diff or {}), **result, dest=dest, msg="Object downloaded")
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
