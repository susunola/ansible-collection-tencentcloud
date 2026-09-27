"""Harness tests for config_aggregate_delivery_info.

The module subclasses ``AnsibleModule``, so the end-to-end tests patch the two
factories it builds its client with (``create_credential`` and
``create_client_profile``) and keep the ``sys.modules`` injection of the fake
``tencentcloud.config.v20220802`` service, which the module imports itself.
``module_args()`` supplies the credentials the argument spec validates.

``run_module()`` is driven for four of the module's documented behaviours: the
single delivery document it returns both as a one-element list and as a single
value with ``RequestId`` stripped out and reported separately, the
all-``None`` document the API returns for an aggregator with no delivery
configured, and the two failure paths -- the Config SDK package missing, and an
API call that raises.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    TencentCloudSDKException,
)
from ansible_collections.susunola.tencentcloud.plugins.modules import config_aggregate_delivery_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


class FakeRequest:
    pass


class FakeModels:
    DescribeAggregateConfigDeliverRequest = FakeRequest


def test_build_request_sets_account_group_id():
    assert config_aggregate_delivery_info.build_request(FakeModels, "ag-1").AccountGroupId == "ag-1"


#: Field names and shapes of the real ``DescribeAggregateConfigDeliverResponse``
#: model, so the payload the tests assert on is the one the API returns.
DELIVERY = {
    "DeliverName": "audit-delivery",
    "TargetArn": "qcs::ckafka:ap-guangzhou::ckafkaId/ckafka-abc123",
    "Status": "Enabled",
    "CreateTime": "2026-01-05 10:20:31",
    "DeliverPrefix": "config-audit",
    "DeliverType": "Ckafka",
    "DeliverUin": "100000000001",
    "DeliverContentType": "ConfigurationItem",
}

#: What the same model serialises to when no delivery is configured.
EMPTY_DELIVERY = {
    "DeliverName": None,
    "TargetArn": None,
    "Status": None,
    "CreateTime": None,
    "DeliverPrefix": None,
    "DeliverType": None,
    "DeliverUin": None,
    "DeliverContentType": None,
}


class FakeResponse:
    """Config response: an SDK model exposing ``_serialize(allow_none=True)``."""

    def __init__(self, delivery, request_id="req-1"):
        self.delivery = delivery
        self.RequestId = request_id

    def _serialize(self, allow_none=True):
        payload = dict(self.delivery)
        payload["RequestId"] = self.RequestId
        return payload


class FakeConfigClient:
    def __init__(self, response):
        self._response = response
        self.requests = []

    def DescribeAggregateConfigDeliver(self, request):
        self.requests.append(request)
        return self._response


def _inject_sdk(monkeypatch, client, created=None):
    """Install the fake ``tencentcloud.config.v20220802`` service."""

    def config_client(credential, region, profile):
        if created is not None:
            created.append((credential, region, profile))
        return client

    service = types.ModuleType("tencentcloud.config.v20220802")
    service.models = FakeModels
    service.config_client = types.SimpleNamespace(ConfigClient=config_client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.config",
                        types.ModuleType("tencentcloud.config"))
    monkeypatch.setitem(sys.modules, "tencentcloud.config.v20220802", service)


@pytest.fixture
def sdk(monkeypatch):
    """Patch the credential/profile factories the module builds its client with."""
    monkeypatch.setattr(config_aggregate_delivery_info, "create_credential",
                        lambda module: "credential")
    monkeypatch.setattr(config_aggregate_delivery_info, "create_client_profile",
                        lambda module, endpoint: "profile:%s" % endpoint)


def test_run_module_returns_the_delivery_without_the_request_id(monkeypatch, sdk):
    client = FakeConfigClient(FakeResponse(DELIVERY, request_id="req-1"))
    created = []
    _inject_sdk(monkeypatch, client, created)
    module_args(account_group_id="ag-abc123")

    payload = run(config_aggregate_delivery_info.run_module)

    assert payload == {
        "changed": False,
        "deliveries": [DELIVERY],
        "delivery": DELIVERY,
        "request_id": "req-1",
    }
    assert "RequestId" not in payload["delivery"]
    assert [request.AccountGroupId for request in client.requests] == ["ag-abc123"]
    # The client is built once, for the requested region and the Config endpoint.
    assert created == [("credential", "ap-guangzhou", "profile:config.tencentcloudapi.com")]


def test_run_module_returns_a_null_document_when_no_delivery_is_configured(monkeypatch, sdk):
    client = FakeConfigClient(FakeResponse(EMPTY_DELIVERY, request_id="req-none"))
    _inject_sdk(monkeypatch, client)
    module_args(account_group_id="ag-empty")

    payload = run(config_aggregate_delivery_info.run_module)

    assert payload == {
        "changed": False,
        "deliveries": [EMPTY_DELIVERY],
        "delivery": EMPTY_DELIVERY,
        "request_id": "req-none",
    }
    assert [request.AccountGroupId for request in client.requests] == ["ag-empty"]


def test_run_module_fails_when_the_config_sdk_package_is_missing(monkeypatch, sdk):
    # ``None`` in ``sys.modules`` is how the import system represents a package
    # that is not installed, without depending on whether it is here or not.
    monkeypatch.setitem(sys.modules, "tencentcloud.config.v20220802", None)
    module_args(account_group_id="ag-1")

    with pytest.raises(AnsibleFailJson) as failure:
        run(config_aggregate_delivery_info.run_module)

    assert failure.value.args[0]["msg"] == (
        "The tencentcloud-sdk-python-config package is required.")


class FakeSDKError(TencentCloudSDKException):
    """SDK failure carrying the code and request id the API reported.

    ``TencentCloudSDKException`` is the installed SDK class or the shim's
    placeholder depending on the environment, so the accessors are pinned here
    instead of read back from the constructor.
    """

    def __init__(self, message="access denied"):
        super(FakeSDKError, self).__init__("UnauthorizedOperation", message, "req-err")

    def get_code(self):
        return "UnauthorizedOperation"

    def get_request_id(self):
        return "req-err"


def test_run_module_fails_with_the_sdk_error_envelope(monkeypatch, sdk):
    class FailingClient:
        def DescribeAggregateConfigDeliver(self, request):
            raise FakeSDKError("access denied")

    _inject_sdk(monkeypatch, FailingClient())
    module_args(account_group_id="ag-fail")

    with pytest.raises(AnsibleFailJson) as failure:
        run(config_aggregate_delivery_info.run_module)

    payload = failure.value.args[0]
    assert payload["failed"] is True
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "access denied" in payload["error"]
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"


def test_run_module_fails_on_an_unexpected_error(monkeypatch, sdk):
    class FailingClient:
        def DescribeAggregateConfigDeliver(self, request):
            raise RuntimeError("connection reset")

    _inject_sdk(monkeypatch, FailingClient())
    module_args(account_group_id="ag-fail")

    with pytest.raises(AnsibleFailJson) as failure:
        run(config_aggregate_delivery_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Unexpected Tencent Cloud API error"
    assert payload["error"] == "connection reset"
