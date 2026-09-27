"""Deep harness tests for gaap_layer4_listener_info.

Covers build_request's scope-field mapping (unset filters stay off the request)
and run_module() end to end through the shared harness: both protocols queried
and marked, protocol narrowing, per-protocol pagination with a summed total, and
the scope fields reaching both requests.

The module is a plain ``AnsibleModule`` module that imports ``create_credential``
and ``create_client_profile`` into its own namespace, so the tests patch those
two factories and keep the ``sys.modules`` injection of the fake
``tencentcloud.gaap.v20180529`` service, which the harness does not provide
because the module reaches the SDK directly. The fixture returns ``ListenerId``
rather than a generic ``Marker``: the payload these tests produce is what
``add_return_samples.py`` captures as the module's documented sample.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import (
    gaap_layer4_listener_info,
)
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    module_args,
    run,
)


class FakeTCPRequest:
    pass


class FakeUDPRequest:
    pass


class FakeModels:
    DescribeTCPListenersRequest = FakeTCPRequest
    DescribeUDPListenersRequest = FakeUDPRequest


def test_build_request_maps_every_scope_field():
    request = gaap_layer4_listener_info.build_request(
        FakeModels, "DescribeTCPListenersRequest",
        {"ProxyId": "link-1", "ListenerId": "listener-1",
         "ListenerName": None, "Port": 3306},
        20, 100)
    assert isinstance(request, FakeTCPRequest)
    assert request.ProxyId == "link-1"
    assert request.ListenerId == "listener-1"
    assert request.Port == 3306
    assert request.Offset == 20
    assert request.Limit == 100
    # A filter left unset must not become an attribute: the API would
    # otherwise receive an explicit None instead of "unfiltered".
    assert not hasattr(request, "ListenerName")


class FakeItem:
    def __init__(self, listener_id):
        self.listener_id = listener_id

    def _serialize(self, allow_none=True):
        return {"ListenerId": self.listener_id}


class FakeResponse:
    def __init__(self, items, total_count):
        self.ListenerSet = items
        self.TotalCount = total_count


class FakeClient:
    def __init__(self, pages):
        self._pages = dict(pages)
        self.requests = []

    def _pop(self, action, request):
        self.requests.append((action, request))
        return self._pages[action].pop(0)

    def DescribeTCPListeners(self, request):
        return self._pop("DescribeTCPListeners", request)

    def DescribeUDPListeners(self, request):
        return self._pop("DescribeUDPListeners", request)


def _inject_sdk(monkeypatch, client):
    """Hand the module a fake ``tencentcloud.gaap.v20180529`` service."""
    service = types.ModuleType("tencentcloud.gaap.v20180529")
    service.models = FakeModels
    service.gaap_client = types.SimpleNamespace(GaapClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.gaap", types.ModuleType("tencentcloud.gaap"))
    monkeypatch.setitem(sys.modules, "tencentcloud.gaap.v20180529", service)


@pytest.fixture
def sdk(monkeypatch):
    """Patch the credential/profile factories the module builds its client with."""
    monkeypatch.setattr(gaap_layer4_listener_info, "create_credential",
                        lambda module: object())
    monkeypatch.setattr(gaap_layer4_listener_info, "create_client_profile",
                        lambda module, endpoint: object())


def _args(**extra):
    """Module arguments; unused scope fields are omitted, not passed as None."""
    params = {"page_size": 100}
    params.update(extra)
    module_args(**params)


def test_both_protocols_are_queried_and_marked(monkeypatch, sdk):
    client = FakeClient({
        "DescribeTCPListeners": [FakeResponse([FakeItem("tcp-1")], 1)],
        "DescribeUDPListeners": [FakeResponse([FakeItem("udp-1")], 1)],
    })
    _inject_sdk(monkeypatch, client)
    _args()

    payload = run(gaap_layer4_listener_info.run_module)

    assert payload["changed"] is False
    assert [(item["ListenerId"], item["protocol"]) for item in payload["listeners"]] == [
        ("tcp-1", "TCP"), ("udp-1", "UDP"),
    ]
    assert payload["total_count"] == 2
    assert [action for action, request in client.requests] == [
        "DescribeTCPListeners", "DescribeUDPListeners",
    ]


def test_protocol_narrows_the_query_to_one_action(monkeypatch, sdk):
    client = FakeClient({
        "DescribeTCPListeners": [FakeResponse([FakeItem("tcp-1")], 1)],
        "DescribeUDPListeners": [FakeResponse([FakeItem("udp-1")], 1)],
    })
    _inject_sdk(monkeypatch, client)
    _args(protocol="UDP")

    payload = run(gaap_layer4_listener_info.run_module)

    assert [item["protocol"] for item in payload["listeners"]] == ["UDP"]
    assert [action for action, request in client.requests] == ["DescribeUDPListeners"]


def test_pagination_runs_per_protocol_and_totals_add_up(monkeypatch, sdk):
    client = FakeClient({
        "DescribeTCPListeners": [
            FakeResponse([FakeItem("tcp-1"), FakeItem("tcp-2")], 3),
            FakeResponse([FakeItem("tcp-3")], 3),
        ],
        "DescribeUDPListeners": [FakeResponse([FakeItem("udp-1")], 1)],
    })
    _inject_sdk(monkeypatch, client)
    _args(page_size=2)

    payload = run(gaap_layer4_listener_info.run_module)

    assert [item["ListenerId"] for item in payload["listeners"]] == [
        "tcp-1", "tcp-2", "tcp-3", "udp-1",
    ]
    assert payload["total_count"] == 4
    offsets = [request.Offset for action, request in client.requests
               if action == "DescribeTCPListeners"]
    assert offsets == [0, 2]


def test_scope_fields_reach_both_requests(monkeypatch, sdk):
    client = FakeClient({
        "DescribeTCPListeners": [FakeResponse([], 0)],
        "DescribeUDPListeners": [FakeResponse([], 0)],
    })
    _inject_sdk(monkeypatch, client)
    _args(proxy_id="link-9", port=53)

    payload = run(gaap_layer4_listener_info.run_module)

    assert payload["listeners"] == []
    assert [request.ProxyId for action, request in client.requests] == ["link-9", "link-9"]
    assert [request.Port for action, request in client.requests] == [53, 53]
