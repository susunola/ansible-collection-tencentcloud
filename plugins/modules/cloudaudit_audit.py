#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: cloudaudit_audit
short_description: Manage Tencent Cloud account-level CloudAudit delivery
version_added: "0.14.0"
description: Reconciles account-level management-event delivery to COS, optional CMQ notifications, KMS encryption and logging state.
options:
  audit_name: {type: str, required: true, description: Existing account-level audit name.}
  enabled: {type: bool, default: true, description: Whether CloudAudit logging is running.}
  read_write_attribute: {type: int, choices: [1, 2, 3], default: 3, description: "One for read events, two for write events or three for all events."}
  cos_region: {type: str, required: true, description: COS delivery region.}
  cos_bucket_name: {type: str, required: true, description: COS destination bucket name.}
  create_new_bucket: {type: bool, default: false, description: Ask CloudAudit to create the COS bucket.}
  log_file_prefix: {type: str, default: CloudAudit, description: COS log object prefix.}
  cmq_notify: {type: bool, default: false, description: Enable real-time CMQ queue notifications.}
  cmq_region: {type: str, description: CMQ queue region; required when cmq_notify is true.}
  cmq_queue_name: {type: str, description: CMQ queue name; required when cmq_notify is true.}
  create_new_queue: {type: bool, default: false, description: Ask CloudAudit to create the CMQ queue.}
  kms_encryption: {type: bool, default: false, description: Encrypt delivered COS objects with KMS.}
  kms_region: {type: str, description: KMS region; required when kms_encryption is true.}
  key_id: {type: str, description: Existing KMS key ID used for encryption.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""

EXAMPLES = r"""
- name: Deliver all account management events to encrypted COS
  susunola.tencentcloud.cloudaudit_audit:
    region: ap-guangzhou
    audit_name: default
    cos_region: ap-guangzhou
    cos_bucket_name: audit-logs-1250000000
    log_file_prefix: CloudAudit
    kms_encryption: true
    kms_region: ap-guangzhou
    key_id: key-xxxxxxxx
"""

RETURN = r"""audit: {description: Account-level CloudAudit configuration., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cloudaudit.v20190319 import models, cloudaudit_client

    return models, cloudaudit_client


def describe_request(models, name):
    request = models.DescribeAuditRequest()
    request.AuditName = name
    return request


def update_request(models, p):
    request = models.UpdateAuditRequest()
    request.AuditName, request.ReadWriteAttribute = p["audit_name"], p["read_write_attribute"]
    request.CosRegion, request.CosBucketName = p["cos_region"], p["cos_bucket_name"]
    request.IsCreateNewBucket, request.LogFilePrefix = int(p["create_new_bucket"]), p["log_file_prefix"]
    request.IsEnableCmqNotify, request.IsCreateNewQueue = int(p["cmq_notify"]), int(p["create_new_queue"])
    if p.get("cmq_region"):
        request.CmqRegion = p["cmq_region"]
    if p.get("cmq_queue_name"):
        request.CmqQueueName = p["cmq_queue_name"]
    request.IsEnableKmsEncry = int(p["kms_encryption"])
    if p.get("kms_region"):
        request.KmsRegion = p["kms_region"]
    if p.get("key_id"):
        request.KeyId = p["key_id"]
    return request


def start_request(models, name):
    request = models.StartLoggingRequest()
    request.AuditName = name
    return request


def stop_request(models, name):
    request = models.StopLoggingRequest()
    request.AuditName = name
    return request


def find_audit(module, client, models, name):
    response = module.sdk_call(client.DescribeAudit, describe_request(models, name))
    value = response._serialize(allow_none=True)
    value.pop("RequestId", None)
    return value


def desired(p):
    result = {
        "AuditName": p["audit_name"],
        "ReadWriteAttribute": p["read_write_attribute"],
        "CosRegion": p["cos_region"],
        "CosBucketName": p["cos_bucket_name"],
        "LogFilePrefix": p["log_file_prefix"],
        "IsEnableCmqNotify": int(p["cmq_notify"]),
        "IsEnableKmsEncry": int(p["kms_encryption"]),
    }
    if p.get("cmq_region"):
        result["CmqRegion"] = p["cmq_region"]
    if p.get("cmq_queue_name"):
        result["CmqQueueName"] = p["cmq_queue_name"]
    if p.get("kms_region"):
        result["KmsRegion"] = p["kms_region"]
    if p.get("key_id"):
        result["KeyId"] = p["key_id"]
    return result


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "audit_name": {"required": True},
            "enabled": {"type": "bool", "default": True},
            "read_write_attribute": {"type": "int", "choices": [1, 2, 3], "default": 3},
            "cos_region": {"required": True},
            "cos_bucket_name": {"required": True},
            "create_new_bucket": {"type": "bool", "default": False},
            "log_file_prefix": {"default": "CloudAudit"},
            "cmq_notify": {"type": "bool", "default": False},
            "cmq_region": {},
            "cmq_queue_name": {},
            "create_new_queue": {"type": "bool", "default": False},
            "kms_encryption": {"type": "bool", "default": False},
            "kms_region": {},
            "key_id": {},
        },
        supports_check_mode=True,
    )
    p = module.params
    if p["cmq_notify"] and (not p.get("cmq_region") or not p.get("cmq_queue_name")):
        module.fail_json(msg="cmq_region and cmq_queue_name are required when cmq_notify=true")
    if p["kms_encryption"] and not p.get("kms_region"):
        module.fail_json(msg="kms_region is required when kms_encryption=true")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CloudauditClient, "cloudaudit.tencentcloudapi.com")
    try:
        current = find_audit(module, client, models, p["audit_name"])
        target = desired(p)
        before = {key: current.get(key) for key in target}
        config_changed = before != target
        running = str(current.get("AuditStatus", "")).lower() in ("1", "true", "running", "enable", "enabled")
        state_changed = running != p["enabled"]
        if not config_changed and not state_changed:
            module.exit_json(changed=False, audit=current)
        diff = maybe_diff(module, dict(before, Enabled=running), dict(target, Enabled=p["enabled"]))
        if not module.check_mode:
            if config_changed:
                module.sdk_call(client.UpdateAudit, update_request(models, p))
            if state_changed:
                if p["enabled"]:
                    module.sdk_call(client.StartLogging, start_request(models, p["audit_name"]))
                else:
                    module.sdk_call(client.StopLogging, stop_request(models, p["audit_name"]))
            current = find_audit(module, client, models, p["audit_name"])
        module.exit_json(changed=True, **(diff or {}), audit=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
