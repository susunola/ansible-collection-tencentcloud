#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: monitor_grafana_integration
short_description: Manage Tencent Cloud Managed Grafana integrations
version_added: "0.14.0"
description: Creates, updates and deletes a Managed Grafana integration.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: Grafana instance ID.}
  integration_id: {type: str, description: Existing integration ID.}
  kind: {type: str, required: true, description: Integration type code.}
  content: {type: str, description: Serialized integration configuration.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.monitor_grafana_integration:
    instance_id: grafana-xxxxxxxx
    kind: tencent-cloud-prometheus
    content: '{}'
"""
RETURN = r"""integration: {description: Grafana integration metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.monitor.v20180724 import models, monitor_client

    return models, monitor_client


def build_describe(models, p):
    request = models.DescribeGrafanaIntegrationsRequest()
    request.InstanceId, request.IntegrationId, request.Kind = p["instance_id"], p.get("integration_id"), p["kind"]
    return request


def build_create(models, p):
    request = models.CreateGrafanaIntegrationRequest()
    request.InstanceId, request.Kind, request.Content = p["instance_id"], p["kind"], p["content"]
    return request


def build_update(models, p, iid):
    request = models.UpdateGrafanaIntegrationRequest()
    request.InstanceId, request.IntegrationId, request.Kind, request.Content = p["instance_id"], iid, p["kind"], p["content"]
    return request


def build_delete(models, p, iid):
    request = models.DeleteGrafanaIntegrationRequest()
    request.InstanceId, request.IntegrationId = p["instance_id"], iid
    return request


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeGrafanaIntegrations, build_describe(models, p))
    matches = [
        x._serialize(allow_none=True)
        for x in list(response.IntegrationSet or [])
        if (p.get("integration_id") and x.IntegrationId == p["integration_id"]) or (not p.get("integration_id") and x.Kind == p["kind"])
    ]
    if len(matches) > 1:
        module.fail_json(msg="Multiple Grafana integrations have the requested kind", kind=p["kind"])
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "instance_id": {"required": True},
            "integration_id": {},
            "kind": {"required": True},
            "content": {},
        },
        required_if=[("state", "present", ["content"])],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.MonitorClient, "monitor.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, integration=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteGrafanaIntegration, build_delete(models, p, current["IntegrationId"]))
            module.exit_json(changed=True, **(diff or {}), integration=current if module.check_mode else None)
        target = {"Kind": p["kind"], "Content": p["content"]}
        before = {"Kind": current.get("Kind"), "Content": current.get("Content")} if current else None
        if before == target:
            module.exit_json(changed=False, integration=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current:
                module.sdk_call(client.UpdateGrafanaIntegration, build_update(models, p, current["IntegrationId"]))
                p["integration_id"] = current["IntegrationId"]
            else:
                p["integration_id"] = module.sdk_call(client.CreateGrafanaIntegration, build_create(models, p)).IntegrationId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), integration=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
