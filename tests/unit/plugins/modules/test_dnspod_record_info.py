from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import dnspod_record_info


class FakeRequest:
    pass


class FakeModels:
    DescribeRecordListRequest = FakeRequest


def test_build_request_sets_domain_and_int_pagination():
    request = dnspod_record_info.build_request(FakeModels, "example.com", 20, 100)
    assert request.Domain == "example.com"
    assert request.Offset == 20
    assert request.Limit == 100


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


class FakeRecordCountInfo:
    def __init__(self, total_count):
        self.TotalCount = total_count


class FakeResponse:
    def __init__(self, items, total_count):
        self.RecordList = items
        self.RecordCountInfo = FakeRecordCountInfo(total_count)


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeRecordList(self, request):
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
    service = types.ModuleType("tencentcloud.dnspod.v20210323")
    service.models = FakeModels
    service.dnspod_client = types.SimpleNamespace(DnspodClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.dnspod", types.ModuleType("tencentcloud.dnspod"))
    monkeypatch.setitem(sys.modules, "tencentcloud.dnspod.v20210323", service)
    fake = FakeModule(params)
    monkeypatch.setattr(dnspod_record_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(dnspod_record_info, "create_credential", lambda module: object())
    monkeypatch.setattr(dnspod_record_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        dnspod_record_info.run_module()
    return fake


def test_run_module_paginates_using_nested_total_count(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 3),
        FakeResponse([FakeItem("c")], 3),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou", domain="example.com", page_size=2)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Marker"] for item in payload["records"]] == ["a", "b", "c"]
    assert payload["total_count"] == 3
    assert [request.Offset for request in client.requests] == [0, 2]
    assert client.requests[0].Domain == "example.com"
