"""Unit tests for the cbs_snapshot_share write module (run_module flows).

Reconciles the exact set of Tencent Cloud account IDs allowed to use a CBS
snapshot in the same region. There is no ``state`` parameter: ``present`` is
expressed as the full list of recipients (empty list revokes every share).
Changes are applied as one ``ModifySnapshotsSharePermission`` call with
``Permission=SHARE`` for newly added accounts and one with
``Permission=CANCEL`` for removed accounts.

Scenario matrix:

* an already-matching set is idempotent (including nothing shared)
* granting a new account issues a SHARE call
* revoking accounts issues a CANCEL call
* an exact-set reconciliation may issue both calls in one run
* drift in check mode is a dry run reporting the target
* SDK failure maps to the standard error envelope
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cbs_snapshot_share as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)


def _run_args(**overrides):
    params = {"snapshot_id": "snap-abc123", "account_ids": []}
    params.update(overrides)
    return module_args(**params)


class FakeCbsClient(object):
    """In-memory CBS client holding the shared-account set for one snapshot."""

    def __init__(self, shared=None):
        self.shared = sorted(set(shared or []))
        self.calls = []

    def DescribeSnapshotSharePermission(self, request):
        self.calls.append(("DescribeSnapshotSharePermission", request))
        return SimpleNamespace(SharePermissionSet=[SimpleNamespace(AccountId=a) for a in self.shared])

    def ModifySnapshotsSharePermission(self, request):
        self.calls.append(("ModifySnapshotsSharePermission", request))
        account_ids = list(getattr(request, "AccountIds", None) or [])
        if getattr(request, "Permission", None) == "SHARE":
            self.shared = sorted(set(self.shared) | set(account_ids))
        else:
            self.shared = sorted(set(self.shared) - set(account_ids))
        return SimpleNamespace(RequestId="req-fake")


class _BoomClient(object):
    """Every SDK call raises so the wrapped SDK failure path is reached."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(CbsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# matching state
# ---------------------------------------------------------------------------


def test_nothing_shared_is_idempotent(monkeypatch):
    fake = FakeCbsClient(shared=[])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["share_permissions"] == []
    assert [name for name, unused in fake.calls] == ["DescribeSnapshotSharePermission"]


def test_matching_share_set_is_idempotent(monkeypatch):
    fake = FakeCbsClient(shared=["100001122000", "100001133000"])
    _make_module(monkeypatch, fake)
    _run_args(account_ids=["100001133000", "100001122000"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["share_permissions"] == ["100001122000", "100001133000"]


# ---------------------------------------------------------------------------
# share reconciliation
# ---------------------------------------------------------------------------


def test_grant_new_account_shares(monkeypatch):
    fake = FakeCbsClient(shared=["100001122000"])
    _make_module(monkeypatch, fake)
    _run_args(account_ids=["100001122000", "100001133000"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["share_permissions"] == ["100001122000", "100001133000"]
    ops = [name for name, unused in fake.calls]
    assert ops == ["DescribeSnapshotSharePermission", "ModifySnapshotsSharePermission", "DescribeSnapshotSharePermission"]
    share = [request for name, request in fake.calls if name == "ModifySnapshotsSharePermission"][0]
    assert share.Permission == "SHARE"
    assert share.SnapshotIds == ["snap-abc123"]
    assert share.AccountIds == ["100001133000"]


def test_revoke_every_share_cancels(monkeypatch):
    fake = FakeCbsClient(shared=["100001122000", "100001133000"])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["share_permissions"] == []
    assert fake.shared == []
    cancel = [request for name, request in fake.calls if name == "ModifySnapshotsSharePermission"][0]
    assert cancel.Permission == "CANCEL"
    assert cancel.AccountIds == ["100001122000", "100001133000"]


def test_exact_set_reconciliation_shares_and_cancels(monkeypatch):
    fake = FakeCbsClient(shared=["100001122000", "100001199999"])
    _make_module(monkeypatch, fake)
    _run_args(account_ids=["100001122000", "100001133000"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["share_permissions"] == ["100001122000", "100001133000"]
    ops = [(name, request.Permission) for name, request in fake.calls if name == "ModifySnapshotsSharePermission"]
    assert ops == [("ModifySnapshotsSharePermission", "CANCEL"), ("ModifySnapshotsSharePermission", "SHARE")]


def test_drift_in_check_mode_is_dry_run(monkeypatch):
    fake = FakeCbsClient(shared=["100001122000"])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, account_ids=["100001122000", "100001133000"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["share_permissions"] == ["100001122000", "100001133000"]  # target reported
    assert fake.shared == ["100001122000"]
    assert "ModifySnapshotsSharePermission" not in [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    _make_module(monkeypatch, _BoomClient())
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeCbsClient(shared=["100001122000"])
    _make_module(monkeypatch, fake)
    _run_args(account_ids=["100001122000"])
    result = run(mod.main)
    assert result["changed"] is False
    assert result["share_permissions"] == ["100001122000"]
