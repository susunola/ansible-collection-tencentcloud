#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tem_environment
short_description: Manage Tencent Cloud TEM environments
version_added: "0.14.0"
description: Creates, updates and destroys TEM environments.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  environment_id:
    description:
      - Existing environment ID.
    type: str
  name:
    description:
      - Environment name and immutable identity.
    type: str
  description:
    description:
      - Environment description.
    type: str
  vpc_id:
    description:
      - VPC ID or name accepted by TEM.
    type: str
  subnet_ids:
    description:
      - Environment subnet IDs.
    type: list
    elements: str
  kubernetes_version:
    description:
      - Creation-time Kubernetes version.
    type: str
  source_channel:
    description:
      - TEM source channel.
    type: int
    default: 0
  enable_tsw_tracing:
    description:
      - Enable TSW distributed tracing for the environment.
    type: bool
  tags:
    description:
      - Creation-time tags.
    type: dict
  environment_type:
    description:
      - Environment stage.
    type: str
    choices: [test, pre, prod]
    default: prod
  create_region:
    description:
      - Creation region override.
    type: str
  setup_vpc:
    description:
      - Create a VPC automatically.
    type: bool
  setup_prometheus:
    description:
      - Create a Prometheus instance automatically.
    type: bool
  prometheus_id:
    description:
      - Existing Prometheus instance ID.
    type: str
  apm_id:
    description:
      - Existing APM instance ID.
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
  - module: susunola.tencentcloud.tem_environment_info
    description: Gather information about Tencent Cloud TEM environments.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tem_environment:
    name: production
    description: Production TEM environment
    vpc_id: vpc-xxxxxxxx
    subnet_ids: [subnet-xxxxxxxx]
    environment_type: prod

- name: Delete the environment
  susunola.tencentcloud.tem_environment:
    state: absent
    name: production
"""
RETURN = r"""environment:
  description:
    - Effective TEM environment metadata.
  returned: always
  type: dict"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, fail_from_sdk_error


def _load():
    from tencentcloud.tem.v20210701 import models, tem_client

    return models, tem_client


def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        x = models.Tag()
        x.TagKey, x.TagValue = str(key), str(value)
        result.append(x)
    return result


def describe_request(models, p, offset=0):
    r = models.DescribeEnvironmentsRequest()
    r.EnvironmentId = p.get("environment_id")
    r.Offset, r.Limit = offset, 100
    r.SourceChannel = p["source_channel"]
    return r


def create_request(models, p):
    r = models.CreateEnvironmentRequest()
    r.EnvironmentName, r.Description, r.Vpc, r.SubnetIds = p["name"], p.get("description"), p.get("vpc_id"), p.get("subnet_ids")
    r.K8sVersion, r.SourceChannel = p.get("kubernetes_version"), p["source_channel"]
    r.EnableTswTraceService = p.get("enable_tsw_tracing")
    r.Tags = _tags(models, p.get("tags"))
    r.EnvType, r.CreateRegion = p["environment_type"], p.get("create_region")
    r.SetupVpc, r.SetupPrometheus = p.get("setup_vpc"), p.get("setup_prometheus")
    r.PrometheusId, r.ApmId = p.get("prometheus_id"), p.get("apm_id")
    return r


def update_request(models, p, environment_id, target):
    r = models.ModifyEnvironmentRequest()
    r.EnvironmentId, r.EnvironmentName = environment_id, target["EnvironmentName"]
    r.Description, r.Vpc, r.SubnetIds = target["Description"], target["Vpc"], target["SubnetIds"]
    r.SourceChannel, r.EnvType = p["source_channel"], target["EnvType"]
    return r


def delete_request(models, p, environment_id):
    r = models.DestroyEnvironmentRequest()
    r.EnvironmentId, r.SourceChannel = environment_id, p["source_channel"]
    return r


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        result = module.sdk_call(client.DescribeEnvironments, describe_request(models, p, offset)).Result
        page = (result.Records if result else None) or []
        for item in page:
            value = item._serialize(allow_none=True)
            if (p.get("environment_id") and value.get("EnvironmentId") == p["environment_id"]) or (
                not p.get("environment_id") and value.get("EnvironmentName") == p.get("name")
            ):
                matches.append(value)
        offset += len(page)
        if not page or offset >= int((result.Total if result else 0) or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple TEM environments matched; specify environment_id")
    return matches[0] if matches else None


def comparable(v):
    return {
        "EnvironmentName": v.get("EnvironmentName"),
        "Description": v.get("Description"),
        "Vpc": v.get("Vpc"),
        "SubnetIds": v.get("SubnetId") if isinstance(v.get("SubnetId"), list) else ([v.get("SubnetId")] if v.get("SubnetId") else []),
        "EnvType": v.get("EnvType"),
    }


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "environment_id": {},
        "name": {},
        "description": {},
        "vpc_id": {},
        "subnet_ids": {"type": "list", "elements": "str"},
        "kubernetes_version": {},
        "source_channel": {"type": "int", "default": 0},
        "enable_tsw_tracing": {"type": "bool"},
        "tags": {"type": "dict"},
        "environment_type": {"choices": ["test", "pre", "prod"], "default": "prod"},
        "create_region": {},
        "setup_vpc": {"type": "bool"},
        "setup_prometheus": {"type": "bool"},
        "prometheus_id": {},
        "apm_id": {},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("environment_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TemClient, "tem.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, environment=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DestroyEnvironment, delete_request(models, p, current["EnvironmentId"]))
            module.exit_json(changed=True, **(diff or {}), environment=None)
        if not current:
            if not p.get("name"):
                module.fail_json(msg="name is required to create a TEM environment")
            target = {
                "EnvironmentName": p["name"],
                "Description": p.get("description"),
                "Vpc": p.get("vpc_id"),
                "SubnetIds": p.get("subnet_ids") or [],
                "EnvType": p["environment_type"],
            }
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                p["environment_id"] = module.sdk_call(client.CreateEnvironment, create_request(models, p)).Result
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), environment=current if not module.check_mode else target)
        before = comparable(current)
        target = {
            "EnvironmentName": p.get("name") or before["EnvironmentName"],
            "Description": p.get("description") if p.get("description") is not None else before["Description"],
            "Vpc": p.get("vpc_id") or before["Vpc"],
            "SubnetIds": p.get("subnet_ids") if p.get("subnet_ids") is not None else before["SubnetIds"],
            "EnvType": p.get("environment_type") or before["EnvType"],
        }
        if before == target:
            module.exit_json(changed=False, environment=current)
        require_immutable_unchanged(module, before, target, ("EnvironmentName",), "TEM environment")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyEnvironment, update_request(models, p, current["EnvironmentId"], target))
            p["environment_id"] = current["EnvironmentId"]
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), environment=current if not module.check_mode else target)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
