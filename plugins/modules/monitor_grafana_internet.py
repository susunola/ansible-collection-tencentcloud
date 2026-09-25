#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: monitor_grafana_internet
short_description: Manage internet access for Tencent Cloud Managed Grafana
version_added: "0.14.0"
description: Enables or disables internet access on a Grafana instance.
options:
  instance_id:
    description:
      - Grafana instance ID.
    type: str
    required: true
  enabled:
    description:
      - Desired internet-access state.
    type: bool
    default: false

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
- susunola.tencentcloud.monitor_grafana_internet:
    instance_id: grafana-xxxxxxxx
    enabled: true
"""
RETURN = r"""enabled: {description: Effective internet-access state., type: bool, returned: always}"""
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.monitor.v20180724 import models, monitor_client

    return models, monitor_client


def build_describe(models, iid):
    request = models.DescribeGrafanaInstancesRequest()
    request.InstanceIds = [iid]
    request.Offset, request.Limit = 0, 1
    return request


def build_update(models, iid, enabled):
    request = models.EnableGrafanaInternetRequest()
    request.InstanceID, request.EnableInternet = iid, enabled
    return request


def read_internet_state(module, client, models, instance_id):
    response = module.sdk_call(client.DescribeGrafanaInstances, build_describe(models, instance_id))
    items = list(getattr(response, "Instances", None) or getattr(response, "InstanceSet", None) or [])
    matching = [item for item in items if item.InstanceId == instance_id]
    if not matching:
        module.fail_json(msg="Grafana instance was not found", instance_id=instance_id)
    return bool(matching[0].InternetUrl)


def wait_for_internet_state(module, client, models, instance_id, target):
    deadline = time.monotonic() + module.params["waiter_timeout"]
    while True:
        current = read_internet_state(module, client, models, instance_id)
        if current == target:
            return current
        if time.monotonic() >= deadline:
            module.fail_json(msg="Timed out waiting for Grafana internet access convergence",
                             instance_id=instance_id, enabled=current, expected=target)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={"instance_id": {"required": True}, "enabled": {"type": "bool", "default": False}}, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.MonitorClient, "monitor.tencentcloudapi.com")
    try:
        current = read_internet_state(module, client, models, p["instance_id"])
        target = p["enabled"]
        if current == target:
            module.exit_json(changed=False, enabled=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.EnableGrafanaInternet, build_update(models, p["instance_id"], target))
            target = wait_for_internet_state(module, client, models, p["instance_id"], target)
        module.exit_json(changed=True, **(diff or {}), enabled=target)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
