#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: mqtt_topic
short_description: Manage Tencent Cloud MQTT topics
version_added: "0.14.0"
description: Creates, updates and deletes MQTT topics.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: MQTT instance ID.}
  topic: {type: str, required: true, description: Topic name.}
  remark: {type: str, default: '', description: Topic remark.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.mqtt_topic:
    instance_id: mqtt-xxxxxxxx
    topic: orders/created
    remark: Order events
"""
RETURN = r"""topic_info: {description: Effective MQTT topic metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.mqtt.v20240516 import models, mqtt_client

    return models, mqtt_client


def describe_request(models, p):
    r = models.DescribeTopicRequest()
    r.InstanceId, r.Topic = p["instance_id"], p["topic"]
    return r


def create_request(models, p):
    r = models.CreateTopicRequest()
    r.InstanceId, r.Topic, r.Remark = p["instance_id"], p["topic"], p["remark"]
    return r


def update_request(models, p):
    r = models.ModifyTopicRequest()
    r.InstanceId, r.Topic, r.Remark = p["instance_id"], p["topic"], p["remark"]
    return r


def delete_request(models, p):
    r = models.DeleteTopicRequest()
    r.InstanceId, r.Topic = p["instance_id"], p["topic"]
    return r


def find(module, client, models, p):
    try:
        value = module.sdk_call(client.DescribeTopic, describe_request(models, p))._serialize(allow_none=True)
        value.pop("RequestId", None)
        return value
    except Exception as exc:
        if "notfound" in str(exc).lower() or "not exist" in str(exc).lower():
            return None
        raise


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "instance_id": {"required": True},
            "topic": {"required": True},
            "remark": {"default": ""},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.MqttClient, "mqtt.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, topic_info=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteTopic, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), topic_info=None)
        target = {"InstanceId": p["instance_id"], "Topic": p["topic"], "Remark": p["remark"]}
        before = None if not current else {k: current.get(k) or "" for k in target}
        if before == target:
            module.exit_json(changed=False, topic_info=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyTopic if current else client.CreateTopic, update_request(models, p) if current else create_request(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), topic_info=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
