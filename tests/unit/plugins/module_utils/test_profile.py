# -*- coding: utf-8 -*-
"""Unit tests for TCCLI credential profile support.

Covers ``~/.tencentcloud/default.configure`` parsing and the precedence
chain (explicit parameter > environment variable > profile section) in
:mod:`client`, plus the ``profile`` option in both shared argument specs.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest

from ansible.module_utils.basic import env_fallback

from ansible_collections.tencentcloud.cloud.plugins.module_utils import base, client
from ansible_collections.tencentcloud.cloud.plugins.module_utils import tencentcloud as legacy


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


PROFILE_BODY = """\
[default]
secret_id = akid-default
secret_key = secret-default
region = ap-guangzhou

[prod]
secret_id = akid-prod
secret_key = secret-prod
region = ap-shanghai
"""

BASE_PARAMS = {
    "secret_id": None,
    "secret_key": None,
    "token": None,
    "region": None,
    "profile": None,
    "role_arn": None,
    "role_session_name": "ansible-tencentcloud",
    "role_session_duration": 7200,
}


@pytest.fixture
def fake_sdk(monkeypatch):
    """Make client.py believe the SDK is present, with a fake Credential."""
    monkeypatch.setattr(client, "HAS_TENCENTCLOUD_SDK", True)
    monkeypatch.setattr(client, "tc_credential", FakeCredentialModule, raising=False)


@pytest.fixture
def profile_path(tmp_path, monkeypatch):
    """Point client.py at a TCCLI configuration file in a temp directory."""
    path = tmp_path / "default.configure"
    path.write_text(PROFILE_BODY)
    monkeypatch.setattr(client, "PROFILE_FILE", str(path))
    return str(path)


def test_load_profile_returns_section_keys(profile_path):
    settings = client.load_profile()
    assert settings == {
        "secret_id": "akid-default",
        "secret_key": "secret-default",
        "region": "ap-guangzhou",
    }


def test_load_profile_named_section(profile_path):
    settings = client.load_profile("prod")
    assert settings["secret_id"] == "akid-prod"
    assert settings["region"] == "ap-shanghai"


def test_load_profile_missing_file_tolerated(tmp_path, monkeypatch):
    monkeypatch.setattr(client, "PROFILE_FILE", str(tmp_path / "does-not-exist"))
    assert client.load_profile() == {}
    assert client.load_profile("prod") == {}


def test_load_profile_corrupt_file_tolerated(tmp_path, monkeypatch):
    path = tmp_path / "default.configure"
    path.write_text("this is [not = valid ini\n")
    monkeypatch.setattr(client, "PROFILE_FILE", str(path))
    assert client.load_profile() == {}


def test_load_profile_unknown_section(profile_path):
    assert client.load_profile("no-such-profile") == {}


def test_credentials_from_profile(fake_sdk, profile_path):
    credential = client.create_credential(FakeModule(dict(BASE_PARAMS)))
    assert credential.secret_id == "akid-default"
    assert credential.secret_key == "secret-default"


def test_named_profile_selection(fake_sdk, profile_path):
    params = dict(BASE_PARAMS, profile="prod")
    module = FakeModule(params)
    credential = client.create_credential(module)
    assert credential.secret_id == "akid-prod"
    assert credential.secret_key == "secret-prod"
    assert module.params["region"] == "ap-shanghai"


def test_explicit_params_beat_profile(fake_sdk, profile_path):
    params = dict(
        BASE_PARAMS,
        secret_id="akid-param",
        secret_key="secret-param",
        region="ap-beijing",
    )
    module = FakeModule(params)
    credential = client.create_credential(module)
    assert credential.secret_id == "akid-param"
    assert credential.secret_key == "secret-param"
    assert module.params["region"] == "ap-beijing"


def test_env_var_beats_profile(fake_sdk, profile_path, monkeypatch):
    """Emulate the AnsibleModule env fallback layer above the profile.

    AnsibleModule folds environment variables into params before our code
    runs; apply the same ``env_fallback`` resolution here and assert the
    profile only supplies what is still missing.
    """
    monkeypatch.setenv("TENCENTCLOUD_SECRET_ID", "akid-env")
    monkeypatch.setenv("TENCENTCLOUD_SECRET_KEY", "secret-env")
    params = dict(BASE_PARAMS)
    params["secret_id"] = env_fallback("TENCENTCLOUD_SECRET_ID")
    params["secret_key"] = env_fallback("TENCENTCLOUD_SECRET_KEY")
    module = FakeModule(params)
    credential = client.create_credential(module)
    assert credential.secret_id == "akid-env"
    assert credential.secret_key == "secret-env"
    # The profile still supplies what the environment did not.
    assert module.params["region"] == "ap-guangzhou"


def test_profile_not_read_when_params_complete(fake_sdk, monkeypatch):
    """A missing/corrupt profile file must not affect modules that do not use it."""

    def explode(*args, **kwargs):
        raise AssertionError("profile file must not be parsed")

    monkeypatch.setattr(client, "load_profile", explode)
    params = dict(
        BASE_PARAMS,
        secret_id="akid-param",
        secret_key="secret-param",
        region="ap-beijing",
    )
    credential = client.create_credential(FakeModule(params))
    assert credential.secret_id == "akid-param"


def test_region_from_profile(fake_sdk, profile_path):
    module = FakeModule(dict(BASE_PARAMS))
    client.create_credential(module)
    # Resolved regions are written back so modules reading
    # module.params["region"] directly stay unaware of profiles.
    assert module.params["region"] == "ap-guangzhou"


def test_region_param_beats_profile(fake_sdk, profile_path):
    module = FakeModule(dict(BASE_PARAMS, region="ap-nanjing"))
    assert client.resolve_region(module) == "ap-nanjing"
    assert module.params["region"] == "ap-nanjing"


def test_region_missing_everywhere_fails_clearly(fake_sdk, tmp_path, monkeypatch):
    monkeypatch.setattr(client, "PROFILE_FILE", str(tmp_path / "does-not-exist"))
    module = FakeModule(
        dict(BASE_PARAMS, secret_id="akid-param", secret_key="secret-param")
    )
    with pytest.raises(AnsibleFailJson):
        client.create_credential(module)
    message = module.failures[0]["msg"]
    assert "region" in message
    assert "TENCENTCLOUD_REGION" in message
    assert "default.configure" in message


def test_credentials_missing_everywhere_fails_clearly(fake_sdk, tmp_path, monkeypatch):
    monkeypatch.setattr(client, "PROFILE_FILE", str(tmp_path / "does-not-exist"))
    module = FakeModule(dict(BASE_PARAMS, region="ap-guangzhou"))
    with pytest.raises(AnsibleFailJson):
        client.create_credential(module)
    message = module.failures[0]["msg"]
    assert "secret_id" in message
    assert "TENCENTCLOUD_" in message
    assert "default.configure" in message


def test_base_argument_spec_profile_and_region():
    spec = base.base_argument_spec()
    assert spec["profile"]["type"] == "str"
    assert spec["profile"]["fallback"] == (env_fallback, ["TENCENTCLOUD_PROFILE"])
    assert "required" not in spec["profile"]
    # Region is no longer hard-required; the failure surfaces at credential
    # build time when no source provides it.
    assert "required" not in spec["region"]
    assert spec["region"]["fallback"] == (env_fallback, ["TENCENTCLOUD_REGION"])


def test_legacy_argument_spec_profile_and_region():
    spec = legacy.tencentcloud_argument_spec()
    assert spec["profile"]["type"] == "str"
    assert spec["profile"]["fallback"] == (env_fallback, ["TENCENTCLOUD_PROFILE"])
    assert "required" not in spec["region"]
    assert spec["region"]["fallback"] == (env_fallback, ["TENCENTCLOUD_REGION"])
