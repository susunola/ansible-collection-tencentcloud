#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tdmq_topic
short_description: Manage Tencent Cloud TDMQ Pulsar topics
version_added: "0.14.0"
description: Creates, updates and deletes Pulsar topics in TDMQ.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  cluster_id:
    description:
      - Pulsar cluster ID.
    type: str
    required: true
  environment_id:
    description:
      - Pulsar namespace name.
    type: str
    required: true
  name:
    description:
      - Topic name.
    type: str
    required: true
  partitions:
    description:
      - Partition count. Existing topics can only be expanded.
    type: int
    default: 1
  topic_type:
    description:
      - Pulsar topic type.
    type: int
    choices: [0, 1, 2, 3]
    default: 2
  remark:
    description:
      - Topic remark.
    type: str
    default: ''
  message_ttl:
    description:
      - Unconsumed message TTL in seconds.
    type: int
    default: 86400
  isolate_consumer:
    description:
      - Enable abnormal consumer isolation.
    type: bool
    default: false
  ack_timeout:
    description:
      - Consumer acknowledgement timeout in seconds.
    type: int
    default: 60
  delay_message_policy:
    description:
      - How delayed delivery is handled for messages on the topic.
    type: str
    choices: [defaultPolicy, timingwheelPolicy]
    default: defaultPolicy
  force:
    description:
      - Force deletion.
    type: bool
    default: false

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
attributes:
  check_mode:
    description:
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  diff_mode:
    description:
      - Returns the difference between the observed and the requested state
        when the task runs with C(--diff).
    support: full
  idempotent:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
seealso:
  - module: susunola.tencentcloud.tdmq_topic_info
    description: Gather information about Tencent Cloud TDMQ topics.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tdmq_topic:
    cluster_id: pulsar-xxxxxxxx
    environment_id: production
    name: orders
    partitions: 4
    message_ttl: 86400

- name: Delete the topic
  susunola.tencentcloud.tdmq_topic:
    state: absent
    cluster_id: pulsar-xxxxxxxx
    environment_id: production
    name: orders
'''
RETURN = r'''
topic:
  description:
    - TDMQ Pulsar topic metadata.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    TopicName: orders
    ClusterId: pulsar-abc
    EnvironmentId: production
    Partitions: 4
    PulsarTopicType: 2
    Remark: orders queue
    MsgTTL: 3600
    IsolateConsumerEnable: true
    AckTimeOut: 30
    DelayMessagePolicy: timingwheelPolicy
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load_tdmq():
    from tencentcloud.tdmq.v20200217 import models, tdmq_client

    return models, tdmq_client


def build_describe_request(models, cluster_id, environment_id, name):
    request = models.DescribeTopicsRequest()
    request.ClusterId, request.EnvironmentId = cluster_id, environment_id
    request.Offset, request.Limit = 0, 20
    item = models.Filter()
    item.Name, item.Values = "TopicName", [name]
    request.Filters = [item]
    return request


def _apply(request, params):
    request.ClusterId, request.EnvironmentId = params["cluster_id"], params["environment_id"]
    request.TopicName, request.Partitions = params["name"], params["partitions"]
    request.Remark, request.MsgTTL = params["remark"], params["message_ttl"]
    request.IsolateConsumerEnable, request.AckTimeOut = params["isolate_consumer"], params["ack_timeout"]
    request.DelayMessagePolicy = params["delay_message_policy"]
    return request


def build_create_request(models, params):
    request = _apply(models.CreateTopicRequest(), params)
    request.PulsarTopicType = params["topic_type"]
    return request


def build_update_request(models, params):
    return _apply(models.ModifyTopicRequest(), params)


def build_delete_request(models, cluster_id, environment_id, name, force=False):
    request = models.DeleteTopicsRequest()
    item = models.TopicRecord()
    item.EnvironmentId, item.TopicName = environment_id, name
    request.TopicSets, request.ClusterId, request.EnvironmentId = [item], cluster_id, environment_id
    request.Force = force
    return request


def find_topic(module, client, models, cluster_id, environment_id, name):
    response = module.sdk_call(client.DescribeTopics, build_describe_request(models, cluster_id, environment_id, name))
    matches = [x._serialize(allow_none=True) for x in (response.TopicSets or []) if x.TopicName == name]
    if len(matches) > 1:
        module.fail_json(msg="Multiple TDMQ topics have the requested name", name=name)
    return matches[0] if matches else None


def _desired(params):
    return {
        "TopicName": params["name"],
        "Partitions": params["partitions"],
        "PulsarTopicType": params["topic_type"],
        "Remark": params["remark"],
        "MsgTTL": params["message_ttl"],
        "IsolateConsumerEnable": params["isolate_consumer"],
        "AckTimeOut": params["ack_timeout"],
        "DelayMessagePolicy": params["delay_message_policy"],
    }


def _matches(current, desired):
    return all(current.get(key) == value for key, value in desired.items())


def wait_for_topic(module, client, models, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        p = module.params
        current = find_topic(module, client, models, p["cluster_id"], p["environment_id"], p["name"])
        if absent and current is None:
            return None
        if not absent and current and _matches(current, desired):
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for TDMQ topic convergence", topic=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "cluster_id": {"type": "str", "required": True},
            "environment_id": {"type": "str", "required": True},
            "name": {"type": "str", "required": True},
            "partitions": {"type": "int", "default": 1},
            "topic_type": {"type": "int", "choices": [0, 1, 2, 3], "default": 2},
            "remark": {"type": "str", "default": ""},
            "message_ttl": {"type": "int", "default": 86400},
            "isolate_consumer": {"type": "bool", "default": False},
            "ack_timeout": {"type": "int", "default": 60},
            "delay_message_policy": {"type": "str", "choices": ["defaultPolicy", "timingwheelPolicy"], "default": "defaultPolicy"},
            "force": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    p = module.params
    if not 1 <= p["partitions"] <= 32:
        module.fail_json(msg="partitions must be between 1 and 32")
    module.require_sdk()
    models, client_module = _load_tdmq()
    client = module.create_client(client_module.TdmqClient, "tdmq.tencentcloudapi.com")
    try:
        current = find_topic(module, client, models, p["cluster_id"], p["environment_id"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, topic=None, msg="TDMQ topic is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), topic=current, msg="Would delete TDMQ topic")
            module.sdk_call(client.DeleteTopics, build_delete_request(models, p["cluster_id"], p["environment_id"], p["name"], p["force"]))
            wait_for_topic(module, client, models, absent=True)
            module.exit_json(changed=True, **(diff or {}), topic=None, msg="TDMQ topic deleted")
        desired = _desired(p)
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), topic=None, msg="Would create TDMQ topic")
            module.sdk_call(client.CreateTopic, build_create_request(models, p))
            current = wait_for_topic(module, client, models, desired)
            module.exit_json(changed=True, **(diff or {}), topic=current, msg="TDMQ topic created")
        if p["partitions"] < int(current.get("Partitions") or 0):
            module.fail_json(
                msg="TDMQ topic partitions cannot be decreased", current_partitions=current.get("Partitions"), requested_partitions=p["partitions"]
            )
        if _matches(current, desired):
            module.exit_json(changed=False, topic=current, msg="TDMQ topic is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), topic=current, msg="Would update TDMQ topic")
        module.sdk_call(client.ModifyTopic, build_update_request(models, p))
        current = wait_for_topic(module, client, models, desired)
        module.exit_json(changed=True, **(diff or {}), topic=current, msg="TDMQ topic updated")
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
