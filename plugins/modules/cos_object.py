#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cos_object
short_description: Manage Tencent Cloud COS objects
version_added: "0.14.0"
description:
  - Upload, download, and delete Tencent Cloud Object Storage (COS) objects.
  - COS is not part of the Tencent Cloud API 3.0 family; this module uses the
    C(qcloud_cos) SDK (C(cos-python-sdk-v5) package) instead.
  - This module is idempotent. Uploading the same content again reports
    C(changed=false), and deleting an absent object reports C(changed=false).
  - Upload compares the object ETag against the local MD5 digest; the ETag
    comparison is exact for single-part uploads. Metadata and storage-class
    drift also trigger a re-upload even when the content is unchanged.
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) uploads C(src)/C(content) to the object, or downloads the
        object to C(dest) when neither C(src) nor C(content) is given.
      - C(absent) deletes the object if it exists.
    type: str
    choices: [present, absent]
    default: present
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
  object:
    description:
      - Object key (the full path inside the bucket), for example
        C(images/logo.png).
    type: str
    required: true
  src:
    description:
      - Local file path to upload to the object.
      - Mutually exclusive with O(content).
    type: path
  content:
    description:
      - Inline string to upload as the object body.
      - Mutually exclusive with O(src).
    type: str
  dest:
    description:
      - Local file path to download the object to.
      - Required when O(state=present) and neither O(src) nor O(content) is
        given (the download form of the module).
    type: path
  force:
    description:
      - When uploading, re-upload even when the remote ETag matches the local
        content.
      - When downloading, overwrite an existing local file even when its MD5
        matches the remote ETag.
    type: bool
    default: false
  metadata:
    description:
      - User-defined object metadata as a dict; keys are sent as
        C(x-cos-meta-<key>) headers. Replaced in full on upload.
    type: dict
    default: {}
  storage_class:
    description:
      - Storage class of the object, for example C(STANDARD), C(STANDARD_IA),
        C(INTELLIGENT_TIERING) or C(ARCHIVE). Applied on upload.
    type: str
    default: STANDARD
  presign:
    description:
      - When C(true), do not transfer anything; instead return a pre-signed
        URL for the object as C(url), signed for the HTTP O(method).
        Nothing is read or written in the bucket and the task reports
        C(changed=false).
      - Only valid with O(state=present).
    type: bool
    default: false
  method:
    description:
      - HTTP method the pre-signed URL is signed for when O(presign=true);
        C(GET) mints a download URL, C(PUT) an upload URL.
      - Passing a non-default value with O(presign=false) fails the task.
    type: str
    choices: [GET, PUT]
    default: GET
  expires:
    description:
      - Validity of the pre-signed URL in seconds when O(presign=true).
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
  - O(role_arn) is honoured; the temporary credentials obtained via STS
    C(AssumeRole) additionally require the C(tencentcloud-sdk-python-sts)
    package.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Upload a local file to COS
  susunola.tencentcloud.cos_object:
    region: ap-guangzhou
    state: present
    bucket: mybucket
    appid: "1300000000"
    object: images/logo.png
    src: /var/www/logo.png

- name: Upload inline content with metadata
  susunola.tencentcloud.cos_object:
    region: ap-guangzhou
    state: present
    bucket: mybucket
    appid: "1300000000"
    object: config.json
    content: "{\"env\": \"prod\"}"
    metadata:
      owner: platform
    storage_class: STANDARD_IA

- name: Download an object to a local path
  susunola.tencentcloud.cos_object:
    region: ap-guangzhou
    state: present
    bucket: mybucket
    appid: "1300000000"
    object: reports/daily.csv
    dest: /tmp/daily.csv

- name: Delete an object
  susunola.tencentcloud.cos_object:
    region: ap-guangzhou
    state: absent
    bucket: mybucket
    appid: "1300000000"
    object: images/logo.png

- name: Mint a short-lived pre-signed download URL
  susunola.tencentcloud.cos_object:
    region: ap-guangzhou
    state: present
    bucket: mybucket
    appid: "1300000000"
    object: reports/daily.csv
    presign: true
    method: GET
    expires: 600
  register: presigned

- name: Mint a short-lived pre-signed upload URL
  susunola.tencentcloud.cos_object:
    region: ap-guangzhou
    state: present
    bucket: mybucket
    appid: "1300000000"
    object: uploads/new-asset.zip
    presign: true
    method: PUT
  register: upload_url
'''

RETURN = r'''
object:
  description: The object as reported by COS after the operation.
  returned: success
  type: dict
  sample:
    key: images/logo.png
    bucket: mybucket-1300000000
    etag: '"9f86d081884c7d659a2feaa0c55ad015"'
    content_length: 11
    storage_class: STANDARD
    metadata:
      x-cos-meta-owner: platform
url:
  description: The pre-signed URL, signed with the module credentials.
  returned: when O(presign=true)
  type: str
  sample: https://mybucket-1300000000.cos.ap-guangzhou.myqcloud.com/images/logo.png?q-sign-algorithm=sha1&...
