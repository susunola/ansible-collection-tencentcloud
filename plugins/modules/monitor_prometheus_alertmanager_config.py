#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: monitor_prometheus_alertmanager_config
short_description: Manage Managed Prometheus Alertmanager configuration
version_added: "0.14.0"
description: Replaces the singleton Alertmanager configuration of a Prometheus instance.
options:
  instance_id:
    description:
      - Prometheus instance ID.
    type: str
    required: true
  config:
    description:
      - SDK-compatible PrometheusAlertmanagerConfigV2 configuration.
    type: dict
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
  - module: susunola.tencentcloud.monitor_prometheus_alertmanager_config_info
    description: Gather Managed Prometheus Alertmanager configuration.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.monitor_prometheus_alertmanager_config:
    instance_id: prom-xxxxxxxx
    config: {InhibitRules: []}
"""
RETURN = r"""config:
  description:
    - Effective Alertmanager configuration.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    InhibitRules: []
    Receivers:
      - Name: pager
        WebhookConfigs:
          - Url: https://hooks.example.com/1
"""
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.monitor.v20180724 import models, monitor_client

    return models, monitor_client


def build_describe(models, iid):
    request = models.DescribePrometheusAlertmanagerConfigRequest()
    request.InstanceId = iid
    return request


def build_update(models, iid, value):
    request = models.ReplacePrometheusAlertmanagerConfigRequest()
    request.InstanceId = iid
    item = models.PrometheusAlertmanagerConfigV2()
    item._deserialize(value)
    request.AlertmanagerConfig = item
    return request


def read_config(module, client, models, instance_id):
    item = module.sdk_call(client.DescribePrometheusAlertmanagerConfig,
                           build_describe(models, instance_id)).AlertmanagerConfig
    return item._serialize(allow_none=True) if item else {}


def wait_for_config(module, client, models, instance_id, target):
    deadline = time.monotonic() + module.params["waiter_timeout"]
    while True:
        current = read_config(module, client, models, instance_id)
        if current == target:
            return current
        if time.monotonic() >= deadline:
            module.fail_json(msg="Timed out waiting for Alertmanager config convergence",
                             instance_id=instance_id, config=current, expected=target)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={"instance_id": {"required": True}, "config": {"type": "dict", "required": True}}, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.MonitorClient, "monitor.tencentcloudapi.com")
    try:
        current = read_config(module, client, models, p["instance_id"])
        target = p["config"]
        if current == target:
            module.exit_json(changed=False, config=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.ReplacePrometheusAlertmanagerConfig, build_update(models, p["instance_id"], target))
            target = wait_for_config(module, client, models, p["instance_id"], target)
        module.exit_json(changed=True, **(diff or {}), config=target)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
