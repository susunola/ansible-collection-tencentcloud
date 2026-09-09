"""Unit tests for the ssm_ssh_key_pair_secret write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake SSM client
whose write operations mutate the secret store, so the module's post-write
``find`` refetch converges immediately.

Scenario matrix:

* absent on a missing or already-pending-delete secret (idempotent no-op)
* absent with a live secret (check-mode dry run and the soft-delete path)
* creation when missing (ssh_key_name guard, disabled-secret creation,
  check mode, happy path)
* no-op when nothing drifts
* description and enable-state drift updates
* the immutability guards (secret type, ssh_key_name, project_id)
* restore of a pending-delete secret
* validation guard (recovery_window_days bound)
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import ssm_ssh_key_pair_secret as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SECRET = {
    "SecretName": "prod-bastion-key",
    "Description": "managed by Ansible",
    "ResourceName": "prod_bastion",
    "ProjectID": 0,
    "SecretType": 2,
    "Status": "Enabled",
}


class MissingSecret(Exception):
    """Mirror the SDK ``ResourceNotFound`` shape used for idempotent lookups."""

    def get_code(self):
        return "ResourceNotFound.NotFound"


def _secret(**overrides):
    item = copy.deepcopy(SECRET)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"secret_name": "prod-bastion-key"}
    params.update(overrides)
    return module_args(**params)


class FakeSsmClient(object):
    """In-memory SSM client mutating a small secret store."""

    def __init__(self, secret=None, missing=None):
        self.secret = copy.deepcopy(secret)
        self.missing = missing if missing is not None else secret is None
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeSecret(self, request):
        self._record("DescribeSecret", request)
        if self.secret is None and self.missing:
            raise MissingSecret("secret not found")
        return FakeResource(self.secret)

    def CreateSSHKeyPairSecret(self, request):
        self._record("CreateSSHKeyPairSecret", request)
        self.secret = {
            "SecretName": getattr(request, "SecretName", None),
            "Description": getattr(request, "Description", None),
            "ResourceName": getattr(request, "SSHKeyName", None),
            "ProjectID": getattr(request, "ProjectId", None),
            "SecretType": 2,
            "Status": "Enabled",
        }
        return SimpleNamespace(SSHKeyID="skey-created-001", RequestId="req-fake")

    def UpdateDescription(self, request):
        self._record("UpdateDescription", request)
        if self.secret is not None:
            self.secret["Description"] = getattr(request, "Description", None)
        return SimpleNamespace(RequestId="req-fake")

    def EnableSecret(self, request):
        self._record("EnableSecret", request)
        if self.secret is not None:
            self.secret["Status"] = "Enabled"
        return SimpleNamespace(RequestId="req-fake")

    def DisableSecret(self, request):
        self._record("DisableSecret", request)
        if self.secret is not None:
            self.secret["Status"] = "Disabled"
        return SimpleNamespace(RequestId="req-fake")

    def RestoreSecret(self, request):
        self._record("RestoreSecret", request)
        if self.secret is not None:
            self.secret["Status"] = "Enabled"
        return SimpleNamespace(RequestId="req-fake")

    def DeleteSecret(self, request):
        self._record("DeleteSecret", request)
        if self.secret is not None:
            self.secret["Status"] = "PendingDelete"
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(SsmClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _ops(fake):
    return [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_secret_is_idempotent(monkeypatch):
    fake = FakeSsmClient(secret=None)
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["secret"] is None
    assert _ops(fake) == ["DescribeSecret"]


def test_absent_pending_delete_secret_is_idempotent(monkeypatch):
    fake = FakeSsmClient(secret=_secret(Status="PendingDelete"))
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["secret"]["Status"] == "PendingDelete"
    assert "DeleteSecret" not in _ops(fake)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeSsmClient(secret=_secret())
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Status"] == "Enabled"
    assert "DeleteSecret" not in _ops(fake)


def test_absent_soft_deletes_secret(monkeypatch):
    fake = FakeSsmClient(secret=_secret())
    _make_module(monkeypatch, fake)
    _base(state="absent", recovery_window_days=3)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Status"] == "PendingDelete"
    assert fake.secret["Status"] == "PendingDelete"
    ops = _ops(fake)
    assert "DeleteSecret" in ops
    delete_request = [r for c, r in fake.calls if c == "DeleteSecret"][0]
    assert delete_request.RecoveryWindowInDays == 3


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_ssh_key_name(monkeypatch):
    fake = FakeSsmClient(secret=None)
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "ssh_key_name is required when creating" in exc.value.args[0]["msg"]


def test_create_secret(monkeypatch):
    fake = FakeSsmClient(secret=None)
    _make_module(monkeypatch, fake)
    _base(state="present", ssh_key_name="prod_bastion", description="bastion access", tags={"env": "prod"})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ssh_key_id"] == "skey-created-001"
    assert result["secret"]["Status"] == "Enabled"
    assert result["secret"]["SecretType"] == 2
    assert fake.secret["Description"] == "bastion access"
    ops = _ops(fake)
    assert ops[0] == "DescribeSecret"
    assert "CreateSSHKeyPairSecret" in ops
    create_request = [r for c, r in fake.calls if c == "CreateSSHKeyPairSecret"][0]
    assert create_request.Tags[0].TagKey == "env"
    assert create_request.Tags[0].TagValue == "prod"


def test_create_secret_created_disabled(monkeypatch):
    fake = FakeSsmClient(secret=None)
    _make_module(monkeypatch, fake)
    _base(state="present", ssh_key_name="prod_bastion", enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Status"] == "Disabled"
    ops = _ops(fake)
    assert "CreateSSHKeyPairSecret" in ops
    assert "DisableSecret" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeSsmClient(secret=None)
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", ssh_key_name="prod_bastion")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Enabled"] is True
    assert result["ssh_key_id"] is None
    assert fake.secret is None
    assert "CreateSSHKeyPairSecret" not in _ops(fake)


# ---------------------------------------------------------------------------
# existing-secret flows
# ---------------------------------------------------------------------------


def test_existing_secret_no_drift_is_idempotent(monkeypatch):
    fake = FakeSsmClient(secret=_secret())
    _make_module(monkeypatch, fake)
    _base(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["secret"]["ResourceName"] == "prod_bastion"
    assert "UpdateDescription" not in _ops(fake)
    assert "EnableSecret" not in _ops(fake)


def test_description_drift_updates(monkeypatch):
    fake = FakeSsmClient(secret=_secret())
    _make_module(monkeypatch, fake)
    _base(state="present", description="renamed description")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Description"] == "renamed description"
    assert "UpdateDescription" in _ops(fake)


def test_enable_state_drift_enables(monkeypatch):
    fake = FakeSsmClient(secret=_secret(Status="Disabled"))
    _make_module(monkeypatch, fake)
    _base(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Status"] == "Enabled"
    assert "EnableSecret" in _ops(fake)
    assert "DisableSecret" not in _ops(fake)


def test_enable_state_drift_disables(monkeypatch):
    fake = FakeSsmClient(secret=_secret(Status="Enabled"))
    _make_module(monkeypatch, fake)
    _base(state="present", enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Status"] == "Disabled"
    assert "DisableSecret" in _ops(fake)


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeSsmClient(secret=_secret())
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", description="renamed description")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.secret["Description"] == "managed by Ansible"
    assert "UpdateDescription" not in _ops(fake)


def test_restore_pending_delete_secret(monkeypatch):
    fake = FakeSsmClient(secret=_secret(Status="PendingDelete"))
    _make_module(monkeypatch, fake)
    _base(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Status"] == "Enabled"
    assert "RestoreSecret" in _ops(fake)


def test_non_ssh_secret_type_fails(monkeypatch):
    fake = FakeSsmClient(secret=_secret(SecretType=4, Description="managed by Ansible"))
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "not an SSH key-pair secret" in exc.value.args[0]["msg"]


def test_ssh_key_name_immutable_fails(monkeypatch):
    fake = FakeSsmClient(secret=_secret())
    _make_module(monkeypatch, fake)
    _base(state="present", ssh_key_name="other_bastion")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "ssh_key_name is immutable" in exc.value.args[0]["msg"]


def test_project_id_immutable_fails(monkeypatch):
    fake = FakeSsmClient(secret=_secret(ProjectID=42))
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "project_id is immutable" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# validation / failure paths
# ---------------------------------------------------------------------------


def test_recovery_window_out_of_range_fails(monkeypatch):
    fake = FakeSsmClient(secret=None)
    _make_module(monkeypatch, fake)
    _base(state="absent", recovery_window_days=31)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "recovery_window_days must be between 0 and 30" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeSecret(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", ssh_key_name="prod_bastion")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_ssm_ssh_key_pair_secret.py)
# ---------------------------------------------------------------------------


class LegacyValue(object):
    pass


class LegacyModels(object):
    CreateSSHKeyPairSecretRequest = LegacyValue
    DescribeSecretRequest = LegacyValue
    Tag = LegacyValue


def test_create_request_maps_key_metadata_without_private_material():
    value = mod.create_request(
        LegacyModels,
        {
            "secret_name": "bastion",
            "project_id": 0,
            "description": "key",
            "kms_key_id": None,
            "tags": {"env": "prod"},
            "ssh_key_name": "bastion_key",
            "kms_hsm_cluster_id": None,
            "encrypt_type": 0,
        },
    )
    assert value.SecretName == "bastion"
    assert value.SSHKeyName == "bastion_key"
    assert value.Tags[0].TagKey == "env"
    assert not hasattr(value, "PrivateKey")


def test_comparable_requires_ssh_secret_type_and_stable_identity():
    value = mod.comparable({"SecretName": "bastion", "ResourceName": "bastion_key", "ProjectID": 3, "SecretType": 2, "Status": "Disabled"})
    assert value == {"SecretName": "bastion", "Description": "", "ResourceName": "bastion_key", "ProjectID": 3, "SecretType": 2, "Enabled": False}
    assert mod.request(LegacyModels, "DescribeSecretRequest", SecretName="bastion").SecretName == "bastion"