'''

import hashlib
import os

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def etag_value(etag):
    """Strip the surrounding quotes COS wraps ETags in, if present."""
    if etag is None:
        return None
    value = str(etag).strip()
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        return value[1:-1]
    return value


def md5_of_bytes(data):
    return hashlib.md5(data).hexdigest()


def md5_of_file(path):
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_metadata(metadata):
    """Return user metadata with the COS ``x-cos-meta-`` header prefix."""
    return {
        "x-cos-meta-{0}".format(key): str(value)
        for key, value in sorted((metadata or {}).items())
    }


def describe_object(client, bucket, key):
    """Return a plain dict describing an object, or ``None`` when absent."""
    try:
        head = client.head_object(Bucket=bucket, Key=key)
    except Exception as exc:
        if cos.is_not_found(exc):
            return None
        raise
    return {
        "key": key,
        "bucket": bucket,
        "etag": etag_value(head.get("ETag")),
        "content_length": int(head.get("Content-Length") or 0) or None,
        "storage_class": head.get("StorageClass", "STANDARD"),
        "metadata": {
            k: v for k, v in (head.get("Metadata") or {}).items()
            if k.lower().startswith("x-cos-meta-")
        },
    }


def upload_body(client, bucket, key, body, metadata, storage_class):
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        Metadata=metadata,
        StorageClass=storage_class,
    )


def download_object(client, bucket, key, dest):
    """Stream the object body to ``dest`` (COS bodies are not seekable)."""
    response = client.get_object(Bucket=bucket, Key=key)
    body = response.get("Body")
    if body is None:
        raise RuntimeError("COS get_object returned no Body for {0}/{1}".format(bucket, key))
    try:
        body.get_stream_to_file(dest)
    except AttributeError:
        with open(dest, "wb") as handle:
            handle.write(body.read())


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "bucket": {"type": "str", "required": True},
            "appid": {"type": "str"},
            "object": {"type": "str", "required": True},
            "src": {"type": "path"},
            "content": {"type": "str"},
            "dest": {"type": "path"},
            "force": {"type": "bool", "default": False},
            "metadata": {"type": "dict", "default": {}},
            "storage_class": {"type": "str", "default": "STANDARD"},
            "presign": {"type": "bool", "default": False},
            "method": {"type": "str", "choices": ["GET", "PUT"], "default": "GET"},
            "expires": {"type": "int", "default": 3600},
        },
        supports_check_mode=True,
        mutually_exclusive=[("src", "content")],
    )
    cos.require_cos_sdk(module)

    state = module.params["state"]
    bucket_short = module.params["bucket"]
    key = module.params["object"]
    src = module.params["src"]
    content = module.params["content"]
    dest = module.params["dest"]
    force = module.params["force"]
    presign = module.params["presign"]
    method = module.params["method"]
    metadata = normalize_metadata(module.params["metadata"])
    storage_class = module.params["storage_class"]

    if state == "absent" and presign:
        module.fail_json(msg="presign is only valid with state=present")
    if method != "GET" and not presign:
        module.fail_json(msg="method only applies when presign=true")

    appid = cos.resolve_appid(module)
    bucket = cos.bucket_full_name(bucket_short, appid)
    client = cos.create_cos_client(module)

    try:
        if presign:
            url = client.get_presigned_url(
                Bucket=bucket, Key=key, Method=method,
                Expired=module.params["expires"],
            )
            module.exit_json(changed=False, url=url, msg="Pre-signed URL generated")

        current = describe_object(client, bucket, key)

        if state == "absent":
            if current is None:
                module.exit_json(changed=False, msg="Object already absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would delete object")
            client.delete_object(Bucket=bucket, Key=key)
            module.exit_json(changed=True, **(diff or {}), object=None, msg="Object deleted")

        # state == present
        if src or content is not None:
            if src is not None:
                body = open(src, "rb").read()
                digest = md5_of_file(src)
            else:
                body = content.encode("utf-8")
                digest = md5_of_bytes(body)
            desired = {
                "key": key,
                "bucket": bucket,
                "etag": digest,
                "content_length": len(body),
                "storage_class": storage_class,
                "metadata": metadata,
            }
            if current is not None and not force:
                unchanged = (
                    etag_value(current.get("etag")) == digest
                    and current.get("storage_class", "STANDARD") == storage_class
                    and current.get("metadata") == metadata
                )
                if unchanged:
                    module.exit_json(changed=False, object=current, msg="Object is up to date")
            diff = maybe_diff(module, current, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would upload object")
            upload_body(client, bucket, key, body, metadata, storage_class)
            updated = describe_object(client, bucket, key)
            module.exit_json(
                changed=True, **(diff or {}), object=updated, msg="Object uploaded"
            )

        # Download form: no src/content given.
        if dest is None:
            module.fail_json(msg="dest is required when neither src nor content is given")
        if current is None:
            module.fail_json(msg="Object {0} does not exist in bucket {1}".format(key, bucket))
        local_digest = md5_of_file(dest) if os.path.exists(dest) else None
        desired = {
            "key": key,
            "bucket": bucket,
            "etag": etag_value(current.get("etag")),
            "content_length": current.get("content_length"),
            "storage_class": current.get("storage_class"),
            "metadata": current.get("metadata"),
        }
        if local_digest == etag_value(current.get("etag")) and not force:
            module.exit_json(changed=False, object=current, msg="Local file is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would download object")
        download_object(client, bucket, key, dest)
        module.exit_json(
            changed=True, **(diff or {}), object=current, msg="Object downloaded"
        )
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
