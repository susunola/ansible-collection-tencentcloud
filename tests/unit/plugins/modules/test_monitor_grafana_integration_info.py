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

from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_grafana_integration as write
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_grafana_integration_info as info


class Request:
    pass


class Item:
    def __init__(self, integration_id, kind):
        self.IntegrationId, self.Kind = integration_id, kind

    def _serialize(self, allow_none=True):
        return {"IntegrationId": self.IntegrationId, "Kind": self.Kind}


MODELS = types.SimpleNamespace(DescribeGrafanaIntegrationsRequest=Request)


def test_write_lookup_by_id_omits_kind_filter():
    request = write.build_describe(MODELS, {
        "instance_id": "grafana-1", "integration_id": "integration-1", "kind": "new-kind",
    })
    assert (request.InstanceId, request.IntegrationId, request.Kind) == (
        "grafana-1", "integration-1", None)


def test_info_request_by_id_omits_kind_filter():
    request = info.build_request(MODELS, {
        "instance_id": "grafana-1", "integration_id": "integration-1", "kind": "new-kind",
    })
    assert (request.InstanceId, request.IntegrationId, request.Kind) == (
        "grafana-1", "integration-1", None)


def test_info_returns_exact_kind_after_api_filter(monkeypatch):
    class Client:
        def DescribeGrafanaIntegrations(self, request):
            return types.SimpleNamespace(IntegrationSet=[Item("integration-1", "target-extra"),
                                                         Item("integration-2", "target")], RequestId="req-1")

    class Exit(SystemExit):
        pass

    class Module:
        params = {"instance_id": "grafana-1", "integration_id": None, "kind": "target"}

        def require_sdk(self):
            pass

        def create_client(self, cls, endpoint):
            return Client()

        def sdk_call(self, operation, request):
            return operation(request)

        def exit_json(self, **kwargs):
            raise Exit(kwargs)

    service = types.ModuleType("tencentcloud.monitor.v20180724")
    service.models = MODELS
    service.monitor_client = types.SimpleNamespace(MonitorClient=Client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.monitor", types.ModuleType("tencentcloud.monitor"))
    monkeypatch.setitem(sys.modules, "tencentcloud.monitor.v20180724", service)
    monkeypatch.setattr(info, "TencentCloudModule", lambda **kwargs: Module())
    with pytest.raises(Exit) as result:
        info.run_module()
    payload = result.value.args[0]
    assert [item["IntegrationId"] for item in payload["integrations"]] == ["integration-2"]
    assert payload["integration"]["Kind"] == "target"
