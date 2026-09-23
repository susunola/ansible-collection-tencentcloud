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

from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_grafana_notification_channel_info as mod


class Request:
    pass


class Item:
    def __init__(self, channel_id, name):
        self.channel_id, self.name = channel_id, name

    def _serialize(self, allow_none=True):
        return {"ChannelId": self.channel_id, "ChannelName": self.name}


class Exit(SystemExit):
    pass


def test_request_uses_id_without_name_filter():
    params = {"instance_id": "grafana-1", "channel_id": "nchannel-1", "name": "new-name"}
    request = mod.build_request(types.SimpleNamespace(DescribeGrafanaNotificationChannelsRequest=Request), params, 100)
    assert (request.InstanceId, request.ChannelIDs, request.ChannelName, request.Offset, request.Limit) == (
        "grafana-1", ["nchannel-1"], None, 100, 100)


def test_info_paginates_and_filters_exact_name(monkeypatch):
    requests = []

    class Client:
        def DescribeGrafanaNotificationChannels(self, request):
            requests.append(request)
            if request.Offset == 0:
                page = [Item("nchannel-%d" % index, "target-extra") for index in range(100)]
            else:
                page = [Item("nchannel-target", "target")]
            return types.SimpleNamespace(NotificationChannelSet=page, RequestId="req-1")

    class Module:
        params = {"instance_id": "grafana-1", "channel_id": None, "name": "target"}

        def require_sdk(self):
            pass

        def create_client(self, cls, endpoint):
            return Client()

        def sdk_call(self, operation, request):
            return operation(request)

        def exit_json(self, **kwargs):
            raise Exit(kwargs)

    service = types.ModuleType("tencentcloud.monitor.v20180724")
    service.models = types.SimpleNamespace(DescribeGrafanaNotificationChannelsRequest=Request)
    service.monitor_client = types.SimpleNamespace(MonitorClient=Client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.monitor", types.ModuleType("tencentcloud.monitor"))
    monkeypatch.setitem(sys.modules, "tencentcloud.monitor.v20180724", service)
    monkeypatch.setattr(mod, "TencentCloudModule", lambda **kwargs: Module())
    with pytest.raises(Exit) as result:
        mod.run_module()
    payload = result.value.args[0]
    assert payload["changed"] is False
    assert payload["channel"]["ChannelId"] == "nchannel-target"
    assert len(payload["channels"]) == 1
    assert [request.Offset for request in requests] == [0, 100]
