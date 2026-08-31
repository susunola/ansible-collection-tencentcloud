#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tse_gateway_ip_lookup_info
short_description: Resolve a Tencent Cloud TSE gateway from its public IP
version_added: "0.14.0"
description: Returns cloud-native API gateway instance information associated with a public network IP.
options:
  public_ip: {type: str, required: true, description: Public IP assigned to a cloud-native API gateway.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
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
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


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
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
