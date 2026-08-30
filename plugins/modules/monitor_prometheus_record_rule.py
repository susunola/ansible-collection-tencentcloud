#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: monitor_prometheus_record_rule
short_description: Manage Tencent Cloud Managed Prometheus recording rules
version_added: "0.14.0"
description: Creates, updates and deletes a named Prometheus recording-rule YAML document.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: Prometheus instance ID.}
  name: {type: str, required: true, description: Recording-rule document name.}
  content: {type: str, description: Prometheus recording-rule YAML.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.monitor_prometheus_record_rule:
    instance_id: prom-xxxxxxxx
    name: application-rollups
    content: |-
      groups:
        - name: application
          rules:
            - record: job:http_requests:rate5m
              expr: sum by (job) (rate(http_requests_total[5m]))
'''
RETURN = r'''record_rule: {description: Prometheus recording-rule metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.monitor.v20180724 import models, monitor_client
    return models, monitor_client
def build_describe(models, instance_id, name):
    request = models.DescribePrometheusRecordRulesRequest(); request.InstanceId, request.Offset, request.Limit = instance_id, 0, 100
    item = models.Filter(); item.Name, item.Values = "Name", [name]; request.Filters = [item]; return request
def build_create(models, p): request = models.CreatePrometheusRecordRuleYamlRequest(); request.InstanceId, request.Name, request.Content = p["instance_id"], p["name"], p["content"]; return request
def build_update(models, p): request = models.ModifyPrometheusRecordRuleYamlRequest(); request.InstanceId, request.Name, request.Content = p["instance_id"], p["name"], p["content"]; return request
def build_delete(models, p): request = models.DeletePrometheusRecordRuleYamlRequest(); request.InstanceId, request.Names = p["instance_id"], [p["name"]]; return request


def find(module, client, models, p):
    response = module.sdk_call(client.DescribePrometheusRecordRules, build_describe(models, p["instance_id"], p["name"])); matches = [x._serialize(allow_none=True) for x in list(response.Records or []) if x.Name == p["name"]]
    if len(matches) > 1: module.fail_json(msg="Multiple Prometheus record rules have the requested name", name=p["name"])
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True}, "name": {"required": True}, "content": {}}, required_if=[("state", "present", ["content"])], supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.MonitorClient, "monitor.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, record_rule=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeletePrometheusRecordRuleYaml, build_delete(models, p))
            module.exit_json(changed=True, **(diff or {}), record_rule=current if module.check_mode else None)
        target = {"Name": p["name"], "Content": p["content"]}; before = {"Name": current.get("Name"), "Content": current.get("Content")} if current else None
        if before == target: module.exit_json(changed=False, record_rule=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode: module.sdk_call(client.ModifyPrometheusRecordRuleYaml if current else client.CreatePrometheusRecordRuleYaml, build_update(models, p) if current else build_create(models, p)); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), record_rule=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
