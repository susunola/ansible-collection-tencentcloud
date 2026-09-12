from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import cfw_address_template_info


class FakeRequest:
    pass


class FakeModels:
    DescribeAddressTemplateListRequest = FakeRequest


def test_build_request_sets_lookup_fields():
    request = cfw_address_template_info.build_request(FakeModels, "uuid-x", "trusted", 200, 100)
    assert request.Offset == 200
    assert request.Limit == 100
    assert request.Uuid == "uuid-x"
    assert request.SearchValue == "trusted"


class FakeItem:
    def __init__(self, uuid, name):
        self.uuid = uuid
        self.name = name

    def _serialize(self, allow_none=True):
        return {"Uuid": self.uuid, "Name": self.name}


class FakeResponse:
    def __init__(self, items, total):
        self.Data = items
        self.Total = total
        self.RequestId = "req-page"


class FakeClient:
    def __init__(self, pages):
        self._pages = list(pages)
        self.requests = []

    def DescribeAddressTemplateList(self, request):
        self.requests.append(request)
        return self._pages.pop(0)


class ModuleExit(Exception):
    pass


class ModuleFail(Exception):
    def __init__(self, payload):
        self.payload = payload
        super(ModuleFail, self).__init__("module failed: %r" % (payload,))


class FakeModule:
    def __init__(self, params):
        self.params = params
        self.exit_payload = None

    def exit_json(self, **kwargs):
        self.exit_payload = kwargs
        raise ModuleExit()

    def fail_json(self, **kwargs):
        raise ModuleFail(kwargs)


def _inject_sdk(monkeypatch, client):
    service = types.ModuleType("tencentcloud.cfw.v20190904")
    service.models = FakeModels
    service.cfw_client = types.SimpleNamespace(CfwClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cfw", types.ModuleType("tencentcloud.cfw"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cfw.v20190904", service)


def test_run_module_paginates_and_filters_exact_name(monkeypatch):
    client = FakeClient([
        FakeResponse([FakeItem("uuid-a", "trusted"), FakeItem("uuid-b", "trusted-old")], 3),
        FakeResponse([FakeItem("uuid-c", "trusted")], 3),
    ])
    _inject_sdk(monkeypatch, client)
    fake = FakeModule({"region": "ap-guangzhou", "uuid": None, "name": "trusted", "page_size": 2})
    monkeypatch.setattr(cfw_address_template_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(cfw_address_template_info, "create_credential", lambda module: object())
    monkeypatch.setattr(cfw_address_template_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        cfw_address_template_info.run_module()
    assert fake.exit_payload["changed"] is False
    assert [item["Uuid"] for item in fake.exit_payload["templates"]] == ["uuid-a", "uuid-c"]
    assert fake.exit_payload["total_count"] == 3
    assert [request.Offset for request in client.requests] == [0, 2]


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def DescribeAddressTemplateList(self, request):
            raise RuntimeError("api exploded")

    def failing_sdk_call(module, function, request):
        try:
            return function(request)
        except RuntimeError as exc:
            module.fail_json(
                msg="Tencent Cloud API request failed",
                error=str(exc),
                error_code="UnauthorizedOperation",
                request_id="req-err",
            )

    _inject_sdk(monkeypatch, FailingClient())
    fake = FakeModule({"region": "ap-guangzhou", "uuid": None, "name": "trusted", "page_size": 2})
    monkeypatch.setattr(cfw_address_template_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(cfw_address_template_info, "create_credential", lambda module: object())
    monkeypatch.setattr(cfw_address_template_info, "create_client_profile", lambda module, endpoint: object())
    monkeypatch.setattr(cfw_address_template_info, "sdk_call", failing_sdk_call)
    with pytest.raises(ModuleFail) as excinfo:
        cfw_address_template_info.run_module()
    assert excinfo.value.payload["error_code"] == "UnauthorizedOperation"
    assert excinfo.value.payload["request_id"] == "req-err"
