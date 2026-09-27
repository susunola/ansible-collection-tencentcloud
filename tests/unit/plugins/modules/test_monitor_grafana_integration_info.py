"""Deep harness tests for monitor_grafana_integration_info.

Covers the request builder the write module and the read module share (an exact
integration ID suppresses the kind filter) and run_module() end to end through
the shared harness: the API-side filter is widened to the whole set and the
exact kind match is re-applied client-side, so only the matching integration is
returned.

The module subclasses ``TencentCloudModule``, so the migration patches the base
class's ``create_client`` instead of module-level factories, and the fake
``tencentcloud.monitor.v20180724`` service is still injected through
``sys.modules`` because the module imports its models and client class directly.
The private double that replaced ``TencentCloudModule`` -- and the fake
``ansible.module_utils.basic`` that came with it -- are gone, so the payload
passes through a real ``AnsibleModule`` and feeds the module's documented
sample.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_grafana_integration as write
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_grafana_integration_info as info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    module_args,
    run,
)


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


def _inject_sdk(monkeypatch, client):
    """Hand the module a fake ``tencentcloud.monitor.v20180724`` service."""
    service = types.ModuleType("tencentcloud.monitor.v20180724")
    service.models = MODELS
    service.monitor_client = types.SimpleNamespace(MonitorClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.monitor",
                        types.ModuleType("tencentcloud.monitor"))
    monkeypatch.setitem(sys.modules, "tencentcloud.monitor.v20180724", service)


def test_info_returns_exact_kind_after_api_filter(monkeypatch):
    class Client:
        def DescribeGrafanaIntegrations(self, request):
            return types.SimpleNamespace(IntegrationSet=[Item("integration-1", "target-extra"),
                                                         Item("integration-2", "target")],
                                         RequestId="req-1")

    client = Client()
    _inject_sdk(monkeypatch, client)
    # The module asks its base class for a client; hand it the fake one.
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)
    module_args(instance_id="grafana-1", kind="target")

    payload = run(info.run_module)

    assert payload["changed"] is False
    assert [item["IntegrationId"] for item in payload["integrations"]] == ["integration-2"]
    assert payload["integration"]["Kind"] == "target"
    assert payload["request_id"] == "req-1"
