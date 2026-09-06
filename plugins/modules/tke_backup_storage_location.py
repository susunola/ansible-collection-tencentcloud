#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tke_backup_storage_location
short_description: Manage Tencent Kubernetes Engine backup storage locations
version_added: "0.14.0"
description:
  - Creates and deletes a regional TKE backup storage location backed by object storage.
  - The API exposes no update operation; configuration drift requires explicit C(force_replace=true).
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  name: {type: str, required: true, description: Backup storage location name.}
  storage_region: {type: str, description: Region containing the object storage bucket.}
  bucket: {type: str, description: Object storage bucket name.}
  provider: {type: str, default: tencentcloud, description: Storage provider.}
  path: {type: str, default: '', description: Object prefix inside the bucket.}
  force_replace: {type: bool, default: false, description: Delete and recreate when immutable configuration differs.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tke_backup_storage_location:
    name: production-backups
    storage_region: ap-guangzhou
    bucket: tke-backup-1250000000
    path: production/
"""
RETURN = r"""backup_storage_location: {description: TKE backup storage location metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tke.v20180525 import models, tke_client

    return models, tke_client


def describe_request(models, name):
    request = models.DescribeBackupStorageLocationsRequest()
    request.Names = [name]
    return request


def create_request(models, p):
    request = models.CreateBackupStorageLocationRequest()
    request.StorageRegion, request.Bucket, request.Name = p["storage_region"], p["bucket"], p["name"]
    request.Provider, request.Path = p["provider"], p["path"]
    return request


def delete_request(models, name):
    request = models.DeleteBackupStorageLocationRequest()
    request.Name = name
    return request


def find(module, client, models, name):
    response = module.sdk_call(client.DescribeBackupStorageLocations, describe_request(models, name))
    for item in response.BackupStorageLocationSet or []:
        value = item._serialize(allow_none=True)
        if value.get("Name") == name:
            return value
    return None


def comparable(value):
    return {
        "Name": value.get("Name"),
        "StorageRegion": value.get("StorageRegion"),
        "Bucket": value.get("Bucket"),
        "Provider": value.get("Provider") or "tencentcloud",
        "Path": value.get("Path") or "",
    }


def desired(p):
    return {"Name": p["name"], "StorageRegion": p["storage_region"], "Bucket": p["bucket"], "Provider": p["provider"], "Path": p["path"]}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "name": {"required": True},
            "storage_region": {},
            "bucket": {},
            "provider": {"default": "tencentcloud"},
            "path": {"default": ""},
            "force_replace": {"type": "bool", "default": False},
        },
        required_if=[("state", "present", ["storage_region", "bucket"])],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TkeClient, "tke.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["name"])
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, backup_storage_location=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteBackupStorageLocation, delete_request(models, p["name"]))
            module.exit_json(changed=True, **(diff or {}), backup_storage_location=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, backup_storage_location=current)
        diff = maybe_diff(module, before, target)
        if current and not p["force_replace"]:
            module.fail_json(
                msg="TKE backup storage location configuration is immutable; set force_replace=true to recreate it", current=before, desired=target
            )
        if not module.check_mode:
            if current:
                module.sdk_call(client.DeleteBackupStorageLocation, delete_request(models, p["name"]))
            module.sdk_call(client.CreateBackupStorageLocation, create_request(models, p))
            current = find(module, client, models, p["name"])
        module.exit_json(changed=True, **(diff or {}), backup_storage_location=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
