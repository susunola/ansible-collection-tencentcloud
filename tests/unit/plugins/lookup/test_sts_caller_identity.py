"""Unit tests for the sts_caller_identity lookup plugin helpers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest

from ansible.errors import AnsibleError

from ansible_collections.susunola.tencentcloud.plugins.lookup import sts_caller_identity as lookup_mod
from ansible_collections.susunola.tencentcloud.plugins.lookup.sts_caller_identity import (
    LookupModule,
    assume_role,
    build_credential,
    get_caller_identity,
    sdk_error_message,
    serialize_identity,
)


class FakeRequest(object):
    pass


class FakeModels(object):
    AssumeRoleRequest = FakeRequest
    GetCallerIdentityRequest = FakeRequest


class FakeCredentialModule(object):
    class Credential(object):
        def __init__(self, secret_id, secret_key, token=None):
            self.secret_id = secret_id
            self.secret_key = secret_key
            self.token = token


class FakeIdentityResponse(object):
    AccountId = "100000000001"
    Arn = "qcs::cam::uin/100000000001:root"
    PrincipalId = "100000000001"
    Type = "RootAccount"
    UserId = "100000000001"
    RequestId = "req-1"


class FakeTemporaryCredentials(object):
    TmpSecretId = "tmp-id"
    TmpSecretKey = "tmp-key"
    Token = "tmp-token"


class FakeAssumeRoleResponse(object):
    Credentials = FakeTemporaryCredentials()


class FakeClient(object):
    def __init__(self):
        self.assume_role_requests = []
        self.caller_requests = []

    def AssumeRole(self, request):
        self.assume_role_requests.append(request)
        return FakeAssumeRoleResponse()

    def GetCallerIdentity(self, request):
        self.caller_requests.append(request)
        return FakeIdentityResponse()


def test_build_credential_with_token():
    cred = build_credential(FakeCredentialModule, "id", "key", "tok")
    assert cred.secret_id == "id"
    assert cred.token == "tok"


def test_build_credential_defaults_token_to_none():
    cred = build_credential(FakeCredentialModule, "id", "key")
    assert cred.token is None


def test_assume_role_builds_request():
    client = FakeClient()
    credentials = assume_role(client, FakeModels, "qcs::cam::uin/1:roleName/ops")
    request = client.assume_role_requests[0]
    assert request.RoleArn == "qcs::cam::uin/1:roleName/ops"
    assert request.RoleSessionName == "ansible-tencentcloud"
    assert request.DurationSeconds == 7200
    assert credentials.TmpSecretId == "tmp-id"


def test_get_caller_identity_serializes_response():
    client = FakeClient()
    identity = get_caller_identity(client, FakeModels)
    assert identity == {
        "AccountId": "100000000001",
        "Arn": "qcs::cam::uin/100000000001:root",
        "PrincipalId": "100000000001",
        "Type": "RootAccount",
        "UserId": "100000000001",
    }
    assert len(client.caller_requests) == 1


def test_serialize_identity_drops_request_id():
    assert "RequestId" not in serialize_identity(FakeIdentityResponse())


def test_sdk_error_message_includes_code_and_request_id():
    class FakeSdkError(Exception):
        def get_code(self):
            return "AuthFailure.SignatureFailure"

        def get_request_id(self):
            return "req-42"

    message = sdk_error_message("GetCallerIdentity", FakeSdkError("denied"))
    assert "GetCallerIdentity failed" in message
    assert "AuthFailure.SignatureFailure" in message
    assert "req-42" in message


def test_sdk_error_message_plain_exception():
    message = sdk_error_message("AssumeRole", ValueError("boom"))
    assert message == "AssumeRole failed: boom"


def _lookup(options, client=None, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setattr(lookup_mod, "HAS_TENCENTCLOUD_SDK", True)
        monkeypatch.setattr(lookup_mod, "sts_models", FakeModels)
        monkeypatch.setattr(lookup_mod, "tc_credential", FakeCredentialModule)
    plugin = LookupModule()
    plugin.set_options = lambda **kwargs: None
    plugin.get_option = options.get
    plugin._create_client = lambda credential: client or FakeClient()
    return plugin


BASE_OPTIONS = {
    "secret_id": "id",
    "secret_key": "key",
    "token": None,
    "region": None,
    "role_arn": None,
    "profile": None,
}


def test_run_uses_profile_credentials(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(
        lookup_mod, "load_profile",
        lambda profile=None: {"secret_id": "akid-prod", "secret_key": "secret-prod"},
    )
    options = dict(BASE_OPTIONS, secret_id=None, secret_key=None, profile="prod")
    plugin = _lookup(options, client, monkeypatch)
    result = plugin.run([])
    assert result == [serialize_identity(FakeIdentityResponse())]
    assert len(client.caller_requests) == 1


def test_run_explicit_credentials_skip_profile(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("profile file must not be read")

    monkeypatch.setattr(lookup_mod, "load_profile", explode)
    plugin = _lookup(dict(BASE_OPTIONS), FakeClient(), monkeypatch)
    assert len(plugin.run([])) == 1


def test_run_profile_supplies_only_missing_secret_key(monkeypatch):
    captured = {}

    class RecordingCredentialModule(object):
        class Credential(object):
            def __init__(self, secret_id, secret_key, token=None):
                captured["secret_id"] = secret_id
                captured["secret_key"] = secret_key

    monkeypatch.setattr(
        lookup_mod, "load_profile",
        lambda profile=None: {"secret_id": "akid-default", "secret_key": "secret-default"},
    )
    options = dict(BASE_OPTIONS, secret_key=None)
    plugin = _lookup(options, FakeClient(), monkeypatch)
    monkeypatch.setattr(lookup_mod, "tc_credential", RecordingCredentialModule)
    plugin.run([])
    assert captured["secret_id"] == "id"
    assert captured["secret_key"] == "secret-default"


def test_run_without_role(monkeypatch):
    client = FakeClient()
    plugin = _lookup(dict(BASE_OPTIONS), client, monkeypatch)
    result = plugin.run(["region=ap-guangzhou"])
    assert result == [serialize_identity(FakeIdentityResponse())]
    assert client.assume_role_requests == []
    assert len(client.caller_requests) == 1


def test_run_with_role_assumes_role_first(monkeypatch):
    client = FakeClient()
    options = dict(BASE_OPTIONS, role_arn="qcs::cam::uin/1:roleName/ops")
    plugin = _lookup(options, client, monkeypatch)
    result = plugin.run([])
    assert client.assume_role_requests[0].RoleArn == "qcs::cam::uin/1:roleName/ops"
    assert len(client.caller_requests) == 1
    assert result[0]["AccountId"] == "100000000001"


def test_run_requires_credentials(monkeypatch):
    monkeypatch.setattr(lookup_mod, "load_profile", lambda profile=None: {})
    options = dict(BASE_OPTIONS, secret_id=None)
    plugin = _lookup(options, FakeClient(), monkeypatch)
    with pytest.raises(AnsibleError, match="secret_id and secret_key"):
        plugin.run([])


def test_run_missing_sdk_raises():
    saved = lookup_mod.HAS_TENCENTCLOUD_SDK
    lookup_mod.HAS_TENCENTCLOUD_SDK = False
    try:
        plugin = LookupModule()
        with pytest.raises(AnsibleError, match="tencentcloud-sdk-python-sts"):
            plugin.run([])
    finally:
        lookup_mod.HAS_TENCENTCLOUD_SDK = saved


def test_run_wraps_sdk_errors(monkeypatch):
    class FailingClient(FakeClient):
        def GetCallerIdentity(self, request):
            raise ValueError("network down")

    plugin = _lookup(dict(BASE_OPTIONS), FailingClient(), monkeypatch)
    with pytest.raises(AnsibleError, match="GetCallerIdentity failed: network down"):
        plugin.run([])


def test_run_wraps_assume_role_errors(monkeypatch):
    class FailingClient(FakeClient):
        def AssumeRole(self, request):
            raise ValueError("no such role")

    options = dict(BASE_OPTIONS, role_arn="qcs::cam::uin/1:roleName/ops")
    plugin = _lookup(options, FailingClient(), monkeypatch)
    with pytest.raises(AnsibleError, match="AssumeRole failed: no such role"):
        plugin.run([])
