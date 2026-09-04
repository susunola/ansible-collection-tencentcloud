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
  instance_id: {type: str, required: true, description: Grafana instance ID.}
  enabled: {type: bool, default: false, description: Desired internet-access state.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.monitor_grafana_internet:
    instance_id: grafana-xxxxxxxx
    enabled: true
"""
RETURN = r"""enabled: {description: Effective internet-access state., type: bool, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


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


def run_module():
    module = TencentCloudModule(argument_spec={"instance_id": {"required": True}, "enabled": {"type": "bool", "default": False}}, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.MonitorClient, "monitor.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeGrafanaInstances, build_describe(models, p["instance_id"]))
        items = list(response.InstanceSet or response.Instances or [])
        current = bool(items and items[0].InternetUrl)
        target = p["enabled"]
        if current == target:
            module.exit_json(changed=False, enabled=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.EnableGrafanaInternet, build_update(models, p["instance_id"], target))
        module.exit_json(changed=True, **(diff or {}), enabled=target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
