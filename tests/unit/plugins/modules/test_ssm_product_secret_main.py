"""Unit tests for the ssm_product_secret write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake SSM client whose
write operations mutate the secret store and whose async task reports
immediate success, so ``wait_task`` and post-write ``find`` converge at once.

Scenario matrix:

* absent on a missing secret (idempotent no-op via ResourceNotFound)
* absent on an existing secret (delete -> PendingDelete, already-pending no-op)
* restore of a PendingDelete secret
* creation when missing (missing-parameter guard, check mode, happy path with
  task wait, enabled=false create)
* no-op when nothing drifts
* drift updates (description, enable/disable, rotation)
* immutable product/instance guard
* validation guards (username prefix length, recovery window, rotation
  frequency/begin-time) and the blanket ``sdk_error_payload`` path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import ssm_product_secret as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SECRET = {
    "SecretName": "orders-db-managed",
    "Description": "managed by Ansible",
    "ProductName": "Mysql",
    "ResourceID": "cdb-xxxxxxxx",
    "Status": "Enabled",
    "RotationStatus": 0,
    "RotationFrequency": 30,
}


class NotFound(Exception):
    def get_code(self):
        return "ResourceNotFound.SecretNotExist"

    def get_request_id(self):
        return "req-notfound"


def _secret(**overrides):
    item = dict(SECRET)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {}
    params.update(overrides)
    return module_args(**params)


def _base_secret(**overrides):
    params = {"secret_name": "orders-db-managed"}
    params.update(overrides)
    return module_args(**params)


class FakeSsmClient(object):
    """In-memory SSM client mutating a small product-secret store."""

    def __init__(self, secrets=None):
        self.secrets = [dict(t) for t in (secrets or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, name):
        for item in self.secrets:
            if item.get("SecretName") == name:
                return item
        return None

    def DescribeSecret(self, request):
        self._record("DescribeSecret", request)
        item = self._find(getattr(request, "SecretName", None))
        if item is None:
            raise NotFound("secret not found")
        return FakeResource(dict(item, RequestId="req-describe"))

    def DescribeAsyncRequestInfo(self, request):
        self._record("DescribeAsyncRequestInfo", request)
        return SimpleNamespace(TaskStatus=1, Description="ok", RequestId="req-async")

    def CreateProductSecret(self, request):
        self._record("CreateProductSecret", request)
        self._next += 1
        item = {
            "SecretName": getattr(request, "SecretName", None),
            "Description": getattr(request, "Description", None) or "managed by Ansible",
            "ProductName": getattr(request, "ProductName", None),
            "ResourceID": getattr(request, "InstanceID", None),
            "Status": "Enabled",
            "RotationStatus": int(getattr(request, "EnableRotation", False)),
            "RotationFrequency": int(getattr(request, "RotationFrequency", 0) or 0),
        }
        self.secrets.append(item)
        return SimpleNamespace(FlowID=42, RequestId="req-create")

    def DeleteSecret(self, request):
        self._record("DeleteSecret", request)
        item = self._find(getattr(request, "SecretName", None))
        if item is not None:
            item["Status"] = "PendingDelete"
        return SimpleNamespace(RequestId="req-delete")

    def RestoreSecret(self, request):
        self._record("RestoreSecret", request)
        item = self._find(getattr(request, "SecretName", None))
        if item is not None:
            item["Status"] = "Enabled"
        return SimpleNamespace(RequestId="req-restore")

    def UpdateDescription(self, request):
        self._record("UpdateDescription", request)
        item = self._find(getattr(request, "SecretName", None))
        if item is not None:
            item["Description"] = getattr(request, "Description", None)
        return SimpleNamespace(RequestId="req-update-desc")

    def EnableSecret(self, request):
        self._record("EnableSecret", request)
        item = self._find(getattr(request, "SecretName", None))
        if item is not None:
            item["Status"] = "Enabled"
        return SimpleNamespace(RequestId="req-enable")

    def DisableSecret(self, request):
        self._record("DisableSecret", request)
        item = self._find(getattr(request, "SecretName", None))
        if item is not None:
            item["Status"] = "Disabled"
        return SimpleNamespace(RequestId="req-disable")

    def UpdateRotationStatus(self, request):
        self._record("UpdateRotationStatus", request)
        item = self._find(getattr(request, "SecretName", None))
        if item is not None:
            item["RotationStatus"] = int(getattr(request, "EnableRotation", False))
            item["RotationFrequency"] = getattr(request, "Frequency", None)
        return SimpleNamespace(RequestId="req-rotation")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(SsmClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_secret_is_idempotent(monkeypatch):
    fake = FakeSsmClient()
    _make_module(monkeypatch, fake)
    _base_secret(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["secret"] is None
    assert [c for c, unused in fake.calls] == ["DescribeSecret"]


def test_absent_deletes_secret_into_pending(monkeypatch):
    fake = FakeSsmClient(secrets=[_secret()])
    _make_module(monkeypatch, fake)
    _base_secret(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Status"] == "PendingDelete"
    assert fake.secrets[0]["Status"] == "PendingDelete"
    assert "DeleteSecret" in [c for c, unused in fake.calls]


def test_absent_pending_delete_is_idempotent(monkeypatch):
    fake = FakeSsmClient(secrets=[_secret(Status="PendingDelete")])
    _make_module(monkeypatch, fake)
    _base_secret(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "DeleteSecret" not in [c for c, unused in fake.calls]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeSsmClient(secrets=[_secret()])
    _make_module(monkeypatch, fake)
    _base_secret(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.secrets[0]["Status"] == "Enabled"
    assert "DeleteSecret" not in [c for c, unused in fake.calls]


def test_restore_pending_delete_secret(monkeypatch):
    fake = FakeSsmClient(secrets=[_secret(Status="PendingDelete")])
    _make_module(monkeypatch, fake)
    _base_secret(
        state="present",
        product_name="Mysql",
        instance_id="cdb-xxxxxxxx",
        username_prefix="ssmapp",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Status"] == "Enabled"
    assert fake.secrets[0]["Status"] == "Enabled"
    assert "RestoreSecret" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_product_parameters(monkeypatch):
    fake = FakeSsmClient()
    _make_module(monkeypatch, fake)
    _base_secret(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "product_name, instance_id and username_prefix are required" in exc.value.args[0]["msg"]


def test_create_secret(monkeypatch):
    fake = FakeSsmClient()
    _make_module(monkeypatch, fake)
    _base_secret(
        state="present",
        product_name="Mysql",
        instance_id="cdb-xxxxxxxx",
        username_prefix="ssmapp",
        privileges=[
            {"privilege_name": "GlobalPrivileges", "privileges": ["SELECT", "INSERT"]}
        ],
        description="managed by Ansible",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["SecretName"] == "orders-db-managed"
    assert result["secret"]["Status"] == "Enabled"
    assert len(fake.secrets) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeSecret"
    assert "CreateProductSecret" in ops
    assert "DescribeAsyncRequestInfo" in ops


def test_create_secret_disabled(monkeypatch):
    fake = FakeSsmClient()
    _make_module(monkeypatch, fake)
    _base_secret(
        state="present",
        product_name="Mysql",
        instance_id="cdb-xxxxxxxx",
        username_prefix="ssmapp",
        enabled=False,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Status"] == "Disabled"
    assert fake.secrets[0]["Status"] == "Disabled"
    assert "DisableSecret" in [c for c, unused in fake.calls]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeSsmClient()
    _make_module(monkeypatch, fake)
    _base_secret(
        _ansible_check_mode=True,
        state="present",
        product_name="Mysql",
        instance_id="cdb-xxxxxxxx",
        username_prefix="ssmapp",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["SecretName"] == "orders-db-managed"
    assert fake.secrets == []
    assert "CreateProductSecret" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-secret flows
# ---------------------------------------------------------------------------


def test_existing_secret_no_drift_is_idempotent(monkeypatch):
    fake = FakeSsmClient(secrets=[_secret()])
    _make_module(monkeypatch, fake)
    _base_secret(
        state="present",
        product_name="Mysql",
        instance_id="cdb-xxxxxxxx",
        username_prefix="ssmapp",
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["secret"]["SecretName"] == "orders-db-managed"


def test_update_description(monkeypatch):
    fake = FakeSsmClient(secrets=[_secret()])
    _make_module(monkeypatch, fake)
    _base_secret(
        state="present",
        product_name="Mysql",
        instance_id="cdb-xxxxxxxx",
        username_prefix="ssmapp",
        description="rotated quarterly",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Description"] == "rotated quarterly"
    assert "UpdateDescription" in [c for c, unused in fake.calls]


def test_disable_existing_secret(monkeypatch):
    fake = FakeSsmClient(secrets=[_secret()])
    _make_module(monkeypatch, fake)
    _base_secret(
        state="present",
        product_name="Mysql",
        instance_id="cdb-xxxxxxxx",
        username_prefix="ssmapp",
        enabled=False,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["Status"] == "Disabled"
    assert "DisableSecret" in [c for c, unused in fake.calls]


def test_enable_rotation(monkeypatch):
    fake = FakeSsmClient(secrets=[_secret()])
    _make_module(monkeypatch, fake)
    _base_secret(
        state="present",
        product_name="Mysql",
        instance_id="cdb-xxxxxxxx",
        username_prefix="ssmapp",
        rotation_enabled=True,
        rotation_begin_time="2026-09-02 02:00:00",
        rotation_frequency=60,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["secret"]["RotationStatus"] == 1
    assert result["secret"]["RotationFrequency"] == 60
    assert "UpdateRotationStatus" in [c for c, unused in fake.calls]


def test_existing_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeSsmClient(secrets=[_secret()])
    _make_module(monkeypatch, fake)
    _base_secret(
        _ansible_check_mode=True,
        state="present",
        product_name="Mysql",
        instance_id="cdb-xxxxxxxx",
        username_prefix="ssmapp",
        description="would change",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.secrets[0]["Description"] == "managed by Ansible"
    assert "UpdateDescription" not in [c for c, unused in fake.calls]


def test_immutable_product_drift_fails(monkeypatch):
    fake = FakeSsmClient(secrets=[_secret()])
    _make_module(monkeypatch, fake)
    _base_secret(
        state="present",
        product_name="Postgresql",
        instance_id="cdb-xxxxxxxx",
        username_prefix="ssmapp",
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "immutable after creation" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# validation / failure paths
# ---------------------------------------------------------------------------


def test_username_prefix_too_long_fails(monkeypatch):
    fake = FakeSsmClient()
    _make_module(monkeypatch, fake)
    _base_secret(
        state="present",
        product_name="Mysql",
        instance_id="cdb-xxxxxxxx",
        username_prefix="waytoolongname",
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "at most eight characters" in exc.value.args[0]["msg"]


def test_recovery_window_out_of_range_fails(monkeypatch):
    fake = FakeSsmClient()
    _make_module(monkeypatch, fake)
    _base_secret(state="absent", recovery_window_days=99)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "recovery_window_days" in exc.value.args[0]["msg"]


def test_rotation_requires_begin_time(monkeypatch):
    fake = FakeSsmClient()
    _make_module(monkeypatch, fake)
    _base_secret(
        state="present",
        product_name="Mysql",
        instance_id="cdb-xxxxxxxx",
        username_prefix="ssmapp",
        rotation_enabled=True,
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rotation_begin_time is required" in exc.value.args[0]["msg"]


def test_rotation_frequency_out_of_range_fails(monkeypatch):
    fake = FakeSsmClient()
    _make_module(monkeypatch, fake)
    _base_secret(
        state="present",
        product_name="Mysql",
        instance_id="cdb-xxxxxxxx",
        username_prefix="ssmapp",
        rotation_enabled=True,
        rotation_begin_time="2026-09-02 02:00:00",
        rotation_frequency=7,
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rotation_frequency must be between 30 and 365" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeSecret(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base_secret(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
