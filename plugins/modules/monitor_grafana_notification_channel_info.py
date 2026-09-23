#!/usr/bin/python
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: monitor_grafana_notification_channel_info
short_description: Gather Grafana notification channels
version_added: "1.4.0"
description: Lists notification channels in a Tencent Cloud Managed Grafana instance.
options:
  instance_id: {description: Grafana instance ID., type: str, required: true}
  channel_id: {description: Exact notification channel ID., type: str}
  name: {description: Exact notification channel name., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.monitor_grafana_notification_channel_info:
    region: ap-guangzhou
    instance_id: grafana-xxxxxxxx
'''
RETURN = r'''
channels: {description: Matching notification channels., returned: always, type: list, elements: dict}
channel: {description: Single matching channel when exactly one is found., returned: always, type: dict}
request_id: {description: Request ID of the final API call., returned: always, type: str}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def build_request(models, params, offset):
    request = models.DescribeGrafanaNotificationChannelsRequest()
    request.InstanceId = params["instance_id"]
    request.ChannelIDs = [params["channel_id"]] if params.get("channel_id") else None
    request.ChannelName = params.get("name") if not params.get("channel_id") else None
    request.Offset, request.Limit = offset, 100
    return request


def matches(channel, params):
    return all((
        not params.get("channel_id") or channel.get("ChannelId") == params["channel_id"],
        not params.get("name") or channel.get("ChannelName") == params["name"],
    ))


def run_module():
    module = TencentCloudModule(argument_spec={
        "instance_id": {"required": True}, "channel_id": {}, "name": {},
    }, supports_check_mode=True)
    params = module.params
    module.require_sdk()
    try:
        from tencentcloud.monitor.v20180724 import models, monitor_client
        client = module.create_client(monitor_client.MonitorClient, "monitor.tencentcloudapi.com")
        channels, offset, request_id = [], 0, None
        while True:
            response = module.sdk_call(client.DescribeGrafanaNotificationChannels,
                                       build_request(models, params, offset))
            request_id = getattr(response, "RequestId", None)
            page = list(response.NotificationChannelSet or [])
            channels.extend(value for value in
                            (item._serialize(allow_none=True) for item in page)
                            if matches(value, params))
            offset += len(page)
            if len(page) < 100:
                break
        module.exit_json(changed=False, channels=channels,
                         channel=channels[0] if len(channels) == 1 else None,
                         request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
