"""Main-path (run_module) unit tests for the tse_gateway_secret_key module.

Complements ``test_tse_gateway_secret_key.py`` (request-builder level) by
driving ``run_module()`` end to end against an in-memory fake TSE client
whose write operations mutate a secret-key store so post-write ``find``
refetch converges.

Scenario matrix:
* creation-validation guards (missing fields, Custom/KMS combinations)
* absent flows (missing, check mode, real delete)
* no-op idempotency and secret redaction (reveal_secret_value)
* immutable-config drift, rotation guards and authorized rotation
* status Enable/Disable transitions
* multiple-match and SDK failure paths
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_gateway_secret_key as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SECRET = {
    "SecretKeyId": "sk-1",
    "Name": "mobile-api-key",
    "SecretType": "ApiKey",
    "GenerateType": "System",
    "ResourceType": "Consumer",
    "Status": "Enable",
    "Description": "mobile api key",
    "SecretValue": "sk-live-secret-value",
}


def _secret(**overrides):
    item = copy.deepcopy(SECRET)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"gateway_id": "gateway-1", "name": "mobile-api-key"}
    params.update(overrides)
    return module_args(**params)


class FakeTseClient(object):
    """In-memory TSE client mutating a secret-key store."""

    def __init__(self, secrets=None):
        self.secrets = [copy.deepcopy(s) for s in (secrets or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeCloudNativeAPIGatewaySecretKeyList(self, request):
        self._record("DescribeCloudNativeAPIGatewaySecretKeyList", request)
        return SimpleNamespace(
            Result=SimpleNamespace(SecretKeys=[FakeResource(copy.deepcopy(s)) for s in self.secrets], TotalCount=len(self.secrets))
        )

    def DescribeCloudNativeAPIGatewaySecretKey(self, request):
        self._record("DescribeCloudNativeAPIGatewaySecretKey", request)
        secret_id = getattr(request, "SecretKeyId", None)
        item = next((s for s in self.secrets if s.get("SecretKeyId") == secret_id), None)
        return SimpleNamespace(Result=FakeResource(copy.deepcopy(item)) if item else None)

    def CreateCloudNativeAPIGatewaySecretKey(self, request):
        self._record("CreateCloudNativeAPIGatewaySecretKey", request)
        self._next += 1
        item = {k: copy.deepcopy(v) for k, v in vars(request).items() if not k.startswith("_")}
        item["SecretKeyId"] = "sk-new-%d" % self._next
        item.setdefault("Status", "Enable")
        if "SecretValue" not in item:
            item["SecretValue"] = "sk-generated-%d" % self._next
        self.secrets.append(item)
        return SimpleNamespace(Result=SimpleNamespace(ID=item["SecretKeyId"]))

    def ModifyCloudNativeAPIGatewaySecretKeyStatus(self, request):
        self._record("ModifyCloudNativeAPIGatewaySecretKeyStatus", request)
        secret_id = getattr(request, "SecretKeyId", None)
        for item in self.secrets:
            if item.get("SecretKeyId") == secret_id:
                item["Status"] = getattr(request, "Status", None)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCloudNativeAPIGatewaySecretKey(self, request):
        self._record("DeleteCloudNativeAPIGatewaySecretKey", request)
        secret_id = getattr(request, "SecretKeyId", None)
        self.secrets = [s for s in self.secrets if s.get("SecretKeyId") != secret_id]
        return SimpleNamespace(RequestId="req-fake")

    def DescribeCloudNativeAPIGatewaySecretKeyValue(self, request):
        self._record("DescribeCloudNativeAPIGatewaySecretKeyValue", request)
        return SimpleNamespace(Result="sk-plaintext-value")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# creation-validation guards
# ---------------------------------------------------------------------------


def test_create_requires_creation_fields(monkeypatch):
    fake = FakeTseClient(secrets=[])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Required for secret key creation" in exc.value.args[0]["msg"]


def test_custom_generate_requires_secret_value(monkeypatch):
    fake = FakeTseClient(secrets=[])
    _make_module(monkeypatch, fake)
    _base(state="present", secret_type="ApiKey", generate_type="Custom", resource_type="Consumer")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "secret_value is required when generate_type=Custom" in exc.value.args[0]["msg"]


def test_kms_generate_requires_kms_fields(monkeypatch):
    fake = FakeTseClient(secrets=[])
    _make_module(monkeypatch, fake)
    _base(state="present", secret_type="ApiKey", generate_type="KMS", resource_type="Consumer")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "kms_key_name and kms_key_version are required" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_secret_is_idempotent(monkeypatch):
    fake = FakeTseClient(secrets=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost-key")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["secret_key"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(secrets=[_secret()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.secrets) == 1
    assert "DeleteCloudNativeAPIGatewaySecretKey" not in [c for c, unused in fake.calls]


def test_absent_deletes_secret(monkeypatch):
    fake = FakeTseClient(secrets=[_secret()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.secrets == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteCloudNativeAPIGatewaySecretKey" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_secret(monkeypatch):
    fake = FakeTseClient(secrets=[])
    _make_module(monkeypatch, fake)
    _base(state="present", secret_type="ApiKey", generate_type="System", resource_type="Consumer")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret_key"]["Name"] == "mobile-api-key"
    assert result["secret_key"]["SecretKeyId"].startswith("sk-new-")
    assert "SecretValue" not in result["secret_key"]
    ops = [c for c, unused in fake.calls]
    assert "CreateCloudNativeAPIGatewaySecretKey" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(secrets=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", secret_type="ApiKey", generate_type="System", resource_type="Consumer")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.secrets == []
    assert "CreateCloudNativeAPIGatewaySecretKey" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-secret flows
# ---------------------------------------------------------------------------


def test_existing_secret_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseClient(secrets=[_secret()])
    _make_module(monkeypatch, fake)
    _base(state="present", secret_type="ApiKey", generate_type="System", resource_type="Consumer")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["secret_key"]["SecretKeyId"] == "sk-1"
    assert "SecretValue" not in result["secret_key"]


def test_reveal_secret_value_returns_plaintext(monkeypatch):
    fake = FakeTseClient(secrets=[_secret()])
    _make_module(monkeypatch, fake)
    _base(state="present", reveal_secret_value=True)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["secret_value"] == "sk-plaintext-value"
    ops = [c for c, unused in fake.calls]
    assert "DescribeCloudNativeAPIGatewaySecretKeyValue" in ops


def test_immutable_drift_fails_without_rotation(monkeypatch):
    fake = FakeTseClient(secrets=[_secret()])
    _make_module(monkeypatch, fake)
    _base(state="present", description="changed description")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "rotate_secret=true" in payload["msg"]
    assert payload["immutable_before"]["Description"] == "mobile api key"
    assert payload["immutable_after"]["Description"] == "changed description"


def test_rotation_requires_allow_recreate(monkeypatch):
    fake = FakeTseClient(secrets=[_secret()])
    _make_module(monkeypatch, fake)
    _base(state="present", rotate_secret=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_recreate=true" in exc.value.args[0]["msg"]


def test_authorized_rotation_recreates_secret(monkeypatch):
    fake = FakeTseClient(secrets=[_secret()])
    _make_module(monkeypatch, fake)
    _base(state="present", rotate_secret=True, allow_recreate=True, secret_type="ApiKey", generate_type="System", resource_type="Consumer")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret_key"]["SecretKeyId"] != "sk-1"
    ops = [c for c, unused in fake.calls]
    assert "CreateCloudNativeAPIGatewaySecretKey" in ops


def test_status_drift_disables_secret(monkeypatch):
    fake = FakeTseClient(secrets=[_secret(Status="Enable")])
    _make_module(monkeypatch, fake)
    _base(state="present", status="Disable")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret_key"]["Status"] == "Disable"
    ops = [c for c, unused in fake.calls]
    assert "ModifyCloudNativeAPIGatewaySecretKeyStatus" in ops


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTseClient(secrets=[_secret(), _secret(SecretKeyId="sk-2")])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE gateway secret keys matched" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCloudNativeAPIGatewaySecretKeyList(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", secret_type="ApiKey")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tse_gateway_secret_key.py)
# ---------------------------------------------------------------------------


def test_create_payload_maps_all_credential_shapes():
    p = {
        "gateway_id": "g1",
        "name": "key",
        "secret_type": "JWT",
        "generate_type": "Custom",
        "resource_type": "Consumer",
        "secret_value": "hidden",
        "jwt_credential_config": {"Algorithm": "RS256"},
        "description": None,
        "provider": None,
        "kms_key_name": None,
        "kms_key_version": None,
    }
    payload = mod.create_payload(p)
    assert payload["JWTCredentialConfig"] == {"Algorithm": "RS256"}
    assert payload["SecretValue"] == "hidden"


def test_scrub_secret_recursively_removes_material():
    value = mod.scrub_secret({
        "SecretValue": "x",
        "Nested": {"Token": "y", "ClientSecret": "z", "Name": "safe"},
        "Items": [{"Password": "z", "HeaderValue": "h"}],
    })
    assert value == {"Nested": {"Name": "safe"}, "Items": [{}]}


def test_unspecified_immutable_values_preserve_current():
    p = {
        "name": "key",
        "secret_type": None,
        "generate_type": None,
        "resource_type": None,
        "kms_key_name": None,
        "kms_key_version": None,
        "description": None,
        "provider": None,
    }
    current = {"Name": "key", "SecretType": "ApiKey", "GenerateType": "System", "ResourceType": "Consumer"}
    assert mod.desired_immutable(p, current)["SecretType"] == "ApiKey"
