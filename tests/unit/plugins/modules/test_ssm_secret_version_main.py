"""Unit tests for the ssm_secret_version write module (run_module flows).

``ssm_secret_version`` manages immutable, explicitly named versions of an
SSM secret: a version is either created, absent, or - when its value
drifted and ``force_replace`` is set - deleted and recreated.

Scenario matrix:

* present without a secret value fails
* create (real, check mode)
* present no-drift idempotence (value read through GetSecretValue)
* immutable drift without force_replace fails; with force it recreates
* absent on a missing version / existing version (check-mode, real delete)
* blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import ssm_secret_version as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SECRET_NAME = "prod/database"
VERSION_ID = "release-2026-08-30"

VERSION = {
    "SecretName": SECRET_NAME,
    "VersionId": VERSION_ID,
    "SecretString": "vault-password-value",
    "SecretBinary": None,
}


def _version(**overrides):
    item = copy.deepcopy(VERSION)
    item.update(overrides)
    return item


def _v_args(**overrides):
    params = {"secret_name": SECRET_NAME, "version_id": VERSION_ID}
    params.update(overrides)
    return module_args(**params)


class FakeSsmClient(object):
    """In-memory SSM client mutating a secret-version store."""

    def __init__(self, versions=None):
        self.versions = [copy.deepcopy(v) for v in (versions or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def ListSecretVersionIds(self, request):
        self._record("ListSecretVersionIds", request)
        matches = [v for v in self.versions if v["SecretName"] == request.SecretName]
        return SimpleNamespace(Versions=[FakeResource(dict(v)) for v in matches])

    def GetSecretValue(self, request):
        self._record("GetSecretValue", request)
        for version in self.versions:
            if version["SecretName"] == request.SecretName and version["VersionId"] == request.VersionId:
                return SimpleNamespace(
                    SecretString=version.get("SecretString"),
                    SecretBinary=version.get("SecretBinary"),
                )
        return SimpleNamespace(SecretString=None, SecretBinary=None)

    def PutSecretValue(self, request):
        self._record("PutSecretValue", request)
        self.versions = [v for v in self.versions if not (v["SecretName"] == request.SecretName and v["VersionId"] == request.VersionId)]
        version = {"SecretName": request.SecretName, "VersionId": request.VersionId}
        if getattr(request, "SecretString", None) is not None:
            version["SecretString"] = request.SecretString
            version["SecretBinary"] = None
        else:
            version["SecretBinary"] = request.SecretBinary
            version["SecretString"] = None
        self.versions.append(version)
        return SimpleNamespace(VersionId=request.VersionId)

    def DeleteSecretVersion(self, request):
        self._record("DeleteSecretVersion", request)
        self.versions = [
            v for v in self.versions
            if not (v["SecretName"] == request.SecretName and v["VersionId"] == request.VersionId)
        ]
        return SimpleNamespace()


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(SsmClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_without_secret_value_fails(monkeypatch):
    fake = FakeSsmClient(versions=[])
    _make_module(monkeypatch, fake)
    _v_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "secret_string or secret_binary is required" in exc.value.args[0]["msg"]


def test_present_creates_version(monkeypatch):
    fake = FakeSsmClient(versions=[])
    _make_module(monkeypatch, fake)
    _v_args(state="present", secret_string="vault-password-value")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["version"]["VersionId"] == VERSION_ID
    assert len(fake.versions) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "ListSecretVersionIds"
    assert "PutSecretValue" in ops


def test_present_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeSsmClient(versions=[])
    _make_module(monkeypatch, fake)
    _v_args(_ansible_check_mode=True, state="present", secret_string="vault-password-value")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["version"] == {"VersionId": VERSION_ID}
    assert fake.versions == []
    assert "PutSecretValue" not in [c for c, unused in fake.calls]


def test_present_no_drift_is_idempotent(monkeypatch):
    fake = FakeSsmClient(versions=[_version()])
    _make_module(monkeypatch, fake)
    _v_args(state="present", secret_string="vault-password-value")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["version"]["VersionId"] == VERSION_ID
    ops = [c for c, unused in fake.calls]
    assert "GetSecretValue" in ops
    assert "PutSecretValue" not in ops


def test_present_binary_no_drift_is_idempotent(monkeypatch):
    fake = FakeSsmClient(versions=[_version(SecretString=None, SecretBinary="YmFzZTY0LXZhbHVl")])
    _make_module(monkeypatch, fake)
    _v_args(state="present", secret_binary="YmFzZTY0LXZhbHVl")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["version"]["VersionId"] == VERSION_ID


def test_value_drift_without_force_replace_fails(monkeypatch):
    fake = FakeSsmClient(versions=[_version()])
    _make_module(monkeypatch, fake)
    _v_args(state="present", secret_string="rotated-secret")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "secret version values are immutable" in payload["msg"]


def test_value_drift_with_force_replace_recreates(monkeypatch):
    fake = FakeSsmClient(versions=[_version()])
    _make_module(monkeypatch, fake)
    _v_args(state="present", secret_string="rotated-secret", force_replace=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["version"]["VersionId"] == VERSION_ID
    assert fake.versions[0]["SecretString"] == "rotated-secret"
    ops = [c for c, unused in fake.calls]
    assert "DeleteSecretVersion" in ops
    assert ops.count("PutSecretValue") == 1


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_on_missing_version_is_idempotent(monkeypatch):
    fake = FakeSsmClient(versions=[])
    _make_module(monkeypatch, fake)
    _v_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["version"] is None
    assert [c for c, unused in fake.calls] == ["ListSecretVersionIds"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeSsmClient(versions=[_version()])
    _make_module(monkeypatch, fake)
    _v_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["version"]["VersionId"] == VERSION_ID
    assert len(fake.versions) == 1
    assert "DeleteSecretVersion" not in [c for c, unused in fake.calls]


def test_absent_deletes_version(monkeypatch):
    fake = FakeSsmClient(versions=[_version()])
    _make_module(monkeypatch, fake)
    _v_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["version"] is None
    assert fake.versions == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteSecretVersion" in ops


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def ListSecretVersionIds(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _v_args(state="present", secret_string="s3cret")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
