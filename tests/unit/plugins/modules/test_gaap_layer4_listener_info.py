from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import (
    gaap_layer4_listener_info,
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
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


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


class ModuleExit(Exception):
    pass


class FakeModule:
    def __init__(self, params):
        self.params = params
        self.exit_payload = None

    def exit_json(self, **kwargs):
        self.exit_payload = kwargs
        raise ModuleExit()

    def fail_json(self, **kwargs):
        raise AssertionError("fail_json called: %r" % (kwargs,))


def _run(monkeypatch, client, **params):
    service = types.ModuleType("tencentcloud.gaap.v20180529")
    service.models = FakeModels
    service.gaap_client = types.SimpleNamespace(GaapClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.gaap", types.ModuleType("tencentcloud.gaap"))
    monkeypatch.setitem(sys.modules, "tencentcloud.gaap.v20180529", service)
    defaults = {
        "region": "ap-guangzhou",
        "protocol": None,
        "proxy_id": None,
        "listener_id": None,
        "listener_name": None,
        "port": None,
        "page_size": 100,
    }
    defaults.update(params)
    fake = FakeModule(defaults)
    monkeypatch.setattr(gaap_layer4_listener_info, "AnsibleModule",
                        lambda **kwargs: fake)
    monkeypatch.setattr(gaap_layer4_listener_info, "create_credential",
                        lambda module: object())
    monkeypatch.setattr(gaap_layer4_listener_info, "create_client_profile",
                        lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        gaap_layer4_listener_info.run_module()
    return fake


def test_both_protocols_are_queried_and_marked(monkeypatch):
    client = FakeClient({
        "DescribeTCPListeners": [FakeResponse([FakeItem("tcp-1")], 1)],
        "DescribeUDPListeners": [FakeResponse([FakeItem("udp-1")], 1)],
    })
    payload = _run(monkeypatch, client).exit_payload
    assert payload["changed"] is False
    assert [(item["Marker"], item["protocol"]) for item in payload["listeners"]] == [
        ("tcp-1", "TCP"), ("udp-1", "UDP"),
    ]
    assert payload["total_count"] == 2
    assert [action for action, request in client.requests] == [
        "DescribeTCPListeners", "DescribeUDPListeners",
    ]


def test_protocol_narrows_the_query_to_one_action(monkeypatch):
    client = FakeClient({
        "DescribeTCPListeners": [FakeResponse([FakeItem("tcp-1")], 1)],
        "DescribeUDPListeners": [FakeResponse([FakeItem("udp-1")], 1)],
    })
    payload = _run(monkeypatch, client, protocol="UDP").exit_payload
    assert [item["protocol"] for item in payload["listeners"]] == ["UDP"]
    assert [action for action, request in client.requests] == ["DescribeUDPListeners"]


def test_pagination_runs_per_protocol_and_totals_add_up(monkeypatch):
    client = FakeClient({
        "DescribeTCPListeners": [
            FakeResponse([FakeItem("tcp-1"), FakeItem("tcp-2")], 3),
            FakeResponse([FakeItem("tcp-3")], 3),
        ],
        "DescribeUDPListeners": [FakeResponse([FakeItem("udp-1")], 1)],
    })
    payload = _run(monkeypatch, client, page_size=2).exit_payload
    assert [item["Marker"] for item in payload["listeners"]] == [
        "tcp-1", "tcp-2", "tcp-3", "udp-1",
    ]
    assert payload["total_count"] == 4
    offsets = [request.Offset for action, request in client.requests
               if action == "DescribeTCPListeners"]
    assert offsets == [0, 2]


def test_scope_fields_reach_both_requests(monkeypatch):
    client = FakeClient({
        "DescribeTCPListeners": [FakeResponse([], 0)],
        "DescribeUDPListeners": [FakeResponse([], 0)],
    })
    _run(monkeypatch, client, proxy_id="link-9", port=53)
    assert [request.ProxyId for action, request in client.requests] == ["link-9", "link-9"]
    assert [request.Port for action, request in client.requests] == [53, 53]
