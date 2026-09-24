#!/usr/bin/python
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: monitor_prometheus_alertmanager_config_info
short_description: Gather Managed Prometheus Alertmanager configuration
version_added: "1.4.0"
description: Reads the Alertmanager configuration of a Tencent Cloud Managed Prometheus instance.
options:
  instance_id: {description: Prometheus instance ID., type: str, required: true}
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
- susunola.tencentcloud.monitor_prometheus_alertmanager_config_info:
    region: ap-guangzhou
    instance_id: prom-xxxxxxxx
'''
RETURN = r'''
config: {description: Alertmanager configuration returned by the API., returned: always, type: dict}
request_id: {description: Request ID of the API call., returned: always, type: str}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def build_request(models, instance_id):
    request = models.DescribePrometheusAlertmanagerConfigRequest()
    request.InstanceId = instance_id
    return request


def run_module():
    module = TencentCloudModule(argument_spec={"instance_id": {"required": True}}, supports_check_mode=True)
    module.require_sdk()
    try:
        from tencentcloud.monitor.v20180724 import models, monitor_client
        client = module.create_client(monitor_client.MonitorClient, "monitor.tencentcloudapi.com")
        response = module.sdk_call(client.DescribePrometheusAlertmanagerConfig,
                                   build_request(models, module.params["instance_id"]))
        item = response.AlertmanagerConfig
        module.exit_json(changed=False, config=item._serialize(allow_none=True) if item else {},
                         request_id=getattr(response, "RequestId", None))
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
