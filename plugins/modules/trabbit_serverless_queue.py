#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: trabbit_serverless_queue
short_description: Manage Tencent Cloud RabbitMQ Serverless queues
version_added: "0.14.0"
description: Creates, updates and deletes RabbitMQ Serverless classic or quorum queues while protecting immutable queue arguments.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: RabbitMQ Serverless instance ID.}
  virtual_host: {type: str, required: true, description: Virtual-host name.}
  name: {type: str, required: true, description: Queue name.}
  queue_type: {type: str, choices: [classic, quorum], description: Queue type; defaults to classic during creation.}
  durable: {type: bool, description: Durable flag; defaults to true during creation.}
  auto_delete: {type: bool, description: Automatic deletion flag; defaults to false during creation.}
  remark: {type: str, default: '', description: Queue remark.}
  message_ttl: {type: int, description: Message TTL in milliseconds.}
  auto_expire: {type: int, description: Unused-queue expiration in milliseconds; immutable after creation.}
  max_length: {type: int, description: Maximum message count; immutable after creation.}
  max_length_bytes: {type: int, description: Maximum byte size; immutable after creation.}
  delivery_limit: {type: int, description: Quorum delivery limit; immutable after creation.}
  overflow_behaviour: {type: str, choices: [drop-head, reject-publish, reject-publish-dlx], description: Overflow behavior; immutable after creation.}
  dead_letter_exchange: {type: str, description: Dead-letter exchange.}
  dead_letter_routing_key: {type: str, description: Dead-letter routing key.}
  single_active_consumer: {type: bool, description: Single-active-consumer flag; immutable after creation.}
  maximum_priority: {type: int, description: Classic queue maximum priority; immutable after creation.}
  lazy_mode: {type: bool, description: Classic lazy mode; immutable after creation.}
  master_locator: {type: str, choices: [min-masters, client-local, random], description: Classic master locator; immutable after creation.}
  max_in_memory_length: {type: int, description: Quorum in-memory message limit; immutable after creation.}
  max_in_memory_bytes: {type: int, description: Quorum in-memory byte limit; immutable after creation.}
  node: {type: str, description: Preferred queue node; immutable after creation.}
  dead_letter_strategy: {type: str, choices: [at-most-once, at-least-once], description: Quorum dead-letter strategy; immutable after creation.}
  queue_leader_locator: {type: str, choices: [client-local, balanced], description: Quorum leader locator; immutable after creation.}
  quorum_initial_group_size: {type: int, description: Initial quorum replica count; immutable after creation.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.trabbit_serverless_queue:
    instance_id: amqp-xxxxxxxx
    virtual_host: production
    name: order-workers
    queue_type: classic
    durable: true
    message_ttl: 86400000
    dead_letter_exchange: orders-dlx
"""
RETURN = r"""queue: {description: RabbitMQ Serverless queue metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.trabbit.v20230418 import models, trabbit_client

    return models, trabbit_client


def describe_request(models, p, offset=0):
    r = models.DescribeRabbitMQServerlessQueuesRequest()
    r.InstanceId, r.VirtualHost, r.SearchWord, r.Offset, r.Limit = p["instance_id"], p["virtual_host"], p["name"], offset, 100
    return r


def detail_request(models, p):
    r = models.DescribeRabbitMQServerlessQueueDetailRequest()
    r.InstanceId, r.VirtualHost, r.QueueName = p["instance_id"], p["virtual_host"], p["name"]
    return r


def create_request(models, p):
    r = models.CreateRabbitMQServerlessQueueRequest()
    r.InstanceId, r.VirtualHost, r.QueueName = p["instance_id"], p["virtual_host"], p["name"]
    r.QueueType = p.get("queue_type") or "classic"
    r.Durable = p["durable"] if p.get("durable") is not None else True
    r.AutoDelete = p["auto_delete"] if p.get("auto_delete") is not None else False
    for field, key in (
        ("Remark", "remark"),
        ("MessageTTL", "message_ttl"),
        ("AutoExpire", "auto_expire"),
        ("MaxLength", "max_length"),
        ("MaxLengthBytes", "max_length_bytes"),
        ("DeliveryLimit", "delivery_limit"),
        ("OverflowBehaviour", "overflow_behaviour"),
        ("DeadLetterExchange", "dead_letter_exchange"),
        ("DeadLetterRoutingKey", "dead_letter_routing_key"),
        ("SingleActiveConsumer", "single_active_consumer"),
        ("MaximumPriority", "maximum_priority"),
        ("LazyMode", "lazy_mode"),
        ("MasterLocator", "master_locator"),
        ("MaxInMemoryLength", "max_in_memory_length"),
        ("MaxInMemoryBytes", "max_in_memory_bytes"),
        ("Node", "node"),
        ("DeadLetterStrategy", "dead_letter_strategy"),
        ("QueueLeaderLocator", "queue_leader_locator"),
        ("QuorumInitialGroupSize", "quorum_initial_group_size"),
    ):
        setattr(r, field, p.get(key))
    return r


def update_request(models, p, current=None):
    current = current or {}
    r = models.ModifyRabbitMQServerlessQueueRequest()
    r.InstanceId, r.VirtualHost, r.QueueName = p["instance_id"], p["virtual_host"], p["name"]
    r.Remark = p["remark"]
    r.MessageTTL = p["message_ttl"] if p.get("message_ttl") is not None else current.get("MessageTTL")
    r.DeadLetterExchange = p["dead_letter_exchange"] if p.get("dead_letter_exchange") is not None else current.get("DeadLetterExchange")
    r.DeadLetterRoutingKey = p["dead_letter_routing_key"] if p.get("dead_letter_routing_key") is not None else current.get("DeadLetterRoutingKey")
    return r


def delete_request(models, p):
    r = models.DeleteRabbitMQServerlessQueueRequest()
    r.InstanceId, r.VirtualHost, r.QueueName = p["instance_id"], p["virtual_host"], p["name"]
    return r


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeRabbitMQServerlessQueues, describe_request(models, p))
    found = any(item.QueueName == p["name"] for item in response.QueueInfoList or [])
    if not found:
        return None
    value = module.sdk_call(client.DescribeRabbitMQServerlessQueueDetail, detail_request(models, p))._serialize(allow_none=True)
    value.pop("RequestId", None)
    return value


FIELDS = {
    "QueueName": "name",
    "VirtualHost": "virtual_host",
    "QueueType": "queue_type",
    "Durable": "durable",
    "AutoDelete": "auto_delete",
    "Remark": "remark",
    "MessageTTL": "message_ttl",
    "AutoExpire": "auto_expire",
    "MaxLength": "max_length",
    "MaxLengthBytes": "max_length_bytes",
    "DeliveryLimit": "delivery_limit",
    "OverflowBehaviour": "overflow_behaviour",
    "DeadLetterExchange": "dead_letter_exchange",
    "DeadLetterRoutingKey": "dead_letter_routing_key",
    "SingleActiveConsumer": "single_active_consumer",
    "MaximumPriority": "maximum_priority",
    "LazyMode": "lazy_mode",
    "MasterLocator": "master_locator",
    "MaxInMemoryLength": "max_in_memory_length",
    "MaxInMemoryBytes": "max_in_memory_bytes",
    "Node": "node",
    "DeadLetterStrategy": "dead_letter_strategy",
    "QueueLeaderLocator": "queue_leader_locator",
    "QuorumInitialGroupSize": "quorum_initial_group_size",
}
MUTABLE = ("Remark", "MessageTTL", "DeadLetterExchange", "DeadLetterRoutingKey")
IMMUTABLE = tuple(key for key in FIELDS if key not in MUTABLE and key not in ("QueueName", "VirtualHost"))


def comparable(value):
    result = {key: value.get(key) for key in FIELDS}
    result["Remark"] = result["Remark"] or ""
    return result


def desired(p, current=None):
    current = current or {}
    result = {key: p.get(param) if p.get(param) is not None else current.get(key) for key, param in FIELDS.items()}
    result["QueueName"], result["VirtualHost"], result["Remark"] = p["name"], p["virtual_host"], p["remark"]
    if not current:
        result["QueueType"], result["Durable"], result["AutoDelete"] = (
            p.get("queue_type") or "classic",
            p["durable"] if p.get("durable") is not None else True,
            p["auto_delete"] if p.get("auto_delete") is not None else False,
        )
    return result


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "instance_id": {"required": True},
        "virtual_host": {"required": True},
        "name": {"required": True},
        "queue_type": {"choices": ["classic", "quorum"]},
        "durable": {"type": "bool"},
        "auto_delete": {"type": "bool"},
        "remark": {"default": ""},
        "message_ttl": {"type": "int"},
        "auto_expire": {"type": "int"},
        "max_length": {"type": "int"},
        "max_length_bytes": {"type": "int"},
        "delivery_limit": {"type": "int"},
        "overflow_behaviour": {"choices": ["drop-head", "reject-publish", "reject-publish-dlx"]},
        "dead_letter_exchange": {},
        "dead_letter_routing_key": {"no_log": False},
        "single_active_consumer": {"type": "bool"},
        "maximum_priority": {"type": "int"},
        "lazy_mode": {"type": "bool"},
        "master_locator": {"choices": ["min-masters", "client-local", "random"]},
        "max_in_memory_length": {"type": "int"},
        "max_in_memory_bytes": {"type": "int"},
        "node": {},
        "dead_letter_strategy": {"choices": ["at-most-once", "at-least-once"]},
        "queue_leader_locator": {"choices": ["client-local", "balanced"]},
        "quorum_initial_group_size": {"type": "int"},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TrabbitClient, "trabbit.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, queue=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteRabbitMQServerlessQueue, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), queue=current if module.check_mode else None)
        before, target = comparable(current) if current else None, desired(p, current)
        if before == target:
            module.exit_json(changed=False, queue=current)
        if current:
            require_immutable_unchanged(module, before, target, IMMUTABLE, "RabbitMQ Serverless queue")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(
                client.ModifyRabbitMQServerlessQueue if current else client.CreateRabbitMQServerlessQueue,
                update_request(models, p, current) if current else create_request(models, p),
            )
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), queue=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
