"""Tests for the account-level Config readers: config_delivery_info and config_recorder_info.

Both modules are raw-``AnsibleModule`` singletons: one region, one describe
call, and a payload that carries the same configuration twice -- as a
single-element list and as the dictionary itself. ``config_recorder_info``
additionally flattens the recorder's monitored resource types into a
deduplicated, sorted list, so a caller can compare ``recorder.ResourceTypes``
with a task's ``resource_types`` without caring about API repetition or order.

The request-builder and normalise tests came first and stay as they were.
Everything below drives ``run_module()`` through the shared harness. The
modules build their own ``ConfigClient`` from the ``tencentcloud.config.v20220802``
service, so the fake service is injected into ``sys.modules`` and the two
legacy factories (``create_credential`` / ``create_client_profile``) are
patched on each module. The real shared read helper runs, which is what makes
the two failure envelopes -- the SDK one and the unexpected one -- the
modules' own behaviour rather than a test double's.

This file used to install a stub ``ansible.module_utils.basic`` in
``sys.modules`` to import the modules. That stub leaked into every test module
collected afterwards in the same pytest process, so ``ansible.module_utils.common``
stopped resolving and unrelated files failed at collection. The real
``ansible.module_utils.basic`` is used now, which is also what the shared
harness needs.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import tencentcloud as tc
from ansible_collections.susunola.tencentcloud.plugins.modules import config_delivery_info, config_recorder_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeResource,
    module_args,
    run,
)


class FakeRequest(object):
    """One SDK request model: a plain attribute store."""


class FakeModels(object):
    """Minimal models module for the request-builder tests."""

    DescribeConfigDeliverRequest = FakeRequest
    DescribeConfigRecorderRequest = FakeRequest


def test_singleton_requests_use_expected_models():
    assert isinstance(config_delivery_info.build_request(FakeModels), FakeRequest)
    assert isinstance(config_recorder_info.build_request(FakeModels), FakeRequest)


def test_recorder_normalize_sorts_and_deduplicates_resource_types():
    class Item:
        def __init__(self, value):
            self.ResourceType = value

    class Response:
        Items = [Item("QCS::VPC::VPC"), Item("QCS::CVM::Instance"), Item("QCS::VPC::VPC")]

        def _serialize(self, allow_none=True):
            return {"RequestId": "request-1", "Status": 1}

    assert config_recorder_info.normalize(Response())["ResourceTypes"] == ["QCS::CVM::Instance", "QCS::VPC::VPC"]


REGION = "ap-guangzhou"
OTHER_REGION = "ap-shanghai"
ENDPOINT = "config.tencentcloudapi.com"
REQUEST_ID = "req-config-1"

#: One ``DescribeConfigDeliver`` configuration as the SDK serialises it, minus
#: the request id the module lifts out into ``request_id``.
DELIVERY = {
    "Status": 1,
    "DeliverName": "compliance-archive",
    "TargetArn": "qcs::cos:ap-guangzhou:100000000001:prefix/1250000000/config-archive",
    "DeliverPrefix": "config",
    "DeliverType": "COS",
    "DeliverContentType": 3,
}

#: ``DescribeConfigRecorder`` answers with the recorder status and one entry
#: per monitored resource type -- the API repeats a type, and returns the set
#: in its own order.
RECORDER_STATUS = 1
RECORDER_TYPES = ["QCS::VPC::VPC", "QCS::CVM::Instance", "QCS::VPC::VPC"]


class RecorderResponse(object):
    """``DescribeConfigRecorder`` response.

    The module reads the monitored types off ``Items`` and the status off the
    serialised model, so the fake keeps the two apart the way the real
    response does: ``Items`` is the per-type list, ``_serialize`` the scalar
    fields (with the request id) Ansible returns.
    """

    def __init__(self, status=RECORDER_STATUS, items=None, request_id=REQUEST_ID):
        self.Status = status
        self.Items = [FakeResource({"ResourceType": value}) for value in (RECORDER_TYPES if items is None else items)]
        self.RequestId = request_id

    def _serialize(self, allow_none=True):
        return {"RequestId": self.RequestId, "Status": self.Status}


def delivery_response(delivery=None, request_id=REQUEST_ID):
    """``DescribeConfigDeliver`` response: the configuration plus its request id."""
    return FakeResource(dict(DELIVERY if delivery is None else delivery, RequestId=request_id))


class FakeConfigClient(object):
    """Config client answering the two singleton describe calls."""

    def __init__(self, delivery=None, recorder=None, error=None):
        self.delivery = delivery_response() if delivery is None else delivery
        self.recorder = RecorderResponse() if recorder is None else recorder
        self.error = error
        self.requests = []

    def DescribeConfigDeliver(self, request):
        self.requests.append(("DescribeConfigDeliver", request))
        if self.error is not None:
            raise self.error
        return self.delivery

    def DescribeConfigRecorder(self, request):
        self.requests.append(("DescribeConfigRecorder", request))
        if self.error is not None:
            raise self.error
        return self.recorder


def _inject_sdk(monkeypatch, client):
    """Install a fake ``tencentcloud.config.v20220802`` service.

    The modules import the client and the models inside ``run_module`` (the
    lazy-import convention every module follows), so the service has to be
    reachable through ``sys.modules``. The client factory records the
    credential, region and profile it was handed, which is how the tests see
    the endpoint and the region the task asked for.
    """
    factory_calls = []

    def factory(credential, region, profile):
        factory_calls.append((credential, region, profile))
        return client

    service = types.ModuleType("tencentcloud.config.v20220802")
    service.models = FakeModels()
    service.config_client = SimpleNamespace(ConfigClient=factory)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.config", types.ModuleType("tencentcloud.config"))
    monkeypatch.setitem(sys.modules, "tencentcloud.config.v20220802", service)
    return factory_calls


@pytest.fixture
def sdk(monkeypatch):
    """Patch the legacy credential/profile factories the modules build clients with."""
    credential = SimpleNamespace(name="credential")
    profile = SimpleNamespace(name="profile")
    endpoints = []

    def profile_factory(module, endpoint):
        endpoints.append(endpoint)
        return profile

    for module in (config_delivery_info, config_recorder_info):
        monkeypatch.setattr(module, "create_credential", lambda module: credential)
        monkeypatch.setattr(module, "create_client_profile", profile_factory)
    return SimpleNamespace(credential=credential, profile=profile, endpoints=endpoints)


# ---------------------------------------------------------------------------
# config_delivery_info
# ---------------------------------------------------------------------------


def test_delivery_info_returns_the_documented_keys(monkeypatch, sdk):
    client = FakeConfigClient()
    _inject_sdk(monkeypatch, client)
    module_args(region=REGION)

    payload = run(config_delivery_info.run_module)

    assert payload.keys() == {"changed", "deliveries", "delivery", "request_id"}
    assert payload["changed"] is False
    assert payload["delivery"] == DELIVERY
    assert payload["deliveries"] == [DELIVERY]
    assert payload["request_id"] == REQUEST_ID


def test_delivery_info_drops_the_request_id_from_the_configuration(monkeypatch, sdk):
    """The request id is reported once, as ``request_id``, not inside the config."""
    client = FakeConfigClient()
    _inject_sdk(monkeypatch, client)
    module_args(region=REGION)

    payload = run(config_delivery_info.run_module)

    assert "RequestId" not in payload["delivery"]
    assert "RequestId" not in payload["deliveries"][0]


def test_delivery_info_uses_the_config_endpoint_and_the_requested_region(monkeypatch, sdk):
    """One ``DescribeConfigDeliver`` on the Config endpoint, for the region asked for."""
    client = FakeConfigClient()
    factory_calls = _inject_sdk(monkeypatch, client)
    module_args(region=OTHER_REGION)

    run(config_delivery_info.run_module)

    assert [name for name, _request in client.requests] == ["DescribeConfigDeliver"]
    assert isinstance(client.requests[0][1], FakeRequest)
    assert factory_calls == [(sdk.credential, OTHER_REGION, sdk.profile)]
    assert sdk.endpoints == [ENDPOINT]


def test_delivery_info_reads_in_check_mode(monkeypatch, sdk):
    """A reader can run in check mode: it only ever reads."""
    client = FakeConfigClient()
    _inject_sdk(monkeypatch, client)
    module_args(region=REGION, _ansible_check_mode=True)

    payload = run(config_delivery_info.run_module)

    assert payload["changed"] is False
    assert payload["delivery"] == DELIVERY
    assert len(client.requests) == 1


def test_delivery_info_is_repeatable(monkeypatch, sdk):
    """A repeated read reports the same state and never changes anything."""
    client = FakeConfigClient()
    _inject_sdk(monkeypatch, client)
    module_args(region=REGION)

    first = run(config_delivery_info.run_module)
    second = run(config_delivery_info.run_module)

    assert first == second
    assert second["changed"] is False
    assert [name for name, _request in client.requests] == ["DescribeConfigDeliver", "DescribeConfigDeliver"]


def test_delivery_info_maps_an_sdk_error_to_the_failure_envelope(monkeypatch, sdk):
    class FakeSdkException(Exception):
        def get_code(self):
            return "UnauthorizedOperation"

        def get_request_id(self):
            return "req-config-denied"

    monkeypatch.setattr(tc, "TencentCloudSDKException", FakeSdkException)
    client = FakeConfigClient(error=FakeSdkException("not allowed to read the delivery configuration"))
    _inject_sdk(monkeypatch, client)
    module_args(region=REGION)

    with pytest.raises(AnsibleFailJson) as failure:
        run(config_delivery_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "not allowed to read the delivery configuration"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-config-denied"


def test_delivery_info_maps_an_unexpected_error_to_the_failure_envelope(monkeypatch, sdk):
    """A non-SDK exception still fails the task instead of escaping."""
    client = FakeConfigClient(error=RuntimeError("socket closed"))
    _inject_sdk(monkeypatch, client)
    module_args(region=REGION)

    with pytest.raises(AnsibleFailJson) as failure:
        run(config_delivery_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Unexpected Tencent Cloud API error"
    assert payload["error"] == "socket closed"


def test_delivery_info_requires_the_config_sdk_package(monkeypatch, sdk):
    """Without the per-product SDK the module names the package to install."""
    _inject_sdk(monkeypatch, FakeConfigClient())
    monkeypatch.setitem(sys.modules, "tencentcloud.config.v20220802", None)
    module_args(region=REGION)

    with pytest.raises(AnsibleFailJson) as failure:
        run(config_delivery_info.run_module)

    assert failure.value.args[0]["msg"] == "The tencentcloud-sdk-python-config package is required."


# ---------------------------------------------------------------------------
# config_recorder_info
# ---------------------------------------------------------------------------


def test_recorder_info_returns_the_documented_keys(monkeypatch, sdk):
    client = FakeConfigClient()
    _inject_sdk(monkeypatch, client)
    module_args(region=REGION)

    payload = run(config_recorder_info.run_module)

    assert payload.keys() == {"changed", "recorders", "recorder", "request_id"}
    assert payload["changed"] is False
    assert payload["recorder"] == {"Status": RECORDER_STATUS, "ResourceTypes": ["QCS::CVM::Instance", "QCS::VPC::VPC"]}
    assert payload["recorders"] == [payload["recorder"]]
    assert payload["request_id"] == REQUEST_ID


def test_recorder_info_reports_an_empty_resource_type_set(monkeypatch, sdk):
    """A recorder that monitors nothing still has to read as a list, not ``None``."""
    client = FakeConfigClient(recorder=RecorderResponse(items=[]))
    _inject_sdk(monkeypatch, client)
    module_args(region=REGION)

    payload = run(config_recorder_info.run_module)

    assert payload["recorder"]["ResourceTypes"] == []
    assert payload["recorder"]["Status"] == RECORDER_STATUS


def test_recorder_info_treats_a_missing_item_list_as_empty(monkeypatch, sdk):
    """``Items: null`` is the same answer as an empty list."""
    client = FakeConfigClient(recorder=RecorderResponse(items=[]))
    client.recorder.Items = None
    _inject_sdk(monkeypatch, client)
    module_args(region=REGION)

    payload = run(config_recorder_info.run_module)

    assert payload["recorder"]["ResourceTypes"] == []


def test_recorder_info_uses_the_config_endpoint_and_the_requested_region(monkeypatch, sdk):
    """One ``DescribeConfigRecorder`` on the Config endpoint, for the region asked for."""
    client = FakeConfigClient()
    factory_calls = _inject_sdk(monkeypatch, client)
    module_args(region=OTHER_REGION)

    run(config_recorder_info.run_module)

    assert [name for name, _request in client.requests] == ["DescribeConfigRecorder"]
    assert isinstance(client.requests[0][1], FakeRequest)
    assert factory_calls == [(sdk.credential, OTHER_REGION, sdk.profile)]
    assert sdk.endpoints == [ENDPOINT]


def test_recorder_info_reads_in_check_mode(monkeypatch, sdk):
    client = FakeConfigClient()
    _inject_sdk(monkeypatch, client)
    module_args(region=REGION, _ansible_check_mode=True)

    payload = run(config_recorder_info.run_module)

    assert payload["changed"] is False
    assert payload["recorder"]["ResourceTypes"] == ["QCS::CVM::Instance", "QCS::VPC::VPC"]
    assert len(client.requests) == 1


def test_recorder_info_maps_an_sdk_error_to_the_failure_envelope(monkeypatch, sdk):
    class FakeSdkException(Exception):
        def get_code(self):
            return "ResourceNotFound.ConfigRecorderNotFound"

        def get_request_id(self):
            return "req-config-missing"

    monkeypatch.setattr(tc, "TencentCloudSDKException", FakeSdkException)
    client = FakeConfigClient(error=FakeSdkException("recorder does not exist"))
    _inject_sdk(monkeypatch, client)
    module_args(region=REGION)

    with pytest.raises(AnsibleFailJson) as failure:
        run(config_recorder_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "recorder does not exist"
    assert payload["error_code"] == "ResourceNotFound.ConfigRecorderNotFound"
    assert payload["request_id"] == "req-config-missing"


def test_recorder_info_maps_an_unexpected_error_to_the_failure_envelope(monkeypatch, sdk):
    client = FakeConfigClient(error=RuntimeError("socket closed"))
    _inject_sdk(monkeypatch, client)
    module_args(region=REGION)

    with pytest.raises(AnsibleFailJson) as failure:
        run(config_recorder_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Unexpected Tencent Cloud API error"
    assert payload["error"] == "socket closed"


def test_recorder_info_requires_the_config_sdk_package(monkeypatch, sdk):
    _inject_sdk(monkeypatch, FakeConfigClient())
    monkeypatch.setitem(sys.modules, "tencentcloud.config.v20220802", None)
    module_args(region=REGION)

    with pytest.raises(AnsibleFailJson) as failure:
        run(config_recorder_info.run_module)

    assert failure.value.args[0]["msg"] == "The tencentcloud-sdk-python-config package is required."
