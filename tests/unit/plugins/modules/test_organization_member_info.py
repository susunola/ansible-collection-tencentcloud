from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.tencentcloud.cloud.plugins.modules import organization_member_info


class FakeRequest:
    pass


class FakeModels:
    DescribeOrganizationMembersRequest = FakeRequest


def test_build_request_uses_int_pagination():
    request = organization_member_info.build_request(FakeModels, 20, 100)
    assert request.Offset == 20
    assert request.Limit == 100


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Marker": self.marker}


class FakeResponse:
    def __init__(self, items, total):
        self.Items = items
        self.Total = total


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeOrganizationMembers(self, request):
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
    service = types.ModuleType("tencentcloud.organization.v20210331")
    service.models = FakeModels
    service.organization_client = types.SimpleNamespace(OrganizationClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(
        sys.modules, "tencentcloud.organization", types.ModuleType("tencentcloud.organization"))
    monkeypatch.setitem(sys.modules, "tencentcloud.organization.v20210331", service)
    fake = FakeModule(params)
    monkeypatch.setattr(organization_member_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(organization_member_info, "create_credential", lambda module: object())
    monkeypatch.setattr(
        organization_member_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        organization_member_info.run_module()
    return fake


def test_run_module_paginates_until_total(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("a"), FakeItem("b")], 3),
        FakeResponse([FakeItem("c")], 3),
    ])
    fake = _run(monkeypatch, client, region="ap-guangzhou", page_size=2)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Marker"] for item in payload["members"]] == ["a", "b", "c"]
    assert payload["total_count"] == 3
    assert [request.Offset for request in client.requests] == [0, 2]
