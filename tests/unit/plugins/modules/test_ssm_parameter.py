"""Unit tests for the ssm_parameter write module (helpers + run_module).

Covers the create / value-update / delete flows of
``plugins/modules/ssm_parameter.py`` with an in-memory fake SSM client whose
write operations mutate the secret store. ``find_secret`` maps a
not-found describe into ``None``, so the fake raises an SDK-style exception
with a ``ResourceNotFound`` code for absent secrets.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import ssm_parameter as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SECRET = {
    "SecretName": "prod/db",
    "Description": "production",
    "SecretType": 0,
}

WRITE_OPS = (
    "CreateSecret",
    "UpdateSecret",
    "DeleteSecret",
)


class SecretNotFound(RuntimeError):
    """SDK-style not-found exception with a ResourceNotFound code."""

    def get_code(self):
        return "ResourceNotFound.SecretNotExist"


def _secret(**overrides):
    """Return a secret fixture isolated from the shared constant."""
    secret = copy.deepcopy(SECRET)
    secret.update(overrides)
    return secret


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base params included)."""
    params = {
        "state": "present",
        "secret_name": "prod/db",
        "secret_string": None,
        "secret_binary": None,
        "description": None,
        "secret_type": 0,
        "encrypt_type": None,
        "kms_key_id": None,
        "tags": {},
        "delete_mode": "soft",
        "recovery_window_in_days": 30,
        "retries": 5,
        "waiter_delay": 5,
        "waiter_timeout": 120,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    args = dict(_params())
    args.update(extra)
    return module_args(**args)


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


class FakeSsmClient(object):
    """In-memory SSM client that mutates a small secret store."""

    def __init__(self, secrets=None):
        self.secrets = [copy.deepcopy(s) for s in (secrets or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeSecret(self, request):
        self._record("DescribeSecret", request)
        for secret in self.secrets:
            if secret["SecretName"] == request.SecretName:
                return FakeResource(dict(secret))
        raise SecretNotFound("secret does not exist")

    def CreateSecret(self, request):
        self._record("CreateSecret", request)
        self.secrets.append(
            {
                "SecretName": request.SecretName,
                "Description": getattr(request, "Description", None),
                "SecretType": getattr(request, "SecretType", 0),
            }
        )
        return SimpleNamespace()

    def UpdateSecret(self, request):
        self._record("UpdateSecret", request)
        return SimpleNamespace()

    def DeleteSecret(self, request):
        self._record("DeleteSecret", request)
        self.secrets = [s for s in self.secrets if s["SecretName"] != request.SecretName]
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeSsmClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        '_load_ssm',
        lambda: (FakeModels(), SimpleNamespace(SsmClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_find_secret_returns_serialized_metadata():
    module = FakeModule()
    client = FakeSsmClient(secrets=[_secret(), _secret(SecretName="other/db", Description="other")])
    found = mod.find_secret(module, client, FakeModels(), "prod/db")
    assert found["SecretName"] == "prod/db"
    assert found["Description"] == "production"


def test_find_secret_missing_returns_none():
    module = FakeModule()
    client = FakeSsmClient()
    assert mod.find_secret(module, client, FakeModels(), "prod/db") is None


def test_find_secret_propagates_non_not_found_errors():
    module = FakeModule()
    client = FakeSsmClient()

    def boom(request):
        raise RuntimeError("ssm api exploded")

    client.DescribeSecret = boom
    with pytest.raises(RuntimeError, match="ssm api exploded"):
        mod.find_secret(module, client, FakeModels(), "prod/db")


def test_create_sets_secret_fields():
    module = FakeModule()
    client = FakeSsmClient()
    mod._create(
        module,
        client,
        FakeModels(),
        _params(secret_string="s3cr3t", description="production", secret_type=1, encrypt_type=1, kms_key_id="kms-1"),
    )
    assert len(module.sdk_calls) == 1
    request = module.sdk_calls[0][1]
    assert request.SecretName == "prod/db"
    assert request.SecretString == "s3cr3t"
    assert request.Description == "production"
    assert request.SecretType == 1
    assert request.EncryptType == 1
    assert request.KmsKeyId == "kms-1"


def test_create_with_binary_only_omits_string():
    module = FakeModule()
    client = FakeSsmClient()
    mod._create(module, client, FakeModels(), _params(secret_binary="b64data"))
    request = module.sdk_calls[0][1]
    assert request.SecretBinary == "b64data"
    assert not hasattr(request, "SecretString")


def test_update_value_sets_given_fields():
    module = FakeModule()
    client = FakeSsmClient()
    mod._update_value(module, client, FakeModels(), "prod/db", "new-value", None)
    request = module.sdk_calls[0][1]
    assert request.SecretName == "prod/db"
    assert request.SecretString == "new-value"
    assert not hasattr(request, "SecretBinary")


def test_update_value_with_binary_sets_binary_only():
    module = FakeModule()
    client = FakeSsmClient()
    mod._update_value(module, client, FakeModels(), "prod/db", None, "b64data")
    request = module.sdk_calls[0][1]
    assert request.SecretName == "prod/db"
    assert request.SecretBinary == "b64data"
    assert not hasattr(request, "SecretString")


def test_delete_soft_uses_recovery_window():
    module = FakeModule()
    client = FakeSsmClient()
    mod._delete(module, client, FakeModels(), "prod/db", immediate=False, recovery_window_in_days=7)
    request = module.sdk_calls[0][1]
    assert request.SecretName == "prod/db"
    assert request.RecoveryWindowInDays == 7


def test_delete_immediate_zeroes_recovery_window():
    module = FakeModule()
    client = FakeSsmClient()
    mod._delete(module, client, FakeModels(), "prod/db", immediate=True, recovery_window_in_days=7)
    request = module.sdk_calls[0][1]
    assert request.RecoveryWindowInDays == 0


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_arguments_enforced(client):
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "missing required arguments" in exc.value.args[0]["msg"]


def test_secret_string_and_binary_mutually_exclusive(client):
    _run_args(secret_string="plain", secret_binary="b64")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "mutually exclusive" in exc.value.args[0]["msg"]


def test_absent_missing_secret_is_unchanged(client):
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "already absent" in result["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_absent_deletes_secret(client):
    client.secrets = [_secret()]
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "deleted" in result["msg"]
    assert result["secret"] is None
    assert any(name == "DeleteSecret" for name, request in client.calls)
    assert client.secrets == []
    delete_request = next(request for name, request in client.calls if name == "DeleteSecret")
    assert delete_request.SecretName == "prod/db"
    assert delete_request.RecoveryWindowInDays == 30


def test_absent_immediate_delete_zeroes_window(client):
    client.secrets = [_secret()]
    _run_args(state="absent", delete_mode="immediate")
    result = run(mod.run_module)
    assert result["changed"] is True
    delete_request = next(request for name, request in client.calls if name == "DeleteSecret")
    assert delete_request.RecoveryWindowInDays == 0


def test_present_create_requires_secret_value(client):
    _run_args(secret_string=None, secret_binary=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "secret_string or secret_binary is required" in exc.value.args[0]["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_creates_secret(client):
    _run_args(secret_string="s3cr3t", description="production")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "created" in result["msg"]
    assert result["secret"]["SecretName"] == "prod/db"
    assert any(name == "CreateSecret" for name, request in client.calls)
    assert len(client.secrets) == 1
    create_request = next(request for name, request in client.calls if name == "CreateSecret")
    assert create_request.SecretString == "s3cr3t"
    assert create_request.Description == "production"


def test_present_existing_is_up_to_date(client):
    client.secrets = [_secret()]
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "up to date" in result["msg"]
    assert result["secret"]["SecretName"] == "prod/db"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_updates_secret_value(client):
    client.secrets = [_secret()]
    _run_args(secret_string="rotated")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "updated" in result["msg"]
    assert any(name == "UpdateSecret" for name, request in client.calls)
    update_request = next(request for name, request in client.calls if name == "UpdateSecret")
    assert update_request.SecretName == "prod/db"
    assert update_request.SecretString == "rotated"


def test_present_value_and_description_drift_updates_value_only(client):
    # Description is create-only: the module reports the change but the only
    # write issued is the value update (lines 315-320 in the module).
    client.secrets = [_secret(Description="stale")]
    _run_args(secret_string="rotated", description="production")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "updated" in result["msg"]
    update_requests = [request for name, request in client.calls if name == "UpdateSecret"]
    assert len(update_requests) == 1
    assert update_requests[0].SecretString == "rotated"


def test_present_description_only_drift_reports_change_without_write(client):
    # Description is create-only: a pure description drift enters the update
    # branch but issues no SDK write (module lines 315-320). Pins current
    # behavior so a future fix is visible in this test.
    client.secrets = [_secret(Description="stale")]
    _run_args(description="production")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "updated" in result["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_check_mode_create_makes_no_writes(client):
    _run_args(secret_string="s3cr3t", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would create" in result["msg"]
    assert client.secrets == []
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_check_mode_update_makes_no_writes(client):
    client.secrets = [_secret()]
    _run_args(secret_string="rotated", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would update" in result["msg"]
    assert result["diff"]["before"]["SecretName"] == "prod/db"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_check_mode_delete_makes_no_writes(client):
    client.secrets = [_secret()]
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "Would delete" in result["msg"]
    assert len(client.secrets) == 1
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_sdk_error_on_describe_is_reported(client):
    def boom(request):
        raise RuntimeError("ssm api exploded")

    client.DescribeSecret = boom
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "ssm api exploded"
    assert payload["error_code"] is None
