#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: monitor_prometheus_global_notification
short_description: Manage Managed Prometheus global notification settings
version_added: "0.14.0"
description:
  - Reconciles the singleton global notification configuration of a Prometheus instance.
  - The underlying Describe/ModifyPrometheusGlobalNotification APIs were marked
    by Tencent Cloud for retirement on 2026-05-25. This module is retained for
    compatibility; prefer Prometheus alert groups and receivers for new
    configurations. If the API is unavailable, the module fails rather than
    claiming convergence.
options:
  instance_id:
    description:
      - Prometheus instance ID.
    type: str
    required: true
  notification:
    description:
      - SDK-compatible PrometheusNotificationItem configuration.
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
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.monitor_prometheus_global_notification:
    instance_id: prom-xxxxxxxx
    notification: {Enabled: true, Type: amp, RepeatInterval: 1h, ReceiverGroups: [notice-xxxxxxxx]}
"""
RETURN = r"""notification:
  description:
    - Effective global notification configuration.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    Enabled: false
    Type: amp
    RepeatInterval: 30m
    ReceiverGroups:
      - notice-abc123
"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.monitor.v20180724 import models, monitor_client

    return models, monitor_client


def build_describe(models, iid):
    request = models.DescribePrometheusGlobalNotificationRequest()
    request.InstanceId = iid
    return request


def build_update(models, iid, value):
    request = models.ModifyPrometheusGlobalNotificationRequest()
    request.InstanceId = iid
    item = models.PrometheusNotificationItem()
    item._deserialize(value)
    request.Notification = item
    return request


def run_module():
    module = TencentCloudModule(argument_spec={"instance_id": {"required": True}, "notification": {"type": "dict", "required": True}}, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.MonitorClient, "monitor.tencentcloudapi.com")
    try:
        item = module.sdk_call(client.DescribePrometheusGlobalNotification, build_describe(models, p["instance_id"])).Notification
        current = item._serialize(allow_none=True) if item else {}
        target = p["notification"]
        if current == target:
            module.exit_json(changed=False, notification=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyPrometheusGlobalNotification, build_update(models, p["instance_id"], target))
        module.exit_json(changed=True, **(diff or {}), notification=target)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
