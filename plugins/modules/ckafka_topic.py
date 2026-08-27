#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: ckafka_topic
short_description: Manage Tencent Cloud CKafka topics
version_added: "0.12.0"
description:
  - Create, update and delete CKafka topics through the
    C(ckafka.v20190819) API.
  - This module is idempotent. Running it twice leaves the topic unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the topic when it does not exist and updates its
        partitions, replicas, retention and note when it does.
      - C(absent) deletes the topic.
    type: str
    choices: [present, absent]
    default: present
  instance_id:
    description:
      - ID of the CKafka instance the topic belongs to, e.g. C(ckafka-xxx).
      - Required for all operations.
    type: str
    required: true
  topic_name:
    description:
      - Name of the topic, e.g. C(order-events).
      - Required to identify, create, update or delete the topic.
    type: str
    required: true
  partition_num:
    description:
      - Number of partitions, written to V(CreateTopicRequest.PartitionNum)
        and V(ModifyTopicAttributesRequest).
    type: int
    default: 1
  replica_num:
    description:
      - Number of replicas, written to V(CreateTopicRequest.ReplicaNum) and
        V(ModifyTopicAttributesRequest).
    type: int
    default: 2
  retention_ms:
    description:
      - Message retention in milliseconds, written to
        V(CreateTopicRequest.RetentionMs) and V(ModifyTopicAttributesRequest).
    type: int
  retention_bytes:
    description:
      - Message retention in bytes, written to V(CreateTopicRequest) and
        V(ModifyTopicAttributesRequest).
    type: int
  clean_up_policy:
    description:
      - Log cleanup policy, C(delete) removes old messages,
        C(compact) keeps the latest value per key.
    type: str
    choices: [delete, compact]
  note:
    description:
      - Note/description of the topic, written to V(CreateTopicRequest.Note)
        and V(ModifyTopicAttributesRequest.Note).
    type: str
  max_message_bytes:
    description:
      - Maximum message size in bytes, written to
        V(CreateTopicRequest.MaxMessageBytes).
    type: int
  tags:
    description:
      - Tags to apply to the topic as a dict, for example I(env=prod).
      - Only applied at creation.
    type: dict
    default: {}
  retries:
    description: Number of retries for transient SDK failures.
    type: int
    default: 5
  waiter_delay:
    description: Seconds to wait between state-polling attempts.
    type: int
    default: 5
  waiter_timeout:
    description: Overall timeout in seconds for state polling.
    type: int
    default: 120
  user_agent:
    description:
      - Value appended to the SDK User-Agent header so API usage can be
        attributed to this collection.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-ckafka) package on the controller.
  - The CKafka instance itself is not created or destroyed by this module;
    provision it separately (e.g. in the console or with a postpaid instance
    request) to keep this module free of per-hour billing surprises.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a topic with 3 partitions and 2 replicas
  susunola.tencentcloud.ckafka_topic:
    region: ap-guangzhou
    state: present
    instance_id: ckafka-xxxxxxxx
    topic_name: order-events
    partition_num: 3
    replica_num: 2
    retention_ms: 86400000
    note: Order event stream

- name: Scale partitions and update the note
  susunola.tencentcloud.ckafka_topic:
    region: ap-guangzhou
    state: present
    instance_id: ckafka-xxxxxxxx
    topic_name: order-events
    partition_num: 6
    note: Order event stream (scaled)

- name: Delete a topic
  susunola.tencentcloud.ckafka_topic:
    region: ap-guangzhou
    state: absent
    instance_id: ckafka-xxxxxxxx
    topic_name: order-events
'''

RETURN = r'''
topic:
  description: The topic as reported by V(DescribeTopicDetail) after the
    operation.
  returned: success
  type: dict
  sample:
    TopicName: order-events
    PartitionNum: 3
    ReplicaNum: 2
    Note: Order event stream
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_ckafka():
    from tencentcloud.ckafka.v20190819 import models, ckafka_client
    return models, ckafka_client


def _first(collection):
    return collection[0] if collection else None


def find_topic(module, client, models, instance_id, topic_name):
    """Return the matching topic dict or None."""
    request = models.DescribeTopicRequest()
    request.InstanceId = instance_id
    request.Limit = 100
    request.Offset = 0
    request.SearchWord = topic_name
    response = module.sdk_call(client.DescribeTopic, request)
    for item in (response.Result or []):
        if getattr(item, "TopicName", None) == topic_name:
            return item._serialize(allow_none=True)
    return None


def _create(module, client, models, params):
    request = models.CreateTopicRequest()
    request.InstanceId = params["instance_id"]
    request.TopicName = params["topic_name"]
    request.PartitionNum = params["partition_num"]
    request.ReplicaNum = params["replica_num"]
    if params["retention_ms"] is not None:
        request.RetentionMs = params["retention_ms"]
    if params["retention_bytes"] is not None:
        request.RetentionBytes = params["retention_bytes"]
    if params["clean_up_policy"]:
        request.CleanUpPolicy = params["clean_up_policy"]
    if params["note"]:
        request.Note = params["note"]
    if params["max_message_bytes"] is not None:
        request.MaxMessageBytes = params["max_message_bytes"]
    return module.sdk_call(client.CreateTopic, request)


