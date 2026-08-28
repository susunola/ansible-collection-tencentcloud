"""Unit tests for the unified SDK client factory (STS AssumeRole support)."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type
import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import base, client


class AnsibleFailJson(Exception):
    pass


class FakeModule(object):
    def __init__(self, params):
        self.params = params
        self.failures = []

    def fail_json(self, **kwargs):
        self.failures.append(kwargs)
        raise AnsibleFailJson(kwargs.get("msg"))


class FakeCredential(object):
    def __init__(self, secret_id, secret_key, token=None):
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.token = token


class FakeCredentialModule(object):
    Credential = FakeCredential


class FakeTempCredentials(object):
    def __init__(self, tmp_secret_id="tmp-id", tmp_secret_key="tmp-key", token="tmp-token"):
        self.TmpSecretId = tmp_secret_id
        self.TmpSecretKey = tmp_secret_key
        self.Token = token


class FakeAssumeRoleResponse(object):
    def __init__(self, credentials=None):
        self.Credentials = credentials or FakeTempCredentials()


class FakeRequest(object):
    pass


class FakeModels(object):
    AssumeRoleRequest = FakeRequest


class FakeStsClient(object):
    def __init__(self, credential, region, profile=None):
        self.credential = credential
        self.region = region
        self.profile = profile
        self.requests = []

    def AssumeRole(self, request):
        self.requests.append(request)
        return FakeAssumeRoleResponse()


BASE_PARAMS = {
    "secret_id": "akid-test",
    "secret_key": "secret-test",
    "token": None,
    "region": "ap-guangzhou",
    "role_arn": None,
    "role_session_name": "ansible-tencentcloud",
    "role_session_duration": 7200,
    "endpoint": None,
    "timeout": 60,
}


@pytest.fixture
def fake_sdk(monkeypatch):
    """Make client.py believe the SDK is present, with a fake Credential."""
    monkeypatch.setattr(client, "HAS_TENCENTCLOUD_SDK", True)
    monkeypatch.setattr(client, "tc_credential", FakeCredentialModule, raising=False)


def test_base_credential_without_role_arn(fake_sdk):
    module = FakeModule(dict(BASE_PARAMS))
    credential = client.create_credential(module)
    assert isinstance(credential, FakeCredential)
    assert credential.secret_id == "akid-test"
    assert credential.secret_key == "secret-test"
    assert credential.token is None


def test_base_credential_passes_token(fake_sdk):
    params = dict(BASE_PARAMS, token="session-token")
    credential = client.create_credential(FakeModule(params))
    assert credential.token == "session-token"


def test_role_arn_unset_never_calls_sts(fake_sdk, monkeypatch):
    def explode(module, credential):
        raise AssertionError("STS must not be called without role_arn")

    monkeypatch.setattr(client, "_assume_role", explode)
    client.create_credential(FakeModule(dict(BASE_PARAMS)))


def test_missing_secrets_fail_json(fake_sdk):
    module = FakeModule(dict(BASE_PARAMS, secret_id=None))
    with pytest.raises(AnsibleFailJson):
        client.create_credential(module)
    assert module.failures


def test_assume_role_returns_temporary_credential(fake_sdk, monkeypatch):
    captured = {}

    def fake_assume_role(module, base_credential):
        captured["base_credential"] = base_credential
        return FakeAssumeRoleResponse(
            FakeTempCredentials("tmp-akid", "tmp-secret", "tmp-token")
        )

    monkeypatch.setattr(client, "_assume_role", fake_assume_role)
    params = dict(BASE_PARAMS, role_arn="qcs::cam::uin/1:roleName/ops")
    credential = client.create_credential(FakeModule(params))

    assert isinstance(captured["base_credential"], FakeCredential)
    assert captured["base_credential"].secret_id == "akid-test"
    assert credential.secret_id == "tmp-akid"
    assert credential.secret_key == "tmp-secret"
    assert credential.token == "tmp-token"


def test_build_assume_role_request():
    request = client.build_assume_role_request(
        FakeModels, "qcs::cam::uin/1:roleName/ops", "ansible-tencentcloud", 7200
    )
    assert request.RoleArn == "qcs::cam::uin/1:roleName/ops"
    assert request.RoleSessionName == "ansible-tencentcloud"
    assert request.DurationSeconds == 7200


def test_assume_role_wires_sts_client(fake_sdk, monkeypatch):
    """_assume_role must build the request from module params and call AssumeRole."""
    seen = {}

    class RecordingStsClient(FakeStsClient):
        def __init__(self, credential, region, profile=None):
            super().__init__(credential, region, profile)
            seen["credential"] = credential
            seen["region"] = region
            seen["profile"] = profile

        def AssumeRole(self, request):
            seen["request"] = request
            return super().AssumeRole(request)

    fake_sts_module = type("sts_client", (), {"StsClient": RecordingStsClient})
    monkeypatch.setattr(client, "_load_sts", lambda: (FakeModels, fake_sts_module))
    monkeypatch.setattr(
        client, "create_client_profile", lambda module, endpoint: ("profile", endpoint)
    )
    params = dict(
        BASE_PARAMS, role_arn="qcs::cam::uin/1:roleName/ops", role_session_duration=3600
    )
    base_credential = FakeCredential("akid-test", "secret-test")

    response = client._assume_role(FakeModule(params), base_credential)

    assert isinstance(response, FakeAssumeRoleResponse)
    assert seen["credential"] is base_credential
    assert seen["region"] == "ap-guangzhou"
    assert seen["profile"] == ("profile", "sts.tencentcloudapi.com")
    assert seen["request"].RoleArn == "qcs::cam::uin/1:roleName/ops"
    assert seen["request"].RoleSessionName == "ansible-tencentcloud"
    assert seen["request"].DurationSeconds == 3600


def test_base_argument_spec_role_options():
    spec = base.base_argument_spec()
    assert spec["role_arn"]["type"] == "str"
    assert "required" not in spec["role_arn"]
    assert spec["role_session_name"]["default"] == "ansible-tencentcloud"
    assert spec["role_session_duration"]["type"] == "int"
    assert spec["role_session_duration"]["default"] == 7200


def test_maybe_assume_role_passthrough_without_role_arn(fake_sdk, monkeypatch):
    def explode(module, credential):
        raise AssertionError("STS must not be called without role_arn")

    monkeypatch.setattr(client, "_assume_role", explode)
    triple = client.maybe_assume_role(
        FakeModule(dict(BASE_PARAMS)), "akid-test", "secret-test", "session-token"
    )
    assert triple == ("akid-test", "secret-test", "session-token")


def test_maybe_assume_role_returns_temporary_triple(fake_sdk, monkeypatch):
    captured = {}

    def fake_assume_role(module, base_credential):
        captured["base_credential"] = base_credential
        return FakeAssumeRoleResponse(
            FakeTempCredentials("tmp-akid", "tmp-secret", "tmp-token")
        )

    monkeypatch.setattr(client, "_assume_role", fake_assume_role)
    params = dict(BASE_PARAMS, role_arn="qcs::cam::uin/1:roleName/ops")
    triple = client.maybe_assume_role(
        FakeModule(params), "akid-test", "secret-test", None
    )
    assert isinstance(captured["base_credential"], FakeCredential)
    assert captured["base_credential"].secret_id == "akid-test"
    assert triple == ("tmp-akid", "tmp-secret", "tmp-token")


class FakeClientProfile(object):
    """Minimal stand-in for ``tencentcloud.common.profile.ClientProfile``.

    ``client.py`` builds a real ``ClientProfile`` through the SDK import;
    unit tests replace the module-level reference so we can assert the
    fields the factory sets without pulling the SDK into the test path.
    """

    def __init__(self):
        self.httpProfile = None
        self.language = None
        self.request_client = None


class FakeHttpProfile(object):
    """Minimal stand-in for ``tencentcloud.common.profile.HttpProfile``.

    ``create_client_profile`` assigns ``endpoint`` and ``reqTimeout`` on it;
    attributes are freely assignable, mirroring the real SDK class.
    """

    pass


def test_create_client_profile_sets_user_agent(fake_sdk, monkeypatch):
    """The user_agent parameter must reach the SDK request_client field.

    Regression: the original implementation had a no-op branch that set
    ``language`` again instead of ``request_client``, so a custom
    User-Agent never left the profile.
    """
    monkeypatch.setattr(client, "ClientProfile", FakeClientProfile, raising=False)
    monkeypatch.setattr(client, "HttpProfile", FakeHttpProfile, raising=False)
    module = FakeModule(
        dict(BASE_PARAMS, user_agent="ansible-collection.susunola.tencentcloud")
    )
    profile = client.create_client_profile(module, "vpc.tencentcloudapi.com")
    assert isinstance(profile, FakeClientProfile)
    assert profile.request_client == "ansible-collection.susunola.tencentcloud"
    assert profile.httpProfile.endpoint == "vpc.tencentcloudapi.com"
    assert profile.language == "en-US"


def test_create_client_profile_default_user_agent(fake_sdk, monkeypatch):
    """Without an explicit user_agent, the shared default must be used."""
    monkeypatch.setattr(client, "ClientProfile", FakeClientProfile, raising=False)
    monkeypatch.setattr(client, "HttpProfile", FakeHttpProfile, raising=False)
    params = dict(BASE_PARAMS)
    params["user_agent"] = base.base_argument_spec()["user_agent"]["default"]
    profile = client.create_client_profile(FakeModule(params), "vpc.tencentcloudapi.com")
    assert profile.request_client == "ansible-collection.susunola.tencentcloud"


def test_base_argument_spec_user_agent_default_matches_sdk_regexp():
    """The default UA must be accepted by the SDK's request_client regexp.

    The SDK only forwards ``ClientProfile.request_client`` when it matches
    ``^[0-9a-zA-Z-_,;.]+$`` and is at most 128 chars; a value with ``/``
    (the historical default) is silently dropped with a warning.
    """
    default = base.base_argument_spec()["user_agent"]["default"]
    assert "/" not in default
    assert len(default) <= 128
    import re
    assert re.match(r"^[0-9a-zA-Z-_,;.]+$", default)


def test_require_sdk_fails_when_sdk_unavailable(monkeypatch):
    module = FakeModule(dict(BASE_PARAMS))
    monkeypatch.setattr(client, "HAS_TENCENTCLOUD_SDK", False)
    with pytest.raises(AnsibleFailJson):
        client.require_sdk(module)
    assert module.failures
    assert "tencentcloud-sdk-python" in module.failures[0]["msg"]


def test_create_client_wires_credential_region_and_profile(fake_sdk, monkeypatch):
    seen = {}

    class _Client(object):
        def __init__(self, credential, region, profile):
            seen["credential"] = credential
            seen["region"] = region
            seen["profile"] = profile

    monkeypatch.setattr(client, "create_credential", lambda module: "cred")
    monkeypatch.setattr(client, "create_client_profile", lambda module, endpoint: "profile")
    params = dict(BASE_PARAMS)
    params["region"] = "ap-shanghai"
    result = client.create_client(FakeModule(params), _Client, "vpc.tencentcloudapi.com")
    assert result is not None
    assert seen == {
        "credential": "cred",
        "region": "ap-shanghai",
        "profile": "profile",
    }
