#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: apigateway_ip_strategy
short_description: Create or delete a Tencent Cloud API Gateway IP strategy
version_added: "1.1.0"
description:
  - Creates or deletes a Tencent Cloud API Gateway (API GW) IP access strategy,
    identified by its service and strategy name. The module is idempotent; it
    lists the service's IP strategies (filtered by name) before changing
    anything and matches on the C(ServiceId) + C(StrategyName) pair.
  - The strategy data is a newline-separated IP list passed as a plain string,
    set directly on the C(CreateIPStrategyRequest) object.
options:
  state:
    description: Desired state of the IP strategy.
    type: str
    choices: [present, absent]
    default: present
  service_id:
    description: Unique service ID the IP strategy belongs to.
    type: str
    required: true
  strategy_name:
    description: User-defined strategy name.
    type: str
    required: true
  strategy_type:
    description: Strategy type. C(WHITE) - allowlist, C(BLACK) - blocklist.
    type: str
    choices: [WHITE, BLACK]
  strategy_data:
    description: Strategy detail, multiple IPs separated by newlines.
    type: str
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a whitelist IP strategy on a service
  susunola.tencentcloud.apigateway_ip_strategy:
    service_id: service-abc
    strategy_name: allow-office
    strategy_type: WHITE
    strategy_data: "10.0.0.0/8\n192.168.1.0/24"

- name: Remove the IP strategy
  susunola.tencentcloud.apigateway_ip_strategy:
    service_id: service-abc
    strategy_name: allow-office
    state: absent
'''

RETURN = r'''
service_id:
  description: Service ID the operation targeted.
  returned: always
  type: str
strategy_name:
  description: Strategy name the operation targeted.
  returned: always
  type: str
strategy_id:
  description: Server-assigned strategy ID after a create, or the matched strategy ID.
  returned: always
  type: str
exists:
  description: Whether the IP strategy exists after the operation.
  returned: always
  type: bool
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def _load():
    from tencentcloud.apigateway.v20180808 import apigateway_client, models
    return models, apigateway_client


def find_strategy(module, client, models, service_id, name):
    request = models.DescribeIPStrategysStatusRequest()
    request.ServiceId = service_id
    flt = models.Filter()
    flt.Key = "StrategyName"
    flt.Values = [name]
    request.Filters = [flt]
    request.Limit = 100
    request.Offset = 0
    response = module.sdk_call(client.DescribeIPStrategysStatus, request)
    summary = getattr(response, "Result", None)
    strategies = list(getattr(summary, "StrategySet", None) or [])
    for item in strategies:
        if getattr(item, "StrategyName", None) == name and getattr(item, "ServiceId", None) == service_id:
            return item
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "service_id": {"type": "str", "required": True},
            "strategy_name": {"type": "str", "required": True},
            "strategy_type": {"type": "str", "choices": ["WHITE", "BLACK"]},
            "strategy_data": {"type": "str"},
        },
        required_if=[("state", "present", ("strategy_type", "strategy_data"))],
        supports_check_mode=True,
    )
    p = module.params
    service_id = p["service_id"]
    name = p["strategy_name"]
    desired_present = p["state"] == "present"
    module.require_sdk()
    models, apigateway_client = _load()
    client = module.create_client(apigateway_client.ApigatewayClient, "apigateway.tencentcloudapi.com")
    try:
        current = find_strategy(module, client, models, service_id, name)
        if bool(current) == desired_present:
            module.exit_json(
                changed=False,
                service_id=service_id,
                strategy_name=name,
                strategy_id=getattr(current, "StrategyId", None),
                exists=bool(current),
                msg="API GW IP strategy already %s" % ("present" if desired_present else "absent"),
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                service_id=service_id,
                strategy_name=name,
                strategy_id=None,
                exists=desired_present,
                msg="Would %s API GW IP strategy" % ("create" if desired_present else "delete"),
            )
        if desired_present:
            request = models.CreateIPStrategyRequest()
            request.ServiceId = service_id
            request.StrategyName = name
            request.StrategyType = p["strategy_type"]
            request.StrategyData = p["strategy_data"]
            response = module.sdk_call(client.CreateIPStrategy, request)
            created_id = getattr(getattr(response, "Result", None), "StrategyId", None)
        else:
            request = models.DeleteIPStrategyRequest()
            request.ServiceId = service_id
            request.StrategyId = getattr(current, "StrategyId", None)
            module.sdk_call(client.DeleteIPStrategy, request)
            created_id = None
        final = find_strategy(module, client, models, service_id, name)
        module.exit_json(
            changed=True,
            service_id=service_id,
            strategy_name=name,
            strategy_id=created_id if desired_present else (getattr(final, "StrategyId", None) if final else None),
            exists=bool(final),
            msg="API GW IP strategy %s" % ("created" if desired_present else "deleted"),
        )
    except Exception as exc:
        module.fail_sdk_error(exc, "Tencent Cloud API GW IP strategy request failed")


def main():
    run_module()


if __name__ == "__main__":
    main()
