#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: monitor_prometheus_instance
short_description: Manage Tencent Cloud pay-as-you-go Managed Prometheus instances
version_added: "0.14.0"
description: Creates, updates and terminates a pay-as-you-go Managed Prometheus instance.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, description: Existing instance ID.}
  name: {type: str, description: Instance name.}
  vpc_id: {type: str, description: VPC ID used at creation.}
  subnet_id: {type: str, description: Subnet ID used at creation.}
  zone: {type: str, description: Availability zone used at creation.}
  retention_days: {type: int, choices: [15, 30, 45, 90, 180, 365, 730], default: 15, description: Data retention period.}
  grafana_instance_id: {type: str, description: Managed Grafana instance to associate at creation.}
  tags: {type: dict, default: {}, description: Instance tags.}
  instance_attributes: {type: dict, default: {}, description: Additional instance attributes.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.monitor_prometheus_instance:
    name: production-observability
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    zone: ap-guangzhou-3
    retention_days: 30
"""
RETURN = r"""instance: {description: Managed Prometheus instance metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.monitor.v20180724 import models, monitor_client

    return models, monitor_client


def _tags(models, values):
    result = []
    for k, v in sorted(values.items()):
        x = models.PrometheusTag()
        x.Key, x.Value = str(k), str(v)
        result.append(x)
    return result


def _attrs(models, values):
    result = []
    for k, v in sorted(values.items()):
        x = models.PrometheusRuleKV()
        x.Key, x.Value = str(k), str(v)
        result.append(x)
    return result


def build_describe(models, instance_id=None, name=None):
    request = models.DescribePrometheusInstancesRequest()
    request.InstanceIds = [instance_id] if instance_id else None
    request.InstanceName = name
    request.Offset, request.Limit = 0, 100
    return request


def build_create(models, p):
    request = models.CreatePrometheusMultiTenantInstancePostPayModeRequest()
    request.InstanceName, request.VpcId, request.SubnetId, request.Zone = p["name"], p["vpc_id"], p["subnet_id"], p["zone"]
    request.DataRetentionTime = p["retention_days"]
    request.GrafanaInstanceId = p.get("grafana_instance_id")
    request.TagSpecification = _tags(models, p["tags"])
    request.InstanceAttributes = _attrs(models, p["instance_attributes"])
    return request


def build_update(models, p, instance_id):
    request = models.ModifyPrometheusInstanceAttributesRequest()
    request.InstanceId, request.InstanceName, request.DataRetentionTime = instance_id, p["name"], p["retention_days"]
    request.InstanceAttributes = _attrs(models, p["instance_attributes"])
    return request


def build_delete(models, instance_id):
    request = models.TerminatePrometheusInstancesRequest()
    request.InstanceIds = [instance_id]
    return request


def find(module, client, models, instance_id, name):
    response = module.sdk_call(client.DescribePrometheusInstances, build_describe(models, instance_id, name))
    matches = [
        x._serialize(allow_none=True)
        for x in list(response.InstanceSet or [])
        if (instance_id and x.InstanceId == instance_id) or (not instance_id and x.InstanceName == name)
    ]
    if len(matches) > 1:
        module.fail_json(msg="Multiple Prometheus instances have the requested name", name=name)
    return matches[0] if matches else None


def wanted(p):
    return {"InstanceName": p["name"], "DataRetentionTime": p["retention_days"]}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "instance_id": {},
            "name": {},
            "vpc_id": {},
            "subnet_id": {},
            "zone": {},
            "retention_days": {"type": "int", "choices": [15, 30, 45, 90, 180, 365, 730], "default": 15},
            "grafana_instance_id": {},
            "tags": {"type": "dict", "default": {}},
            "instance_attributes": {"type": "dict", "default": {}},
        },
        required_one_of=[("instance_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p["name"]:
        module.fail_json(msg="name is required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.MonitorClient, "monitor.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["instance_id"], p["name"])
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, instance=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.TerminatePrometheusInstances, build_delete(models, current["InstanceId"]))
            module.exit_json(changed=True, **(diff or {}), instance=current if module.check_mode else None)
        target = wanted(p)
        before = {k: current.get(k) for k in target} if current else None
        if before == target:
            module.exit_json(changed=False, instance=current)
        if not current and not all((p["vpc_id"], p["subnet_id"], p["zone"])):
            module.fail_json(msg="vpc_id, subnet_id and zone are required when creating")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                module.sdk_call(client.ModifyPrometheusInstanceAttributes, build_update(models, p, current["InstanceId"]))
                iid = current["InstanceId"]
            else:
                iid = module.sdk_call(client.CreatePrometheusMultiTenantInstancePostPayMode, build_create(models, p)).InstanceId
            current = find(module, client, models, iid, None)
        module.exit_json(changed=True, **(diff or {}), instance=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
