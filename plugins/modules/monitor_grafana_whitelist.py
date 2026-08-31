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
  instance_id: {type: str, required: true, description: Grafana instance ID.}
  addresses: {type: list, elements: str, default: [], description: Exact IP address and CIDR whitelist.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.monitor_grafana_whitelist:
    instance_id: grafana-xxxxxxxx
    addresses: [203.0.113.10/32]
"""
RETURN = r"""whitelist: {description: Effective whitelist., type: list, elements: str, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


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


def run_module():
    module = TencentCloudModule(
        argument_spec={"instance_id": {"required": True}, "addresses": {"type": "list", "elements": "str", "default": []}}, supports_check_mode=True
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.MonitorClient, "monitor.tencentcloudapi.com")
    try:
        current = sorted(module.sdk_call(client.DescribeGrafanaWhiteList, build_describe(models, p["instance_id"])).WhiteList or [])
        target = sorted(p["addresses"])
        if current == target:
            module.exit_json(changed=False, whitelist=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.UpdateGrafanaWhiteList, build_update(models, p["instance_id"], target))
        module.exit_json(changed=True, **(diff or {}), whitelist=target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
