"""Unit tests for the ssm_parameter lookup plugin helpers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest

from ansible.errors import AnsibleError

from ansible_collections.tencentcloud.cloud.plugins.lookup import ssm_parameter as lookup_mod
from ansible_collections.tencentcloud.cloud.plugins.lookup.ssm_parameter import (
    LookupModule,
    build_get_secret_value_request,
    extract_value,
    get_secret_value,
    sdk_error_message,
)


class FakeRequest(object):
    pass


class FakeModels(object):
    GetSecretValueRequest = FakeRequest


class FakeCredentialModule(object):
    class Credential(object):
        def __init__(self, secret_id, secret_key, token=None):
            self.secret_id = secret_id
            self.secret_key = secret_key
            self.token = token


class FakeResponse(object):
    def __init__(self, secret_string=None, secret_binary=None):
        self.SecretString = secret_string
        self.SecretBinary = secret_binary
        self.RequestId = "req-1"


class FakeClient(object):
    def __init__(self, values):
        self.values = values
        self.requests = []

    def GetSecretValue(self, request):
        self.requests.append(request)
        return self.values[request.SecretName]


def test_build_get_secret_value_request_defaults_to_current_version():
    request = build_get_secret_value_request(FakeModels, "db-password")
    assert request.SecretName == "db-password"
    assert request.VersionId == "SSM_Current"


def test_extract_value_prefers_secret_string():
    assert extract_value(FakeResponse(secret_string="s3cr3t")) == "s3cr3t"


def test_extract_value_falls_back_to_secret_binary():
    assert extract_value(FakeResponse(secret_binary="YmluYXJ5")) == "YmluYXJ5"


def test_get_secret_value_calls_client():
    client = FakeClient({"db-password": FakeResponse(secret_string="s3cr3t")})
    assert get_secret_value(client, FakeModels, "db-password") == "s3cr3t"
    assert client.requests[0].SecretName == "db-password"


def test_sdk_error_message_includes_code_and_request_id():
    class FakeSdkError(Exception):
        def get_code(self):
            return "ResourceNotFound"

        def get_request_id(self):
            return "req-7"

    message = sdk_error_message("GetSecretValue(db-password)", FakeSdkError("missing"))
    assert "GetSecretValue(db-password) failed" in message
    assert "ResourceNotFound" in message
    assert "req-7" in message


def _lookup(options, client, monkeypatch):
    monkeypatch.setattr(lookup_mod, "HAS_TENCENTCLOUD_SDK", True)
    monkeypatch.setattr(lookup_mod, "ssm_models", FakeModels)
    monkeypatch.setattr(lookup_mod, "tc_credential", FakeCredentialModule)
    plugin = LookupModule()
    plugin.set_options = lambda **kwargs: None
    plugin.get_option = options.get
    plugin._create_client = lambda credential, region: client
    return plugin


BASE_OPTIONS = {
    "secret_id": "id",
    "secret_key": "key",
    "token": None,
    "region": "ap-guangzhou",
    "with_decryption": True,
    "profile": None,
}


def test_run_uses_profile_credentials_and_region(monkeypatch):
    monkeypatch.setattr(
        lookup_mod, "load_profile",
        lambda profile=None: {
            "secret_id": "akid-prod",
            "secret_key": "secret-prod",
            "region": "ap-shanghai",
        },
    )
    options = dict(
        BASE_OPTIONS, secret_id=None, secret_key=None, region=None, profile="prod"
    )
    seen = {}

    def create_client(credential, region):
        seen["region"] = region
        seen["secret_id"] = credential.secret_id
        return FakeClient({"db-password": FakeResponse(secret_string="s3cr3t")})

    plugin = _lookup(options, FakeClient({}), monkeypatch)
    plugin._create_client = create_client
    assert plugin.run(["db-password"]) == ["s3cr3t"]
    assert seen["secret_id"] == "akid-prod"
    assert seen["region"] == "ap-shanghai"


def test_run_explicit_options_skip_profile(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("profile file must not be read")

    monkeypatch.setattr(lookup_mod, "load_profile", explode)
    client = FakeClient({"db-password": FakeResponse(secret_string="s3cr3t")})
    plugin = _lookup(dict(BASE_OPTIONS), client, monkeypatch)
    assert plugin.run(["db-password"]) == ["s3cr3t"]


def test_run_returns_values_in_term_order(monkeypatch):
    client = FakeClient({
        "db-password": FakeResponse(secret_string="s3cr3t"),
        "api-token": FakeResponse(secret_string="tok"),
    })
    plugin = _lookup(dict(BASE_OPTIONS), client, monkeypatch)
    result = plugin.run(["db-password", "api-token", "region=ap-guangzhou"])
    assert result == ["s3cr3t", "tok"]
    assert [r.SecretName for r in client.requests] == ["db-password", "api-token"]


def test_run_returns_binary_values(monkeypatch):
    client = FakeClient({"bin": FakeResponse(secret_binary="YmluYXJ5")})
    plugin = _lookup(dict(BASE_OPTIONS), client, monkeypatch)
    assert plugin.run(["bin"]) == ["YmluYXJ5"]


def test_run_requires_region(monkeypatch):
    monkeypatch.setattr(lookup_mod, "load_profile", lambda profile=None: {})
    options = dict(BASE_OPTIONS, region=None)
    plugin = _lookup(options, FakeClient({}), monkeypatch)
    with pytest.raises(AnsibleError, match="region"):
        plugin.run(["db-password"])


def test_run_requires_credentials(monkeypatch):
    monkeypatch.setattr(lookup_mod, "load_profile", lambda profile=None: {})
    options = dict(BASE_OPTIONS, secret_key=None)
    plugin = _lookup(options, FakeClient({}), monkeypatch)
    with pytest.raises(AnsibleError, match="secret_id and secret_key"):
        plugin.run(["db-password"])


def test_run_missing_sdk_raises():
    saved = lookup_mod.HAS_TENCENTCLOUD_SDK
    lookup_mod.HAS_TENCENTCLOUD_SDK = False
    try:
        plugin = LookupModule()
        with pytest.raises(AnsibleError, match="tencentcloud-sdk-python-ssm"):
            plugin.run(["db-password"])
    finally:
        lookup_mod.HAS_TENCENTCLOUD_SDK = saved


def test_run_wraps_sdk_errors_with_secret_name(monkeypatch):
    class FailingClient(object):
        def GetSecretValue(self, request):
            raise ValueError("access denied")

    plugin = _lookup(dict(BASE_OPTIONS), FailingClient(), monkeypatch)
    with pytest.raises(AnsibleError, match=r"GetSecretValue\(db-password\) failed: access denied"):
        plugin.run(["db-password"])
