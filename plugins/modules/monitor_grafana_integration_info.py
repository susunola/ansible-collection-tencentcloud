#!/usr/bin/python
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: monitor_grafana_integration_info
short_description: Gather installed Managed Grafana integrations
version_added: "1.4.0"
description: Reads integrations installed in a Tencent Cloud Managed Grafana instance.
options:
  instance_id:
    description:
      - Grafana instance ID.
    type: str
    required: true
  integration_id:
    description:
      - Exact integration ID.
    type: str
  kind:
    description:
      - Exact integration type code.
    type: str
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
      - 'Can run in C(check_mode): the module reads the current state and
        predicts the result without issuing a write API call.'
    support: full
  idempotency:
    description:
      - 'Read-only: every run returns the current state and never changes
        the target, so a repeated run reports C(changed=false).'
    support: full
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.monitor_grafana_integration_info:
    region: ap-guangzhou
    instance_id: grafana-xxxxxxxx
'''
RETURN = r'''
integrations: {description: Matching integrations., returned: always, type: list, elements: dict}
integration: {description: Single integration when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID of the API call., returned: always, type: str}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def build_request(models, params):
    request = models.DescribeGrafanaIntegrationsRequest()
    request.InstanceId = params["instance_id"]
    request.IntegrationId = params.get("integration_id")
    request.Kind = params.get("kind") if not params.get("integration_id") else None
    return request


def matches(value, params):
    return all((
        not params.get("integration_id") or value.get("IntegrationId") == params["integration_id"],
        not params.get("kind") or value.get("Kind") == params["kind"],
    ))


def run_module():
    module = TencentCloudModule(argument_spec={
        "instance_id": {"required": True}, "integration_id": {}, "kind": {},
    }, supports_check_mode=True)
    params = module.params
    module.require_sdk()
    try:
        from tencentcloud.monitor.v20180724 import models, monitor_client
        client = module.create_client(monitor_client.MonitorClient, "monitor.tencentcloudapi.com")
        response = module.sdk_call(client.DescribeGrafanaIntegrations, build_request(models, params))
        values = [value for value in
                  (item._serialize(allow_none=True) for item in (response.IntegrationSet or []))
                  if matches(value, params)]
        module.exit_json(changed=False, integrations=values,
                         integration=values[0] if len(values) == 1 else None,
                         request_id=getattr(response, "RequestId", None))
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
