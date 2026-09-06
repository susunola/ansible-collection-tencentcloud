#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: trabbit_serverless_exchange
short_description: Manage Tencent Cloud RabbitMQ Serverless exchanges
version_added: "0.14.0"
description: Creates, updates and deletes RabbitMQ Serverless exchanges while protecting immutable routing semantics.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: RabbitMQ Serverless instance ID.}
  virtual_host: {type: str, required: true, description: Virtual-host name.}
  name: {type: str, required: true, description: Exchange name.}
  exchange_type: {type: str, choices: [fanout, direct, topic, headers, x-delayed-message], description: Exchange type; defaults to direct during creation.}
  remark: {type: str, default: '', description: Exchange remark.}
  durable: {type: bool, description: Durable exchange flag; defaults to true during creation.}
  auto_delete: {type: bool, description: Automatic deletion flag; defaults to false during creation.}
  internal: {type: bool, description: Internal-only exchange flag; defaults to false during creation.}
  alternate_exchange: {type: str, default: '', description: Alternate exchange for unroutable messages.}
  delayed_exchange_type: {type: str, choices: [fanout, direct, topic, headers], description: Backing type for a delayed exchange.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.trabbit_serverless_exchange:
    instance_id: amqp-xxxxxxxx
    virtual_host: production
    name: orders
    exchange_type: topic
    durable: true
"""
RETURN = r"""exchange: {description: RabbitMQ Serverless exchange metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.trabbit.v20230418 import models, trabbit_client

    return models, trabbit_client


def describe_request(models, p, offset=0):
    r = models.DescribeRabbitMQServerlessExchangesRequest()
    r.InstanceId, r.VirtualHost, r.ExchangeName, r.Offset, r.Limit = p["instance_id"], p["virtual_host"], p["name"], offset, 100
    return r


def detail_request(models, p):
    r = models.DescribeRabbitMQServerlessExchangeDetailRequest()
    r.InstanceId, r.VirtualHost, r.ExchangeName = p["instance_id"], p["virtual_host"], p["name"]
    return r


def create_request(models, p):
    r = models.CreateRabbitMQServerlessExchangeRequest()
    r.InstanceId, r.VirtualHost, r.ExchangeName = p["instance_id"], p["virtual_host"], p["name"]
    r.ExchangeType = p.get("exchange_type") or "direct"
    r.Remark = p["remark"]
    r.Durable = p["durable"] if p.get("durable") is not None else True
    r.AutoDelete = p["auto_delete"] if p.get("auto_delete") is not None else False
    r.Internal = p["internal"] if p.get("internal") is not None else False
    r.AlternateExchange, r.DelayedExchangeType = p["alternate_exchange"], p.get("delayed_exchange_type")
    return r


def update_request(models, p):
    r = models.ModifyRabbitMQServerlessExchangeRequest()
    r.InstanceId, r.VirtualHost, r.ExchangeName = p["instance_id"], p["virtual_host"], p["name"]
    r.Remark, r.AlternateExchange = p["remark"], p["alternate_exchange"]
    return r


def delete_request(models, p):
    r = models.DeleteRabbitMQServerlessExchangeRequest()
    r.InstanceId, r.VirtualHost, r.ExchangeName = p["instance_id"], p["virtual_host"], p["name"]
    return r


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeRabbitMQServerlessExchanges, describe_request(models, p))
    found = any(item.ExchangeName == p["name"] for item in response.ExchangeInfoList or [])
    if not found:
        return None
    value = module.sdk_call(client.DescribeRabbitMQServerlessExchangeDetail, detail_request(models, p))._serialize(allow_none=True)
    value.pop("RequestId", None)
    return value


def comparable(value):
    return {
        "ExchangeName": value.get("ExchangeName"),
        "VirtualHost": value.get("VirtualHost"),
        "ExchangeType": value.get("ExchangeType"),
        "Remark": value.get("Remark") or "",
        "Durable": bool(value.get("Durable")),
        "AutoDelete": bool(value.get("AutoDelete")),
        "Internal": bool(value.get("Internal")),
        "AlternateExchange": value.get("AlternateExchange") or "",
    }


def desired(p, current=None):
    current = current or {}
    return {
        "ExchangeName": p["name"],
        "VirtualHost": p["virtual_host"],
        "ExchangeType": p.get("exchange_type") or current.get("ExchangeType") or "direct",
        "Remark": p["remark"],
        "Durable": p["durable"] if p.get("durable") is not None else current.get("Durable", True),
        "AutoDelete": p["auto_delete"] if p.get("auto_delete") is not None else current.get("AutoDelete", False),
        "Internal": p["internal"] if p.get("internal") is not None else current.get("Internal", False),
        "AlternateExchange": p["alternate_exchange"],
    }


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "instance_id": {"required": True},
        "virtual_host": {"required": True},
        "name": {"required": True},
        "exchange_type": {"choices": ["fanout", "direct", "topic", "headers", "x-delayed-message"]},
        "remark": {"default": ""},
        "durable": {"type": "bool"},
        "auto_delete": {"type": "bool"},
        "internal": {"type": "bool"},
        "alternate_exchange": {"default": ""},
        "delayed_exchange_type": {"choices": ["fanout", "direct", "topic", "headers"]},
    }
    module = TencentCloudModule(argument_spec=spec, required_if=[("exchange_type", "x-delayed-message", ["delayed_exchange_type"])], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TrabbitClient, "trabbit.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, exchange=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteRabbitMQServerlessExchange, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), exchange=current if module.check_mode else None)
        before, target = comparable(current) if current else None, desired(p, current)
        if before == target:
            module.exit_json(changed=False, exchange=current)
        if current:
            require_immutable_unchanged(module, before, target, ("ExchangeType", "Durable", "AutoDelete", "Internal"), "RabbitMQ Serverless exchange")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(
                client.ModifyRabbitMQServerlessExchange if current else client.CreateRabbitMQServerlessExchange,
                update_request(models, p) if current else create_request(models, p),
            )
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), exchange=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