def _validate_partition_scale(module, topic_name, current_partition_num,
                              desired_partition_num):
    """Fail when a partition change would require shrinking the topic.

    CKafka partitions can only be added, never removed.
    """
    if desired_partition_num < current_partition_num:
        module.fail_json(
            msg="CKafka cannot reduce partitions: topic %s currently has %d, "
                "requested %d" % (topic_name, current_partition_num,
                                  desired_partition_num),
        )


def _scale_partitions(module, client, models, instance_id, topic_name,
                      current_partition_num, desired_partition_num):
    """Scale a topic up to *desired_partition_num* via CreatePartition."""
    _validate_partition_scale(module, topic_name, current_partition_num,
                              desired_partition_num)
    if desired_partition_num == current_partition_num:
        return
    request = models.CreatePartitionRequest()
    request.InstanceId = instance_id
    request.TopicName = topic_name
    request.PartitionNum = desired_partition_num - current_partition_num
    module.sdk_call(client.CreatePartition, request)


def _update(module, client, models, instance_id, topic_name, current_partition_num, params):
    request = models.ModifyTopicAttributesRequest()
    request.InstanceId = instance_id
    request.TopicName = topic_name
    if params["replica_num"] is not None:
        request.ReplicaNum = params["replica_num"]
    if params["retention_ms"] is not None:
        request.RetentionMs = params["retention_ms"]
    if params["retention_bytes"] is not None:
        request.RetentionBytes = params["retention_bytes"]
    if params["clean_up_policy"]:
        request.CleanUpPolicy = params["clean_up_policy"]
    if params["note"] is not None:
        request.Note = params["note"]
    if params["max_message_bytes"] is not None:
        request.MaxMessageBytes = params["max_message_bytes"]
    module.sdk_call(client.ModifyTopicAttributes, request)


def _delete(module, client, models, instance_id, topic_name):
    request = models.DeleteTopicRequest()
    request.InstanceId = instance_id
    request.TopicName = topic_name
    module.sdk_call(client.DeleteTopic, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "instance_id": {"type": "str", "required": True},
            "topic_name": {"type": "str", "required": True},
            "partition_num": {"type": "int", "default": 1},
            "replica_num": {"type": "int", "default": 2},
            "retention_ms": {"type": "int"},
            "retention_bytes": {"type": "int"},
            "clean_up_policy": {"type": "str", "choices": ["delete", "compact"]},
            "note": {"type": "str"},
            "max_message_bytes": {"type": "int"},
            "tags": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    instance_id = module.params["instance_id"]
    topic_name = module.params["topic_name"]

    models, ckafka_client = _load_ckafka()
    client = module.create_client(ckafka_client.CkafkaClient, "ckafka.tencentcloudapi.com")

    try:
        current = find_topic(module, client, models, instance_id, topic_name)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="Topic already absent")
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete topic")
        _delete(module, client, models, instance_id, topic_name)
        module.exit_json(changed=True, **(diff or {}), topic=None, msg="Topic deleted")

    # state == present
    if current is None:
        desired = {
            "TopicName": topic_name,
            "PartitionNum": module.params["partition_num"],
            "ReplicaNum": module.params["replica_num"],
        }
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create topic")
        _create(module, client, models, module.params)
        created = find_topic(module, client, models, instance_id, topic_name)
        module.exit_json(changed=True, **(diff or {}), topic=created, msg="Topic created")

    changes = []
    partition_num = module.params["partition_num"]
    if partition_num is not None and current.get("PartitionNum") != partition_num:
        changes.append("partition_num")
    replica_num = module.params["replica_num"]
    if replica_num is not None and current.get("ReplicaNum") != replica_num:
        changes.append("replica_num")
    retention_ms = module.params["retention_ms"]
    if retention_ms is not None and current.get("RetentionMs") != retention_ms:
        changes.append("retention_ms")
    retention_bytes = module.params["retention_bytes"]
    if retention_bytes is not None and current.get("RetentionBytes") != retention_bytes:
        changes.append("retention_bytes")
    clean_up_policy = module.params["clean_up_policy"]
    if clean_up_policy and current.get("CleanUpPolicy") != clean_up_policy:
        changes.append("clean_up_policy")
    note = module.params["note"]
    if note is not None and current.get("Note") != note:
        changes.append("note")
    max_message_bytes = module.params["max_message_bytes"]
    if max_message_bytes is not None and current.get("MaxMessageBytes") != max_message_bytes:
        changes.append("max_message_bytes")

    if not changes:
        module.exit_json(changed=False, topic=current, msg="Topic is up to date")

    diff = maybe_diff(module, current, {
        "PartitionNum": partition_num if partition_num is not None else current.get("PartitionNum"),
        "ReplicaNum": replica_num if replica_num is not None else current.get("ReplicaNum"),
        "Note": note if note is not None else current.get("Note"),
    })
    if partition_num is not None and partition_num != current.get("PartitionNum"):
        _validate_partition_scale(module, topic_name, current.get("PartitionNum"),
                                  partition_num)
    if module.check_mode:
        module.exit_json(changed=True, **(diff or {}), msg="Would update topic")

    if partition_num is not None and partition_num != current.get("PartitionNum"):
        _scale_partitions(module, client, models, instance_id, topic_name,
                          current.get("PartitionNum"), partition_num)
    _update(module, client, models, instance_id, topic_name,
            current.get("PartitionNum"), module.params)
    updated = find_topic(module, client, models, instance_id, topic_name)
    module.exit_json(changed=True, **(diff or {}), topic=updated, msg="Topic updated")


def main():
    run_module()


if __name__ == "__main__":
    main()
