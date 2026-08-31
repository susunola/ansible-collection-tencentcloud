#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: ckafka_datahub_topic
short_description: Manage Tencent Cloud CKafka Datahub topics
version_added: "0.14.0"
description: Creates, updates and deletes a CKafka Datahub elastic topic while suppressing returned credentials.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  name: {type: str, required: true, description: Datahub topic resource name.}
  partition_num: {type: int, default: 1, description: Immutable partition count.}
  retention_ms: {type: int, default: 86400000, description: Message retention in milliseconds.}
  note: {type: str, default: '', description: Topic note.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.ckafka_datahub_topic:
    name: 1250000000-orders-stream
    partition_num: 6
    retention_ms: 604800000
    note: Order event stream
"""
RETURN = r"""datahub_topic: {description: CKafka Datahub topic metadata without username or password., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.ckafka.v20190819 import ckafka_client, models

    return models, ckafka_client


def describe_request(models, name):
    request = models.DescribeDatahubTopicRequest()
    request.Name = name
    return request


def create_request(models, p):
    request = models.CreateDatahubTopicRequest()
    request.Name, request.PartitionNum, request.RetentionMs, request.Note = p["name"], p["partition_num"], p["retention_ms"], p["note"]
    return request


def update_request(models, p):
    request = models.ModifyDatahubTopicRequest()
    request.Name, request.RetentionMs, request.Note = p["name"], p["retention_ms"], p["note"]
    return request


def delete_request(models, name):
    request = models.DeleteDatahubTopicRequest()
    request.Name = name
    return request


def sanitize(value):
    return {key: item for key, item in (value or {}).items() if key not in ("UserName", "Password")}


def find(module, client, models, name):
    try:
        response = module.sdk_call(client.DescribeDatahubTopic, describe_request(models, name))
        return sanitize(response.Result._serialize(allow_none=True)) if response.Result else None
    except Exception as exc:
        if is_not_found(exc):
            return None
        raise


def comparable(value):
    return {
        "Name": value.get("Name"),
        "PartitionNum": int(value.get("PartitionNum") or 0),
        "RetentionMs": int(value.get("RetentionMs") or 0),
        "Note": value.get("Note") or "",
    }


def desired(p):
    return {"Name": p["name"], "PartitionNum": p["partition_num"], "RetentionMs": p["retention_ms"], "Note": p["note"]}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "name": {"required": True},
            "partition_num": {"type": "int", "default": 1},
            "retention_ms": {"type": "int", "default": 86400000},
            "note": {"default": ""},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CkafkaClient, "ckafka.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["name"])
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, datahub_topic=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteDatahubTopic, delete_request(models, p["name"]))
            module.exit_json(changed=True, **(diff or {}), datahub_topic=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, datahub_topic=current)
        diff = maybe_diff(module, before, target)
        if current:
            require_immutable_unchanged(module, before, target, ("PartitionNum",), "CKafka Datahub topic")
        if not module.check_mode:
            module.sdk_call(
                client.ModifyDatahubTopic if current else client.CreateDatahubTopic, update_request(models, p) if current else create_request(models, p)
            )
            current = find(module, client, models, p["name"])
        module.exit_json(changed=True, **(diff or {}), datahub_topic=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
