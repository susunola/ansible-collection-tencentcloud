#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: monitor_grafana_notification_channel
short_description: Manage Tencent Cloud Managed Grafana notification channels
version_added: "0.14.0"
description: Creates, updates and deletes a Grafana notification channel backed by alarm notification templates.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: Grafana instance ID.}
  channel_id: {type: str, description: Existing channel ID.}
  name: {type: str, description: Channel name.}
  receivers: {type: list, elements: str, default: [], description: Alarm notification template IDs.}
  organization_ids: {type: list, elements: str, default: ['1'], description: Grafana organization IDs.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.monitor_grafana_notification_channel:
    instance_id: grafana-xxxxxxxx
    name: operations
    receivers: [notice-xxxxxxxx]
"""
RETURN = r"""channel: {description: Grafana notification-channel metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.monitor.v20180724 import models, monitor_client

    return models, monitor_client


def build_describe(models, p):
    request = models.DescribeGrafanaNotificationChannelsRequest()
    request.InstanceId, request.ChannelName, request.ChannelIDs, request.Offset, request.Limit = (
        p["instance_id"],
        p.get("name"),
        [p["channel_id"]] if p.get("channel_id") else None,
        0,
        100,
    )
    return request


def build_create(models, p):
    request = models.CreateGrafanaNotificationChannelRequest()
    request.InstanceId, request.ChannelName, request.Receivers, request.OrganizationIds = p["instance_id"], p["name"], p["receivers"], p["organization_ids"]
    return request


def build_update(models, p, cid):
    request = models.UpdateGrafanaNotificationChannelRequest()
    request.InstanceId, request.ChannelId, request.Receivers, request.OrganizationIds = p["instance_id"], cid, p["receivers"], p["organization_ids"]
    return request


def build_delete(models, p, cid):
    request = models.DeleteGrafanaNotificationChannelRequest()
    request.InstanceId, request.ChannelIDs = p["instance_id"], [cid]
    return request


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeGrafanaNotificationChannels, build_describe(models, p))
    matches = [
        x._serialize(allow_none=True)
        for x in list(response.NotificationChannelSet or [])
        if (p.get("channel_id") and x.ChannelId == p["channel_id"]) or (not p.get("channel_id") and x.ChannelName == p.get("name"))
    ]
    if len(matches) > 1:
        module.fail_json(msg="Multiple Grafana channels have the requested name", name=p.get("name"))
    return matches[0] if matches else None


def target(p):
    return {"ChannelName": p["name"], "Receivers": sorted(p["receivers"]), "OrganizationIds": sorted(p["organization_ids"])}


def comparable(v):
    return {"ChannelName": v.get("ChannelName"), "Receivers": sorted(v.get("Receivers") or []), "OrganizationIds": sorted(v.get("OrganizationIds") or [])}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "instance_id": {"required": True},
            "channel_id": {},
            "name": {},
            "receivers": {"type": "list", "elements": "str", "default": []},
            "organization_ids": {"type": "list", "elements": "str", "default": ["1"]},
        },
        required_one_of=[("channel_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p["name"]:
        module.fail_json(msg="name is required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.MonitorClient, "monitor.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, channel=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteGrafanaNotificationChannel, build_delete(models, p, current["ChannelId"]))
            module.exit_json(changed=True, **(diff or {}), channel=current if module.check_mode else None)
        wanted = target(p)
        before = comparable(current) if current else None
        if before == wanted:
            module.exit_json(changed=False, channel=current)
        diff = maybe_diff(module, before, wanted)
        if not module.check_mode:
            if current:
                module.sdk_call(client.UpdateGrafanaNotificationChannel, build_update(models, p, current["ChannelId"]))
                p["channel_id"] = current["ChannelId"]
            else:
                p["channel_id"] = module.sdk_call(client.CreateGrafanaNotificationChannel, build_create(models, p)).ChannelId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), channel=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
