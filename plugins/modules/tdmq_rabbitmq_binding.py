#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: tdmq_rabbitmq_binding
short_description: Manage TDMQ RabbitMQ bindings
version_added: "0.14.0"
description: Creates and deletes immutable exchange-to-queue or exchange-to-exchange bindings.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: TDMQ RabbitMQ instance ID.}
  virtual_host: {type: str, required: true, description: Virtual host name.}
  binding_id: {type: int, description: Existing binding ID.}
  source_exchange: {type: str, required: true, description: Source exchange name.}
  destination_type: {type: str, choices: [queue, exchange], required: true, description: Destination resource type.}
  destination: {type: str, required: true, description: Destination queue or exchange name.}
  routing_key: {type: str, default: '', description: Binding routing key.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tdmq_rabbitmq_binding:
    instance_id: amqp-xxxxxxxx
    virtual_host: production
    source_exchange: orders
    destination_type: queue
    destination: order-workers
    routing_key: orders.created
'''
RETURN = r'''binding: {description: RabbitMQ binding metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tdmq.v20200217 import models, tdmq_client
    return models, tdmq_client


def describe_request(models, p, offset=0):
    request = models.DescribeRabbitMQBindingsRequest(); request.InstanceId, request.VirtualHost = p["instance_id"], p["virtual_host"]
    request.Offset, request.Limit, request.SourceExchange = offset, 100, p["source_exchange"]
    if p["destination_type"] == "queue": request.QueueName = p["destination"]
    else: request.DestinationExchange = p["destination"]
    return request


def create_request(models, p):
    request = models.CreateRabbitMQBindingRequest(); request.InstanceId, request.VirtualHost = p["instance_id"], p["virtual_host"]
    request.Source, request.DestinationType, request.Destination, request.RoutingKey = p["source_exchange"], p["destination_type"], p["destination"], p["routing_key"]; return request


def delete_request(models, p, binding_id):
    request = models.DeleteRabbitMQBindingRequest(); request.InstanceId, request.VirtualHost, request.BindingId = p["instance_id"], p["virtual_host"], binding_id; return request


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeRabbitMQBindings, describe_request(models, p, offset)); items = list(response.BindingInfoList or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if p.get("binding_id") and int(value.get("BindingId") or 0) == p["binding_id"]: return value
            if not p.get("binding_id") and value.get("Source") == p["source_exchange"] and value.get("DestinationType") == p["destination_type"] and value.get("Destination") == p["destination"] and (value.get("RoutingKey") or "") == p["routing_key"]: return value
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0): return None


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True}, "virtual_host": {"required": True}, "binding_id": {"type": "int"}, "source_exchange": {"required": True}, "destination_type": {"choices": ["queue", "exchange"], "required": True}, "destination": {"required": True}, "routing_key": {"default": "", "no_log": False}}, supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TdmqClient, "tdmq.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, binding=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteRabbitMQBinding, delete_request(models, p, current["BindingId"]))
            module.exit_json(changed=True, **(diff or {}), binding=current if module.check_mode else None)
        if current: module.exit_json(changed=False, binding=current)
        target = {"Source": p["source_exchange"], "DestinationType": p["destination_type"], "Destination": p["destination"], "RoutingKey": p["routing_key"]}; diff = maybe_diff(module, None, target)
        if not module.check_mode: module.sdk_call(client.CreateRabbitMQBinding, create_request(models, p)); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), binding=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
