"""Unit tests for the ckafka_acl write module (run_module flows).

Drives ``run_module()`` against an in-memory fake CKafka client whose ACL
grant store is mutated by create/delete so post-write describes converge
immediately.

Scenario matrix:

* absent on a missing grant (idempotent no-op)
* absent with a matching grant (check-mode dry run, real delete)
* creation when the exact grant is missing (happy path, check mode)
* no-op when the exact grant already exists
* unrelated grants do not satisfy the match (a second ACL is created)
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import ckafka_acl as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

# The CKafka ACL API encodes resource type / operation / permission as
# integers; grant records carry those encodings back from DescribeACL.
ACL = {
    "ResourceType": 2,  # TOPIC
    "ResourceName": "orders",
    "Operation": 3,  # READ
    "PermissionType": 3,  # ALLOW
    "Host": "*",
    "Principal": "User:analytics",
}


def _acl(**overrides):
    item = copy.deepcopy(ACL)
    item.update(overrides)
    return item


def _args(**overrides):
    params = {
        "instance_id": "ckafka-abcdef12",
        "resource_type": "TOPIC",
        "resource_name": "orders",
        "operation": "READ",
        "permission": "ALLOW",
        "host": "*",
        "principal": "User:analytics",
    }
    params.update(overrides)
    return module_args(**params)


class FakeCkafkaClient(object):
    """In-memory CKafka client mutating an ACL grant store."""

    def __init__(self, acls=None):
        self.acls = [copy.deepcopy(t) for t in (acls or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeACL(self, request):
        self._record("DescribeACL", request)
        return SimpleNamespace(Result=SimpleNamespace(AclList=[FakeResource(t) for t in self.acls]))

    def CreateAcl(self, request):
        self._record("CreateAcl", request)
        item = {
            "ResourceType": request.ResourceType,
            "ResourceName": request.ResourceName,
            "Operation": request.Operation,
            "PermissionType": request.PermissionType,
            "Host": request.Host,
            "Principal": request.Principal,
        }
        self.acls.append(item)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAcl(self, request):
        self._record("DeleteAcl", request)
        self.acls = [
            t
            for t in self.acls
            if not (
                t["ResourceType"] == request.ResourceType
                and t["ResourceName"] == request.ResourceName
                and t["Operation"] == request.Operation
                and t["PermissionType"] == request.PermissionType
                and t["Host"] == request.Host
                and t["Principal"] == request.Principal
            )
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(CkafkaClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_grant_is_idempotent(monkeypatch):
    fake = FakeCkafkaClient(acls=[])
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["acl"] is None
    assert [c for c, unused in fake.calls] == ["DescribeACL"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCkafkaClient(acls=[_acl()])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acl"]["Principal"] == "User:analytics"
    assert len(fake.acls) == 1
    assert "DeleteAcl" not in [c for c, unused in fake.calls]


def test_absent_deletes_grant(monkeypatch):
    fake = FakeCkafkaClient(acls=[_acl()])
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acl"] is None
    assert fake.acls == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteAcl" in ops


def test_absent_leaves_unrelated_grants(monkeypatch):
    # Only the exact requested grant is removed; a WRITE grant on the same
    # topic stays behind.
    other = _acl(Operation=4, Principal="User:writer")
    fake = FakeCkafkaClient(acls=[_acl(), other])
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acl"] is None
    assert [t for t in fake.acls if t.get("Principal") == "User:writer"] == [other]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_grant(monkeypatch):
    fake = FakeCkafkaClient(acls=[])
    _make_module(monkeypatch, fake)
    _args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acl"]["ResourceName"] == "orders"
    assert result["acl"]["Principal"] == "User:analytics"
    assert result["acl"]["ResourceType"] == 2
    assert len(fake.acls) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeACL"
    assert "CreateAcl" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCkafkaClient(acls=[])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acl"] is None
    assert "diff" in result and result["diff"]["after"]["Principal"] == "User:analytics"
    assert fake.acls == []
    assert "CreateAcl" not in [c for c, unused in fake.calls]


def test_unrelated_grant_does_not_satisfy_present(monkeypatch):
    # An existing DENY grant on the same topic is not the grant requested,
    # so the module still creates the ALLOW grant.
    fake = FakeCkafkaClient(acls=[_acl(PermissionType=2, Principal="User:blocked")])
    _make_module(monkeypatch, fake)
    _args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acl"]["Principal"] == "User:analytics"
    assert len(fake.acls) == 2
    ops = [c for c, unused in fake.calls]
    assert "CreateAcl" in ops


# ---------------------------------------------------------------------------
# existing-grant flows
# ---------------------------------------------------------------------------


def test_existing_grant_no_drift_is_idempotent(monkeypatch):
    fake = FakeCkafkaClient(acls=[_acl()])
    _make_module(monkeypatch, fake)
    _args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["acl"]["Principal"] == "User:analytics"
    assert [c for c, unused in fake.calls] == ["DescribeACL"]


def test_different_permission_creates_separate_grant(monkeypatch):
    # The existing grant is ALLOW; requesting DENY for the same principal and
    # topic is a different exact grant, so it gets created.
    fake = FakeCkafkaClient(acls=[_acl()])
    _make_module(monkeypatch, fake)
    _args(state="present", permission="DENY")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acl"]["PermissionType"] == 2
    assert len(fake.acls) == 2


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeACL(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
