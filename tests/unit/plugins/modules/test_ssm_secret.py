"""Unit tests for the ssm_secret write module (helpers + run_module).

Covers the create / drift-update / restore / schedule-delete flows of
``plugins/modules/ssm_secret.py`` with an in-memory fake SSM client whose
write operations mutate the secret store, so the module's post-write ``find``
refetch converges immediately. Secrets are matched by ``secret_name``
(DescribeSecret, not-found swallowed); KmsKeyId / EncryptType are immutable
after creation; a secret in PendingDelete status is restored before the
present flow reconciles description and enabled state.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import ssm_secret as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SECRET = {
    "SecretName": "prod-db",
    "Description": "managed by Ansible",
    "Status": "Enabled",
    "KmsKeyId": None,
    "SecretType": 0,
    "EncryptType": 0,
}


def _secret(**overrides):
    """API-shaped secret dict isolated from the shared constant."""
    item = copy.deepcopy(SECRET)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec."""
    params = {
        "state": "present",
        "secret_name": "prod-db",
        "description": "managed by Ansible",
        "enabled": True,
        "initial_version_id": "SSM_Current",
        "initial_secret_string": None,
        "initial_secret_binary": None,
        "kms_key_id": None,
        "kms_hsm_cluster_id": None,
        "encrypt_type": 0,
        "recovery_window_days": 7,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter (None dropped)."""
    args = dict(_params())
    args.update(extra)
    return module_args(**{k: v for k, v in args.items() if v is not None})


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or _params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class _NotFound(RuntimeError):
    """SDK-style not-found exception carrying a get_code()."""

    def get_code(self):
        return "ResourceNotFound.NotFound"


class FakeSsmClient(object):
    """In-memory SsmClient stand-in.

    Stores API-shaped secret dicts keyed by SecretName. DescribeSecret
    raises a not-found error for unknown names (find swallows it); write
    operations mutate the store so post-write refetches converge.
    """

    def __init__(self, secrets=None):
        self.secrets = [copy.deepcopy(s) for s in (secrets or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _get(self, name):
        for stored in self.secrets:
            if stored.get("SecretName") == name:
                return stored
        return None

    def DescribeSecret(self, request):
        self._record("DescribeSecret", request)
        stored = self._get(request.SecretName)
        if stored is None:
            raise _NotFound("secret not found")
        return FakeResource(dict(stored))

    def CreateSecret(self, request):
        self._record("CreateSecret", request)
        self.secrets.append(
            {
                "SecretName": request.SecretName,
                "Description": request.Description,
                "Status": "Enabled",
                "KmsKeyId": request.KmsKeyId,
                "SecretType": int(request.SecretType or 0),
                "EncryptType": int(request.EncryptType or 0),
            }
        )
        return SimpleNamespace(RequestId="req-fake")

    def UpdateDescription(self, request):
        self._record("UpdateDescription", request)
        stored = self._get(request.SecretName)
        if stored is not None:
            stored["Description"] = request.Description
        return SimpleNamespace(RequestId="req-fake")

    def EnableSecret(self, request):
        self._record("EnableSecret", request)
        stored = self._get(request.SecretName)
        if stored is not None:
            stored["Status"] = "Enabled"
        return SimpleNamespace(RequestId="req-fake")

    def DisableSecret(self, request):
        self._record("DisableSecret", request)
        stored = self._get(request.SecretName)
        if stored is not None:
            stored["Status"] = "Disabled"
        return SimpleNamespace(RequestId="req-fake")

    def RestoreSecret(self, request):
        self._record("RestoreSecret", request)
        stored = self._get(request.SecretName)
        if stored is not None:
            stored["Status"] = "Enabled"
        return SimpleNamespace(RequestId="req-fake")

    def DeleteSecret(self, request):
        self._record("DeleteSecret", request)
        stored = self._get(request.SecretName)
        if stored is not None:
            stored["Status"] = "PendingDelete"
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(SsmClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# request-builder / normalisation helper tests
# ---------------------------------------------------------------------------


def test_describe_request_fields():
    request = mod.describe_request(FakeModels(), "prod-db")
    assert request.SecretName == "prod-db"


def test_create_request_fields():
    request = mod.create_request(FakeModels(), _params(initial_secret_string="s3cret", kms_key_id="kms-1", encrypt_type=1))
    assert request.SecretName == "prod-db"
    assert request.VersionId == "SSM_Current"
    assert request.Description == "managed by Ansible"
    assert request.SecretString == "s3cret"
    assert request.SecretBinary is None
    assert request.KmsKeyId == "kms-1"
    assert request.EncryptType == 1
    assert request.SecretType == 0


def test_create_request_binary_variant():
    request = mod.create_request(FakeModels(), _params(initial_secret_string=None, initial_secret_binary="YmFzZTY0"))
    assert request.SecretString is None
    assert request.SecretBinary == "YmFzZTY0"


def test_description_request_fields():
    request = mod.description_request(FakeModels(), _params(description="rotated"))
    assert request.SecretName == "prod-db"
    assert request.Description == "rotated"


def test_state_request_selects_enable_disable_class():
    enabled = mod.state_request(FakeModels(), "prod-db", True)
    assert type(enabled).__name__ == "EnableSecretRequest"
    assert enabled.SecretName == "prod-db"
    disabled = mod.state_request(FakeModels(), "prod-db", False)
    assert type(disabled).__name__ == "DisableSecretRequest"
    assert disabled.SecretName == "prod-db"


def test_restore_request_fields():
    request = mod.restore_request(FakeModels(), "prod-db")
    assert request.SecretName == "prod-db"


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params(recovery_window_days=14))
    assert request.SecretName == "prod-db"
    assert request.RecoveryWindowInDays == 14


def test_comparable_maps_status_and_types():
    value = mod.comparable(_secret(Status="Enabled", SecretType="0", EncryptType=1, Description=""))
    assert value["SecretName"] == "prod-db"
    assert value["Description"] == ""  # falsy falls back to empty string
    assert value["KmsKeyId"] is None
    assert value["SecretType"] == 0  # string coerced to int
    assert value["EncryptType"] == 1
    assert value["Enabled"] is True


def test_comparable_disabled_status():
    assert mod.comparable(_secret(Status="Disabled"))["Enabled"] is False


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_returns_serialized_secret(monkeypatch):
    fake = FakeSsmClient([_secret()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), "prod-db")
    assert value["SecretName"] == "prod-db"
    assert value["Status"] == "Enabled"


def test_find_not_found_returns_none(monkeypatch):
    fake = FakeSsmClient([_secret()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), "ghost") is None


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_secret_name_required():
    module_args(state="present")  # no secret_name
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_mutually_exclusive_secret_material_enforced():
    module_args(secret_name="prod-db", initial_secret_string="a", initial_secret_binary="b")
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_recovery_window_above_30_fails():
    module_args(secret_name="prod-db", recovery_window_days=31)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "recovery_window_days must be between 0 and 30" in exc.value.args[0]["msg"]


def test_recovery_window_negative_fails():
    module_args(secret_name="prod-db", recovery_window_days=-1)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "recovery_window_days must be between 0 and 30" in exc.value.args[0]["msg"]


def test_present_creates_secret(monkeypatch):
    fake = FakeSsmClient()
    _make_module(monkeypatch, fake)
    _run_args(initial_secret_string="s3cret")
    result = run(mod.run_module)
    assert result["changed"] is True
    secret = result["secret"]
    assert secret["SecretName"] == "prod-db"
    assert secret["Status"] == "Enabled"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeSecret") == 2  # find + refetch
    assert names.count("CreateSecret") == 1
    create = [c for c in fake.calls if c[0] == "CreateSecret"][0][1]
    assert create.SecretString == "s3cret"
    assert create.EncryptType == 0


def test_present_requires_initial_material_when_creating(monkeypatch):
    fake = FakeSsmClient()
    _make_module(monkeypatch, fake)
    _run_args()  # no initial_secret_string / binary
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "initial_secret_string or initial_secret_binary is required when creating a secret" in exc.value.args[0]["msg"]
    assert not any("CreateSecret" == c[0] for c in fake.calls)


def test_present_create_then_disable(monkeypatch):
    fake = FakeSsmClient()
    _make_module(monkeypatch, fake)
    _run_args(initial_secret_string="s3cret", enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Status"] == "Disabled"
    names = [c[0] for c in fake.calls]
    assert names.index("CreateSecret") < names.index("DisableSecret")
    assert "EnableSecret" not in names


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeSsmClient([_secret()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["secret"]["SecretName"] == "prod-db"
    names = [c[0] for c in fake.calls]
    assert "UpdateDescription" not in names
    assert "EnableSecret" not in names
    assert "DisableSecret" not in names


def test_present_description_drift_triggers_update(monkeypatch):
    fake = FakeSsmClient([_secret(Description="old")])
    _make_module(monkeypatch, fake)
    _run_args(description="new-description")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Description"] == "new-description"
    update = [c for c in fake.calls if c[0] == "UpdateDescription"][0][1]
    assert update.Description == "new-description"


def test_present_enable_drift_triggers_enable(monkeypatch):
    fake = FakeSsmClient([_secret(Status="Disabled")])
    _make_module(monkeypatch, fake)
    _run_args(enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Status"] == "Enabled"
    names = [c[0] for c in fake.calls]
    assert names.count("EnableSecret") == 1
    assert "DisableSecret" not in names


def test_present_disable_drift_triggers_disable(monkeypatch):
    fake = FakeSsmClient([_secret()])
    _make_module(monkeypatch, fake)
    _run_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Status"] == "Disabled"
    names = [c[0] for c in fake.calls]
    assert names.count("DisableSecret") == 1


def test_present_kms_key_id_drift_fails(monkeypatch):
    fake = FakeSsmClient([_secret(KmsKeyId="kms-1")])
    _make_module(monkeypatch, fake)
    _run_args(kms_key_id="kms-2")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "kms_key_id is immutable after secret creation" in payload["msg"]
    assert payload["current_kms_key_id"] == "kms-1"
    assert not any("UpdateDescription" == c[0] for c in fake.calls)


def test_present_encrypt_type_drift_fails(monkeypatch):
    fake = FakeSsmClient([_secret(EncryptType=1)])
    _make_module(monkeypatch, fake)
    _run_args(encrypt_type=0)  # module default differs from remote
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "encrypt_type is immutable after secret creation" in payload["msg"]
    assert payload["current_encrypt_type"] == 1


def test_present_restores_pending_delete_secret(monkeypatch):
    fake = FakeSsmClient([_secret(Status="PendingDelete")])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Status"] == "Enabled"
    names = [c[0] for c in fake.calls]
    assert names.count("RestoreSecret") == 1
    restore = [c for c in fake.calls if c[0] == "RestoreSecret"][0][1]
    assert restore.SecretName == "prod-db"
    # description / enabled already match -> only the restore call is issued
    assert "UpdateDescription" not in names
    assert "EnableSecret" not in names


def test_present_restore_with_description_drift(monkeypatch):
    fake = FakeSsmClient([_secret(Status="PendingDelete", Description="stale")])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Status"] == "Enabled"
    assert result["secret"]["Description"] == "managed by Ansible"
    names = [c[0] for c in fake.calls]
    assert names.count("RestoreSecret") == 1
    assert names.count("UpdateDescription") == 1


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeSsmClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, secret_name="prod-db", initial_secret_string="s3cret")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["SecretName"] == "prod-db"  # desired reported
    assert result["secret"]["Enabled"] is True
    assert not any("CreateSecret" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeSsmClient([_secret(Description="old")])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, secret_name="prod-db", description="new")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Description"] == "old"  # pre-change state reported
    assert not any("UpdateDescription" == c[0] for c in fake.calls)


def test_absent_schedules_deletion(monkeypatch):
    fake = FakeSsmClient([_secret()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Status"] == "PendingDelete"  # post-delete refetch
    delete = [c for c in fake.calls if c[0] == "DeleteSecret"][0][1]
    assert delete.SecretName == "prod-db"
    assert delete.RecoveryWindowInDays == 7


def test_absent_uses_custom_recovery_window(monkeypatch):
    fake = FakeSsmClient([_secret()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", recovery_window_days=14)
    result = run(mod.run_module)
    assert result["changed"] is True
    delete = [c for c in fake.calls if c[0] == "DeleteSecret"][0][1]
    assert delete.RecoveryWindowInDays == 14


def test_absent_pending_delete_is_noop(monkeypatch):
    fake = FakeSsmClient([_secret(Status="PendingDelete")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["secret"]["Status"] == "PendingDelete"
    assert not any("DeleteSecret" == c[0] for c in fake.calls)


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeSsmClient([_secret()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", secret_name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["secret"] is None
    assert not any("DeleteSecret" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeSsmClient([_secret()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, secret_name="prod-db", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Status"] == "Enabled"  # pre-change state reported
    assert not any("DeleteSecret" == c[0] for c in fake.calls)
    assert len(fake.secrets) == 1


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(SsmClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args(initial_secret_string="s3cret")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"
