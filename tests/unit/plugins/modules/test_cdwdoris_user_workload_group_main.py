"""Unit tests for the cdwdoris_user_workload_group write module (run_module flows).

The module declaratively moves every host identity of a Doris user into the
requested workload group. There is no delete lifecycle, so coverage focuses
on the no-op, binding creation and group-migration flows. The fake CDW Doris
client mutates a user-binding store so the post-write describe refetch
converges.

Scenario matrix:

* argument validation (empty hosts, missing required arguments)
* no-op when the user is already in the requested group
* moving an existing binding to a different group (drift)
* binding an unbound user (old group absent)
* check-mode dry run
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdwdoris_user_workload_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "cdwdoris-xxxxxxxx"
USER_NAME = "analyst"


def _args(**overrides):
    params = {"instance_id": INSTANCE_ID, "user_name": USER_NAME, "hosts": ["%", "10.0.0.%"], "workload_group": "interactive"}
    params.update(overrides)
    return module_args(**params)


class FakeCdwdorisClient(object):
    """In-memory CDW Doris client mutating a user-to-group binding store."""

    def __init__(self, bindings=None):
        self.bindings = [copy.deepcopy(b) for b in (bindings or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeUserBindWorkloadGroup(self, request):
        self._record("DescribeUserBindWorkloadGroup", request)
        return SimpleNamespace(UserBindInfos=[FakeResource(b) for b in self.bindings], ErrorMsg=None)

    def ModifyUserBindWorkloadGroup(self, request):
        self._record("ModifyUserBindWorkloadGroup", request)
        target_user = getattr(request, "UserName", None) or (getattr(request, "BindUsers", [None])[0].UserName if getattr(request, "BindUsers", None) else None)
        for binding in self.bindings:
            if binding.get("UserName") == target_user:
                binding["WorkloadGroupName"] = getattr(request, "NewWorkloadGroupName", None)
                return SimpleNamespace(ErrorMsg=None, RequestId="req-fake")
        self.bindings.append({"UserName": target_user, "WorkloadGroupName": getattr(request, "NewWorkloadGroupName", None)})
        return SimpleNamespace(ErrorMsg=None, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(CdwdorisClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_missing_required_args_fails(monkeypatch):
    fake = FakeCdwdorisClient()
    _make_module(monkeypatch, fake)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "missing required arguments" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_empty_hosts_fails(monkeypatch):
    fake = FakeCdwdorisClient()
    _make_module(monkeypatch, fake)
    _args(hosts=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "hosts must contain every host identity" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_idempotent_when_already_in_group(monkeypatch):
    fake = FakeCdwdorisClient(bindings=[{"UserName": USER_NAME, "WorkloadGroupName": "interactive"}])
    _make_module(monkeypatch, fake)
    _args(workload_group="interactive")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["binding"]["WorkloadGroupName"] == "interactive"
    assert [c for c, unused in fake.calls] == ["DescribeUserBindWorkloadGroup"]


def test_move_binding_to_new_group(monkeypatch):
    fake = FakeCdwdorisClient(bindings=[{"UserName": USER_NAME, "WorkloadGroupName": "batch"}])
    _make_module(monkeypatch, fake)
    _args(workload_group="interactive")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"]["WorkloadGroupName"] == "interactive"
    assert len(fake.bindings) == 1
    move_call = next((c, r) for c, r in fake.calls if c == "ModifyUserBindWorkloadGroup")
    assert getattr(move_call[1], "OldWorkloadGroupName") == "batch"
    assert getattr(move_call[1], "NewWorkloadGroupName") == "interactive"
    assert [item.UserName for item in getattr(move_call[1], "BindUsers")] == [USER_NAME, USER_NAME]
    assert [item.Host for item in getattr(move_call[1], "BindUsers")] == ["%", "10.0.0.%"]


def test_bind_unbound_user(monkeypatch):
    fake = FakeCdwdorisClient()
    _make_module(monkeypatch, fake)
    _args(workload_group="interactive")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"]["WorkloadGroupName"] == "interactive"
    move_call = next((c, r) for c, r in fake.calls if c == "ModifyUserBindWorkloadGroup")
    assert getattr(move_call[1], "OldWorkloadGroupName") is None


def test_move_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdwdorisClient(bindings=[{"UserName": USER_NAME, "WorkloadGroupName": "batch"}])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, workload_group="interactive")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["binding"] == {"UserName": USER_NAME, "WorkloadGroupName": "interactive"}
    assert fake.bindings[0]["WorkloadGroupName"] == "batch"
    assert "ModifyUserBindWorkloadGroup" not in [c for c, unused in fake.calls]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeUserBindWorkloadGroup(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(workload_group="interactive")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_cdwdoris_user_workload_group.py)
# ---------------------------------------------------------------------------


def test_normalized_hosts_are_stable_and_unique():
    assert mod.normalized_hosts(["10.0.0.%", "%", "%"]) == ["%", "10.0.0.%"]
