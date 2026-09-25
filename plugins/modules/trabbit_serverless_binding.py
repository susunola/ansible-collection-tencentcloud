#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: trabbit_serverless_binding
short_description: Manage Tencent Cloud RabbitMQ Serverless bindings
version_added: "0.14.0"
description: Creates and deletes immutable exchange-to-queue or exchange-to-exchange bindings.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  instance_id:
    description:
      - RabbitMQ Serverless instance ID.
    type: str
    required: true
  virtual_host:
    description:
      - Virtual-host name.
    type: str
    required: true
  binding_id:
    description:
      - Existing binding ID.
    type: int
  source_exchange:
    description:
      - Source exchange name.
    type: str
    required: true
  destination_type:
    description:
      - Kind of destination the binding routes to.
    type: str
    required: true
    choices: [queue, exchange]
  destination:
    description:
      - Destination queue or exchange.
    type: str
    required: true
  routing_key:
    description:
      - Routing key that selects this binding.
    type: str
    default: ''

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
  - module: susunola.tencentcloud.trabbit_serverless_binding_info
    description: Gather information about Tencent Cloud TRABBIT serverless bindings.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.trabbit_serverless_binding:
    instance_id: amqp-xxxxxxxx
    virtual_host: production
    source_exchange: orders
    destination_type: queue
    destination: order-workers
    routing_key: orders.created

- name: Delete the binding
  susunola.tencentcloud.trabbit_serverless_binding:
    state: absent
    destination: order-workers
    destination_type: queue
    instance_id: amqp-xxxxxxxx
    source_exchange: orders
    virtual_host: production
"""
RETURN = r"""binding:
  description:
    - RabbitMQ Serverless binding metadata.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    BindingId: 501
    InstanceId: amqp-abc123
    VirtualHost: production
    Source: orders
    DestinationType: queue
    Destination: order-workers
    RoutingKey: orders.created
"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.trabbit.v20230418 import models, trabbit_client

    return models, trabbit_client


def describe_request(models, p, offset=0):
    r = models.DescribeRabbitMQServerlessBindingsRequest()
    r.InstanceId, r.VirtualHost, r.Offset, r.Limit, r.SourceExchange = p["instance_id"], p["virtual_host"], offset, 100, p["source_exchange"]
    if p["destination_type"] == "queue":
        r.QueueName = p["destination"]
    else:
        r.DestinationExchange = p["destination"]
    return r


def create_request(models, p):
    r = models.CreateRabbitMQServerlessBindingRequest()
    r.InstanceId, r.VirtualHost, r.Source = p["instance_id"], p["virtual_host"], p["source_exchange"]
    r.DestinationType, r.Destination, r.RoutingKey = p["destination_type"], p["destination"], p["routing_key"]
    return r


def delete_request(models, p, binding_id):
    r = models.DeleteRabbitMQServerlessBindingRequest()
    r.InstanceId, r.VirtualHost, r.BindingId = p["instance_id"], p["virtual_host"], binding_id
    return r


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeRabbitMQServerlessBindings, describe_request(models, p, offset))
        items = list(response.BindingInfoList or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if p.get("binding_id") and int(value.get("BindingId") or 0) == p["binding_id"]:
                return value
            if (
                not p.get("binding_id")
                and value.get("Source") == p["source_exchange"]
                and value.get("DestinationType") == p["destination_type"]
                and value.get("Destination") == p["destination"]
                and (value.get("RoutingKey") or "") == p["routing_key"]
            ):
                return value
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0):
            return None


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "instance_id": {"required": True},
        "virtual_host": {"required": True},
        "binding_id": {"type": "int"},
        "source_exchange": {"required": True},
        "destination_type": {"choices": ["queue", "exchange"], "required": True},
        "destination": {"required": True},
        "routing_key": {"default": "", "no_log": False},
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
                module.exit_json(changed=False, binding=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteRabbitMQServerlessBinding, delete_request(models, p, current["BindingId"]))
            module.exit_json(changed=True, **(diff or {}), binding=current if module.check_mode else None)
        if current:
            module.exit_json(changed=False, binding=current)
        target = {"Source": p["source_exchange"], "DestinationType": p["destination_type"], "Destination": p["destination"], "RoutingKey": p["routing_key"]}
        diff = maybe_diff(module, None, target)
        if not module.check_mode:
            module.sdk_call(client.CreateRabbitMQServerlessBinding, create_request(models, p))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), binding=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
