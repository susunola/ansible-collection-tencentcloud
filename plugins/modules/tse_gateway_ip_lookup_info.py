#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tse_gateway_ip_lookup_info
short_description: Resolve a Tencent Cloud TSE gateway from its public IP
version_added: "0.14.0"
description: Returns cloud-native API gateway instance information associated with a public network IP.
options:
  public_ip:
    description:
      - Public IP assigned to a cloud-native API gateway.
    type: str
    required: true
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
  idempotency:
    description:
      - Read-only, so every run returns the current state and never changes
        the target, and a repeated run reports C(changed=false).
    support: full
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tse_gateway_ip_lookup_info:
    public_ip: 203.0.113.10
  register: gateway_lookup
'''
RETURN = r'''
gateway_info: {description: Gateway instance information associated with the IP., type: dict, returned: always}
request_id: {description: Tencent Cloud request ID., type: str, returned: always}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client
    return models, tse_client


def request(models, public_ip):
    value = models.DescribeCloudNativeAPIGatewayInfoByIpRequest()
    value.PublicNetworkIP = public_ip
    return value


def run_module():
    module = TencentCloudModule(argument_spec={"public_ip": {"required": True}}, supports_check_mode=True)
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.TseClient, "tse.tencentcloudapi.com")
    try:
        response = module.sdk_call(
            client.DescribeCloudNativeAPIGatewayInfoByIp, request(models, module.params["public_ip"])
        )
        result = response.Result._serialize(allow_none=True) if response.Result else {}
        module.exit_json(changed=False, gateway_info=result, request_id=response.RequestId)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
