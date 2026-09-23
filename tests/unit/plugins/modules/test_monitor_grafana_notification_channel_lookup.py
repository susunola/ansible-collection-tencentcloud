from __future__ import absolute_import, division, print_function

import sys
import types

import pytest

basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)

from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_grafana_notification_channel as mod


class Request:
    pass


class Item:
    def __init__(self, channel_id, name):
        self.ChannelId, self.ChannelName = channel_id, name

    def _serialize(self, allow_none=True):
        return {"ChannelId": self.ChannelId, "ChannelName": self.ChannelName}


class Client:
    def __init__(self, values):
        self.values = values
        self.requests = []

    def DescribeGrafanaNotificationChannels(self, request):
        self.requests.append(request)
        values = self.values
        if request.ChannelIDs:
            values = [item for item in values if item.ChannelId in request.ChannelIDs]
        if request.ChannelName:
            values = [item for item in values if request.ChannelName in item.ChannelName]
        return types.SimpleNamespace(NotificationChannelSet=values[request.Offset:request.Offset + request.Limit])


class Module:
    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise ValueError(kwargs["msg"])


MODELS = types.SimpleNamespace(DescribeGrafanaNotificationChannelsRequest=Request)


def test_find_name_paginates_and_filters_exact_match():
    values = [Item(str(index), "target-extra") for index in range(100)] + [Item("wanted", "target")]
    client = Client(values)
    result = mod.find(Module(), client, MODELS,
                      {"instance_id": "grafana-1", "channel_id": None, "name": "target"})
    assert result["ChannelId"] == "wanted"
    assert [request.Offset for request in client.requests] == [0, 100]


def test_find_id_ignores_name_query_filter():
    client = Client([Item("wanted", "old-name")])
    result = mod.find(Module(), client, MODELS,
                      {"instance_id": "grafana-1", "channel_id": "wanted", "name": "new-name"})
    assert result["ChannelName"] == "old-name"
    assert client.requests[0].ChannelName is None


def test_immutable_name_drift_is_rejected():
    with pytest.raises(ValueError, match="cannot be changed"):
        mod.validate_immutable_name(Module(), {"ChannelId": "wanted", "ChannelName": "old-name"}, "new-name")
