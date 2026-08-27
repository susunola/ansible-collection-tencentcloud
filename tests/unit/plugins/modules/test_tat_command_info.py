from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.tencentcloud.cloud.plugins.modules import tat_command_info


class FakeFilter:
    pass


class FakeRequest:
    pass


class FakeModels:
    Filter = FakeFilter
    DescribeCommandsRequest = FakeRequest


def test_build_request_maps_ids_and_int_pagination():
    request = tat_command_info.build_request(FakeModels, ["cmd-123"], {}, 20, 100)
    assert request.CommandIds == ["cmd-123"]
    assert request.Offset == 20
    assert request.Limit == 100


def test_build_request_sorts_filters():
    request = tat_command_info.build_request(
        FakeModels, [], {"command-name": ["deploy"], "created-by": ["ansible"]}, 0, 100)
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("command-name", ["deploy"]), ("created-by", ["ansible"]),
    ]


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


class FakeResponse:
    def __init__(self, items, total_count):
        self.CommandSet = items
        self.TotalCount = total_count


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeCommands(self, request):
        self.requests.append(request)
        return self._pages.pop(0)


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
    service = types.ModuleType("tencentcloud.tat.v20201028")
    service.models = FakeModels
    service.tat_client = types.SimpleNamespace(TatClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.tat", types.ModuleType("tencentcloud.tat"))
    monkeypatch.setitem(sys.modules, "tencentcloud.tat.v20201028", service)
    fake = FakeModule(params)
    monkeypatch.setattr(tat_command_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(tat_command_info, "create_credential", lambda module: object())
    monkeypatch.setattr(tat_command_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        tat_command_info.run_module()
    return fake


def test_run_module_paginates_until_total_count(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 3),
        FakeResponse([FakeItem("c")], 3),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou",
                command_ids=None, filters={}, page_size=2)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Marker"] for item in payload["commands"]] == ["a", "b", "c"]
    assert payload["total_count"] == 3
    assert [request.Offset for request in client.requests] == [0, 2]
