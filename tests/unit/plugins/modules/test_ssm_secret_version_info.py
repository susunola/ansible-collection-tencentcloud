# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for the ssm_secret_version_info read module.

The module lists version metadata, and reads secret material only when
``include_secret_value=true`` is asked for explicitly. That gate is the point
of the module, so it is asserted in both directions: the default run must not
call ``GetSecretValue`` at all, and the opt-in run must return the value and
carry the request id separately. The two guard rails around it -- a version id
is required to read a value, and encryption response options are meaningless
without one -- are asserted too, because a guard that quietly stopped firing
would leave a caller believing they had requested an encrypted response.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.modules import ssm_secret_version_info as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

VERSIONS = [
    {"VersionId": "v1", "CreateTime": "2026-01-01 00:00:00", "SecretName": "prod/database"},
    {"VersionId": "v2", "CreateTime": "2026-02-01 00:00:00", "SecretName": "prod/database"},
]

SECRET = {
    "SecretName": "prod/database",
    "VersionId": "v2",
    "SecretString": "correct-horse-battery-staple",
    "RequestId": "req-value",
}


class FakeSsmClient(object):
    """Records every call and returns canned SSM responses."""

    def __init__(self, versions=None, secret=None):
        self.versions = [dict(item) for item in (versions if versions is not None else VERSIONS)]
        self.secret = dict(secret if secret is not None else SECRET)
        self.calls = []

    def ListSecretVersionIds(self, request):
        self.calls.append(("ListSecretVersionIds", request))
        return FakeResource({"Versions": [FakeResource(item) for item in self.versions],
                             "RequestId": "req-list"})

    def GetSecretValue(self, request):
        self.calls.append(("GetSecretValue", request))
        return FakeResource(self.secret)

    def operations(self):
        return [name for name, _request in self.calls]


def _wire(monkeypatch, client):
    """Point the module at the fake client and a no-op SDK check."""
    monkeypatch.setattr(mod.TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load",
                        lambda: (FakeModels(), SimpleNamespace(SsmClient=object())))
    monkeypatch.setattr(mod.TencentCloudModule, "create_client",
                        lambda self, cls, endpoint: client)


# ---------------------------------------------------------------------------
# listing metadata
# ---------------------------------------------------------------------------

def test_listing_returns_every_version(monkeypatch):
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database")
    result = run(mod.run_module)

    assert result["changed"] is False
    assert [item["VersionId"] for item in result["versions"]] == ["v1", "v2"]
    assert result["request_id"] == "req-list"
    assert client.operations() == ["ListSecretVersionIds"]


def test_listing_sends_the_secret_name(monkeypatch):
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database")
    run(mod.run_module)
    request = client.calls[0][1]
    assert request.SecretName == "prod/database"


def test_listing_with_a_version_id_filters_the_result(monkeypatch):
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database", version_id="v2")
    result = run(mod.run_module)

    assert [item["VersionId"] for item in result["versions"]] == ["v2"]
    # Filtering is local: the API call is the same list request.
    assert client.operations() == ["ListSecretVersionIds"]


def test_listing_an_absent_version_id_returns_nothing(monkeypatch):
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database", version_id="v9")
    result = run(mod.run_module)
    assert result["versions"] == []


def test_listing_a_secret_with_no_versions_is_empty(monkeypatch):
    client = FakeSsmClient(versions=[])
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database")
    result = run(mod.run_module)
    assert result["versions"] == []
    assert result["request_id"] == "req-list"


def test_listing_never_reads_secret_material(monkeypatch):
    """The default run must not call GetSecretValue at all. The gate is the
    module's reason to exist, and a regression here would put secret material
    into a task result the user never asked for."""
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database")
    result = run(mod.run_module)
    assert "GetSecretValue" not in client.operations()
    assert "secret_value" not in result


# ---------------------------------------------------------------------------
# reading the value on request
# ---------------------------------------------------------------------------

def test_include_secret_value_returns_the_material(monkeypatch):
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database", version_id="v2", include_secret_value=True)
    result = run(mod.run_module)

    assert result["changed"] is False
    assert result["secret_value"]["SecretString"] == "correct-horse-battery-staple"
    assert result["secret_value"]["VersionId"] == "v2"
    assert client.operations() == ["GetSecretValue"]


def test_include_secret_value_reports_the_request_id_separately(monkeypatch):
    """RequestId is lifted out of the payload rather than left inside it, so
    the returned secret_value is the secret and nothing else."""
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database", version_id="v2", include_secret_value=True)
    result = run(mod.run_module)

    assert result["request_id"] == "req-value"
    assert "RequestId" not in result["secret_value"]


def test_include_secret_value_sends_the_requested_version(monkeypatch):
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database", version_id="SSM_Current", include_secret_value=True)
    run(mod.run_module)
    request = client.calls[0][1]
    assert request.SecretName == "prod/database"
    assert request.VersionId == "SSM_Current"


def test_encryption_options_are_sent_when_asked_for(monkeypatch):
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database", version_id="v2", include_secret_value=True,
                encryption_public_key="-----BEGIN PUBLIC KEY-----",
                encryption_algorithm="RSA_OAEP_SHA_256")
    run(mod.run_module)
    request = client.calls[0][1]
    assert request.EncryptionPublicKey == "-----BEGIN PUBLIC KEY-----"
    assert request.EncryptionAlgorithm == "RSA_OAEP_SHA_256"


# ---------------------------------------------------------------------------
# guard rails
# ---------------------------------------------------------------------------

def test_include_secret_value_requires_a_version_id(monkeypatch):
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database", include_secret_value=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "version_id is required" in exc.value.args[0]["msg"]
    assert client.calls == []


def test_encryption_public_key_requires_include_secret_value(monkeypatch):
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database", encryption_public_key="-----BEGIN PUBLIC KEY-----")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "encryption response options require include_secret_value=true" in exc.value.args[0]["msg"]
    assert client.calls == []


def test_encryption_algorithm_requires_include_secret_value(monkeypatch):
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database", encryption_algorithm="RSA_OAEP_SHA_256")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "encryption response options require include_secret_value=true" in exc.value.args[0]["msg"]


def test_secret_name_is_required(monkeypatch):
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "secret_name" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failures
# ---------------------------------------------------------------------------

def test_sdk_error_is_surfaced(monkeypatch):
    client = FakeSsmClient()

    def boom(request):
        raise RuntimeError("AuthFailure.SignatureExpire")

    client.GetSecretValue = boom
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database", version_id="v2", include_secret_value=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["failed"] is True
    assert "AuthFailure.SignatureExpire" in str(payload)


# ---------------------------------------------------------------------------
# request builders
# ---------------------------------------------------------------------------

def test_list_request_carries_the_secret_name():
    request = mod.list_request(FakeModels(), "prod/database")
    assert request.SecretName == "prod/database"


def test_value_request_omits_absent_encryption_options():
    request = mod.value_request(FakeModels(), {
        "secret_name": "prod/database", "version_id": "v2",
        "encryption_public_key": None, "encryption_algorithm": None})
    assert request.SecretName == "prod/database"
    assert request.VersionId == "v2"
    assert not hasattr(request, "EncryptionPublicKey")
    assert not hasattr(request, "EncryptionAlgorithm")
