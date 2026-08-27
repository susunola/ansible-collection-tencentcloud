from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import cloudaudit_event_info


class FakeRequest:
    pass


class FakeModels:
    LookUpEventsRequest = FakeRequest


def test_build_request_sets_max_results_and_optional_time_range():
    request = cloudaudit_event_info.build_request(FakeModels, 1704067200, None, None, 50)
    assert request.MaxResults == 50
    assert request.StartTime == 1704067200
    assert not hasattr(request, "EndTime")
    assert not hasattr(request, "NextToken")


def test_build_request_sets_next_token_when_given():
    request = cloudaudit_event_info.build_request(FakeModels, None, None, "token-2", 50)
    assert request.NextToken == "token-2"
    assert not hasattr(request, "StartTime")


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


class FakeResponse:
    def __init__(self, items, total_count, next_token, list_over):
        self.Events = items
        self.TotalCount = total_count
        self.NextToken = next_token
        self.ListOver = list_over


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def LookUpEvents(self, request):
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
    service = types.ModuleType("tencentcloud.cloudaudit.v20190319")
    service.models = FakeModels
    service.cloudaudit_client = types.SimpleNamespace(CloudauditClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(
        sys.modules, "tencentcloud.cloudaudit", types.ModuleType("tencentcloud.cloudaudit"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cloudaudit.v20190319", service)
    fake = FakeModule(params)
    monkeypatch.setattr(cloudaudit_event_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(cloudaudit_event_info, "create_credential", lambda module: object())
    monkeypatch.setattr(
        cloudaudit_event_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        cloudaudit_event_info.run_module()
    return fake


def test_run_module_follows_next_token_until_list_over(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 3, "token-2", False),
        FakeResponse([FakeItem("c")], 3, "", True),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou",
                start_time=None, end_time=None, page_size=2)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Marker"] for item in payload["events"]] == ["a", "b", "c"]
    assert payload["total_count"] == 3
    assert [getattr(request, "NextToken", None) for request in client.requests] == [None, "token-2"]


def test_run_module_stops_when_next_token_is_empty(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("a")], None, "", False),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou",
                start_time=None, end_time=None, page_size=2)
    payload = fake.exit_payload
    assert payload["total_count"] == 1
    assert len(client.requests) == 1
