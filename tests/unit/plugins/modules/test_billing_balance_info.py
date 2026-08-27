from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.tencentcloud.cloud.plugins.modules import billing_balance_info


class FakeRequest:
    pass


class FakeModels:
    DescribeAccountBalanceRequest = FakeRequest


def test_build_request_has_no_arguments():
    request = billing_balance_info.build_request(FakeModels, 0, 0)
    assert vars(request) == {}


class FakeResponse:
    def _serialize(self, allow_none=True):
        return {"Balance": 1000, "RealBalance": 1000.0, "RequestId": "req-123"}


class FakeClient:
    def __init__(self):
        self.requests = []

    def DescribeAccountBalance(self, request):
        self.requests.append(request)
        return FakeResponse()


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
    service = types.ModuleType("tencentcloud.billing.v20180709")
    service.models = FakeModels
    service.billing_client = types.SimpleNamespace(BillingClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(
        sys.modules, "tencentcloud.billing", types.ModuleType("tencentcloud.billing"))
    monkeypatch.setitem(sys.modules, "tencentcloud.billing.v20180709", service)
    fake = FakeModule(params)
    monkeypatch.setattr(billing_balance_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(billing_balance_info, "create_credential", lambda module: object())
    monkeypatch.setattr(
        billing_balance_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        billing_balance_info.run_module()
    return fake


def test_run_module_returns_balance_without_request_id(monkeypatch):
    client = FakeClient()
    fake = _run(monkeypatch, client, region="ap-guangzhou")
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert payload["balance"] == {"Balance": 1000, "RealBalance": 1000.0}
    assert len(client.requests) == 1
