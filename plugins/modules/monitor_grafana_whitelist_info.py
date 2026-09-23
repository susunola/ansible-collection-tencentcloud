#!/usr/bin/python
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: monitor_grafana_whitelist_info
short_description: Gather a Managed Grafana IP whitelist
version_added: "1.4.0"
description: Reads the complete internet-access whitelist of a Tencent Cloud Managed Grafana instance.
options:
  instance_id: {description: Grafana instance ID., type: str, required: true}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.monitor_grafana_whitelist_info:
    region: ap-guangzhou
    instance_id: grafana-xxxxxxxx
'''
RETURN = r'''
whitelist: {description: IP addresses and CIDR ranges in the whitelist., returned: always, type: list, elements: str}
request_id: {description: Request ID of the API call., returned: always, type: str}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def build_request(models, instance_id):
    request = models.DescribeGrafanaWhiteListRequest()
    request.InstanceId = instance_id
    return request


def run_module():
    module = TencentCloudModule(argument_spec={"instance_id": {"required": True}}, supports_check_mode=True)
    module.require_sdk()
    try:
        from tencentcloud.monitor.v20180724 import models, monitor_client
        client = module.create_client(monitor_client.MonitorClient, "monitor.tencentcloudapi.com")
        response = module.sdk_call(client.DescribeGrafanaWhiteList,
                                   build_request(models, module.params["instance_id"]))
        module.exit_json(changed=False, whitelist=sorted(response.WhiteList or []),
                         request_id=getattr(response, "RequestId", None))
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
