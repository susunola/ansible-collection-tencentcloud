#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: monitor_grafana_whitelist
short_description: Manage a Tencent Cloud Managed Grafana IP whitelist
version_added: "0.14.0"
description: Reconciles the complete internet-access IP whitelist of a Grafana instance.
options:
  instance_id:
    description:
      - Grafana instance ID.
    type: str
    required: true
  addresses:
    description:
      - Exact IP address and CIDR whitelist.
    type: list
    default: []
    elements: str

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
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.monitor_grafana_whitelist:
    instance_id: grafana-xxxxxxxx
    addresses: [203.0.113.10/32]
"""
RETURN = r"""whitelist: {description: Effective whitelist., type: list, elements: str, returned: always}"""
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.monitor.v20180724 import models, monitor_client

    return models, monitor_client


def build_describe(models, iid):
    request = models.DescribeGrafanaWhiteListRequest()
    request.InstanceId = iid
    return request


def build_update(models, iid, values):
    request = models.UpdateGrafanaWhiteListRequest()
    request.InstanceId, request.Whitelist = iid, sorted(values)
    return request


def read_whitelist(module, client, models, instance_id):
    response = module.sdk_call(client.DescribeGrafanaWhiteList, build_describe(models, instance_id))
    return sorted(response.WhiteList or [])


def wait_for_whitelist(module, client, models, instance_id, target):
    deadline = time.monotonic() + module.params["waiter_timeout"]
    while True:
        current = read_whitelist(module, client, models, instance_id)
        if current == target:
            return current
        if time.monotonic() >= deadline:
            module.fail_json(msg="Timed out waiting for Grafana whitelist convergence",
                             instance_id=instance_id, whitelist=current, expected=target)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={"instance_id": {"required": True}, "addresses": {"type": "list", "elements": "str", "default": []}}, supports_check_mode=True
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.MonitorClient, "monitor.tencentcloudapi.com")
    try:
        current = read_whitelist(module, client, models, p["instance_id"])
        target = sorted(p["addresses"])
        if current == target:
            module.exit_json(changed=False, whitelist=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.UpdateGrafanaWhiteList, build_update(models, p["instance_id"], target))
            target = wait_for_whitelist(module, client, models, p["instance_id"], target)
        module.exit_json(changed=True, **(diff or {}), whitelist=target)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
