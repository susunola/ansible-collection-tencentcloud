"""Unit tests for the dcdb_security_config write module (run_module flows).

The module reconciles explicitly supplied DCDB encryption, SSL and security
groups; encryption is one-way, and enabling it or SSL waits for the described
state to converge. The fake DCDB client mutates the relevant store so the
post-write waiters converge immediately.

Scenario matrix:

* argument validation (missing instance, no control supplied)
* no-op when every supplied control already matches
* enabling encryption / toggling SSL / replacing security groups
* disabling encryption is rejected
* check-mode dry run
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dcdb_security_config as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)

INSTANCE_ID = "tdsqlshard-xxxxxxxx"


def _args(**overrides):
    params = {
        "instance_id": INSTANCE_ID,
        "encryption_enabled": True,
        "ssl_enabled": True,
        "security_group_ids": ["sg-a", "sg-b"],
    }
    params.update(overrides)
    return module_args(**params)


class FakeDcdbClient(object):
    """In-memory DCDB client with mutable encryption/SSL/security-group state."""

    def __init__(self, encrypt_status=0, ssl_status=3, groups=None):
        self.encrypt_status = encrypt_status
        self.ssl_status = ssl_status
        self.groups = list(groups or [])
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeDBEncryptAttributes(self, request):
        self._record("DescribeDBEncryptAttributes", request)
        return SimpleNamespace(EncryptStatus=self.encrypt_status)

    def DescribeInstanceSSLAttributes(self, request):
        self._record("DescribeInstanceSSLAttributes", request)
        return SimpleNamespace(Status=self.ssl_status)

    def DescribeDBSecurityGroups(self, request):
        self._record("DescribeDBSecurityGroups", request)
        return SimpleNamespace(Groups=[SimpleNamespace(SecurityGroupId=g) for g in self.groups])

    def ModifyDBEncryptAttributes(self, request):
        self._record("ModifyDBEncryptAttributes", request)
        self.encrypt_status = getattr(request, "EncryptEnabled", 0)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyInstanceSSLAttributes(self, request):
        self._record("ModifyInstanceSSLAttributes", request)
        enabled = bool(getattr(request, "SSLEnabled", 0))
        self.ssl_status = 2 if enabled else 3
        return SimpleNamespace(RequestId="req-fake")

    def ModifyDBInstanceSecurityGroups(self, request):
        self._record("ModifyDBInstanceSecurityGroups", request)
        self.groups = list(getattr(request, "SecurityGroupIds", None) or [])
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DcdbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_missing_instance_id_fails(monkeypatch):
    fake = FakeDcdbClient()
    _make_module(monkeypatch, fake)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "missing required arguments" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_no_control_supplied_fails(monkeypatch):
    fake = FakeDcdbClient()
    _make_module(monkeypatch, fake)
    module_args(instance_id=INSTANCE_ID)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "at least one DCDB security control must be supplied" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_idempotent_when_all_controls_match(monkeypatch):
    fake = FakeDcdbClient(encrypt_status=1, ssl_status=2, groups=["sg-a", "sg-b"])
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["security_config"]["encryption_enabled"] is True
    assert result["security_config"]["ssl_enabled"] is True
    assert result["security_config"]["security_group_ids"] == ["sg-a", "sg-b"]


def test_enable_encryption(monkeypatch):
    fake = FakeDcdbClient(encrypt_status=0)
    _make_module(monkeypatch, fake)
    module_args(instance_id=INSTANCE_ID, encryption_enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["security_config"]["encryption_enabled"] is True
    modify_call = next((c, r) for c, r in fake.calls if c == "ModifyDBEncryptAttributes")
    assert getattr(modify_call[1], "EncryptEnabled") == 1


def test_disable_encryption_fails(monkeypatch):
    fake = FakeDcdbClient(encrypt_status=1)
    _make_module(monkeypatch, fake)
    module_args(instance_id=INSTANCE_ID, encryption_enabled=False)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "encryption cannot be disabled" in payload["msg"]


def test_enable_ssl_waits_for_status(monkeypatch):
    fake = FakeDcdbClient(ssl_status=3)
    _make_module(monkeypatch, fake)
    module_args(instance_id=INSTANCE_ID, ssl_enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["security_config"]["ssl_enabled"] is True
    modify_call = next((c, r) for c, r in fake.calls if c == "ModifyInstanceSSLAttributes")
    assert getattr(modify_call[1], "SSLEnabled") == 1


def test_disable_ssl(monkeypatch):
    fake = FakeDcdbClient(ssl_status=2)
    _make_module(monkeypatch, fake)
    module_args(instance_id=INSTANCE_ID, ssl_enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["security_config"]["ssl_enabled"] is False
    modify_call = next((c, r) for c, r in fake.calls if c == "ModifyInstanceSSLAttributes")
    assert getattr(modify_call[1], "SSLEnabled") == 0


def test_replace_security_groups(monkeypatch):
    fake = FakeDcdbClient(groups=["sg-a"])
    _make_module(monkeypatch, fake)
    module_args(instance_id=INSTANCE_ID, security_group_ids=["sg-a", "sg-c"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["security_config"]["security_group_ids"] == ["sg-a", "sg-c"]
    modify_call = next((c, r) for c, r in fake.calls if c == "ModifyDBInstanceSecurityGroups")
    assert getattr(modify_call[1], "SecurityGroupIds") == ["sg-a", "sg-c"]


def test_enable_check_mode_is_dry_run(monkeypatch):
    fake = FakeDcdbClient(ssl_status=3)
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, instance_id=INSTANCE_ID, ssl_enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["security_config"] == {"ssl_enabled": True}
    assert "ModifyInstanceSSLAttributes" not in [c for c, unused in fake.calls]
    assert fake.ssl_status == 3


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeDBEncryptAttributes(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    module_args(instance_id=INSTANCE_ID, encryption_enabled=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_dcdb_security_config.py)
# ---------------------------------------------------------------------------


def test_desired_only_includes_explicit_controls():
    assert mod.desired({"encryption_enabled": True, "ssl_enabled": None, "security_group_ids": None}) == {"encryption_enabled": True}


def test_desired_sorts_and_deduplicates_security_groups():
    value = mod.desired({"encryption_enabled": None, "ssl_enabled": True, "security_group_ids": ["sg-b", "sg-a", "sg-a"]})
    assert value == {"ssl_enabled": True, "security_group_ids": ["sg-a", "sg-b"]}
