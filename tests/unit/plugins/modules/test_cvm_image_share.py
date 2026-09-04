"""Unit tests for the cvm_image_share write module (helpers + run_module).

Shares (or un-shares) a custom CVM image with a set of root accounts.
The module is set-arithmetic idempotent: it only issues a
ModifyImageSharePermission call for the accounts that are not already in
the desired state, and a second run with identical inputs reports
changed=false. Lookup reads DescribeImageSharePermission and tolerates
both the ``AccountId`` and ``Account`` response attributes, coercing and
de-duplicating into a sorted list.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cvm_image_share as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "image_id": "img-abc123",
        "account_ids": ["100000000001", "100000000002"],
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    return module_args(**{k: v for k, v in _params(**extra).items() if v is not None})


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


class FakeCvmClient(object):
    """In-memory CvmClient stand-in storing per-image share sets.

    DescribeImageSharePermission reports the stored accounts;
    ModifyImageSharePermission adds or removes the request's AccountIds
    according to its Permission attribute so the module's SHARE/CANCEL
    dispatch is observable.
    """

    def __init__(self, shares=None):
        # image_id -> sorted list of account-id strings
        self.shares = {k: list(v) for k, v in (shares or {}).items()}
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeImageSharePermission(self, request):
        self._record("DescribeImageSharePermission", request)
        accounts = self.shares.get(request.ImageId, [])
        return SimpleNamespace(
            SharePermissionSet=[FakeResource({"AccountId": a}) for a in accounts],
            RequestId="req-fake",
        )

    def ModifyImageSharePermission(self, request):
        self._record("ModifyImageSharePermission", request)
        current = set(self.shares.get(request.ImageId, []))
        requested = set(request.AccountIds or [])
        if request.Permission == "SHARE":
            current |= requested
        elif request.Permission == "CANCEL":
            current -= requested
        self.shares[request.ImageId] = sorted(current)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load_cvm",
        lambda: (FakeModels(), SimpleNamespace(CvmClient=object)),
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
# find_shared_accounts tests
# ---------------------------------------------------------------------------


def _describe_response(items):
    return SimpleNamespace(SharePermissionSet=items, RequestId="req-fake")


def test_find_shared_accounts_reads_account_id_and_dedupes(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)

    def describe(request):
        return _describe_response([
            FakeResource({"AccountId": 100000000001}),  # int coercion
            FakeResource({"AccountId": "100000000002"}),
            FakeResource({"AccountId": "100000000001"}),  # duplicate
        ])

    module = FakeModule()
    module.sdk_call = lambda op, req: describe(req)
    assert mod.find_shared_accounts(module, fake, FakeModels(), "img-abc123") == [
        "100000000001",
        "100000000002",
    ]


def test_find_shared_accounts_falls_back_to_account_attribute(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)

    def describe(request):
        return _describe_response([FakeResource({"Account": "100000000009"})])

    module = FakeModule()
    module.sdk_call = lambda op, req: describe(req)
    assert mod.find_shared_accounts(module, fake, FakeModels(), "img-abc123") == ["100000000009"]


def test_find_shared_accounts_skips_entries_without_account(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)

    def describe(request):
        return _describe_response([
            FakeResource({"AccountId": "100000000001"}),
            FakeResource({"SharedToMe": True}),  # no account identity
        ])

    module = FakeModule()
    module.sdk_call = lambda op, req: describe(req)
    assert mod.find_shared_accounts(module, fake, FakeModels(), "img-abc123") == ["100000000001"]


def test_find_shared_accounts_empty_response_returns_empty(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    module = FakeModule()
    assert mod.find_shared_accounts(module, fake, FakeModels(), "img-abc123") == []


def test_find_shared_accounts_sends_image_id(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    module = FakeModule()
    mod.find_shared_accounts(module, fake, FakeModels(), "img-xyz")
    request = [c[1] for c in fake.calls if c[0] == "DescribeImageSharePermission"][0]
    assert request.ImageId == "img-xyz"


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_empty_account_ids_fails(monkeypatch):
    _make_module(monkeypatch, FakeCvmClient())
    _run_args(account_ids=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "account_ids must not be empty" in exc.value.args[0]["msg"]


def test_present_shares_missing_accounts(monkeypatch):
    fake = FakeCvmClient(shares={"img-abc123": ["100000000001"]})
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["shared_accounts"] == ["100000000001", "100000000002"]
    assert result["msg"] == "Shared with ['100000000002']"
    update = [c for c in fake.calls if c[0] == "ModifyImageSharePermission"][0][1]
    assert update.ImageId == "img-abc123"
    assert update.AccountIds == ["100000000002"]
    assert update.Permission == "SHARE"


def test_present_all_accounts_shared_is_noop(monkeypatch):
    fake = FakeCvmClient(shares={"img-abc123": ["100000000001", "100000000002"]})
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["shared_accounts"] == ["100000000001", "100000000002"]
    assert result["msg"] == "Image shares are up to date"
    assert not any(c[0] == "ModifyImageSharePermission" for c in fake.calls)


def test_present_no_shares_creates_all(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["shared_accounts"] == ["100000000001", "100000000002"]
    update = [c for c in fake.calls if c[0] == "ModifyImageSharePermission"][0][1]
    assert update.AccountIds == ["100000000001", "100000000002"]
    assert update.Permission == "SHARE"


def test_present_dedupes_account_ids(monkeypatch):
    fake = FakeCvmClient(shares={"img-abc123": ["100000000001"]})
    _make_module(monkeypatch, fake)
    _run_args(account_ids=["100000000002", "100000000002", "100000000001"])
    result = run(mod.run_module)
    assert result["changed"] is True  # only the duplicate of 002 is new work
    assert result["shared_accounts"] == ["100000000001", "100000000002"]
    update = [c for c in fake.calls if c[0] == "ModifyImageSharePermission"][0][1]
    assert update.AccountIds == ["100000000002"]


def test_present_check_mode_is_dry_run(monkeypatch):
    fake = FakeCvmClient(shares={"img-abc123": ["100000000001"]})
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["shared_accounts"] == ["100000000001", "100000000002"]
    assert result["msg"] == "Would share with ['100000000002']"
    assert result["diff"]["before"] == {"SharedAccounts": ["100000000001"]}
    assert result["diff"]["after"] == {"SharedAccounts": ["100000000001", "100000000002"]}
    assert not any(c[0] == "ModifyImageSharePermission" for c in fake.calls)
    assert fake.shares["img-abc123"] == ["100000000001"]  # remote untouched


def test_present_check_mode_noop_unchanged(monkeypatch):
    fake = FakeCvmClient(shares={"img-abc123": ["100000000001", "100000000002"]})
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "Image shares are up to date"


def test_absent_cancels_shared_accounts(monkeypatch):
    fake = FakeCvmClient(shares={"img-abc123": ["100000000001", "100000000002"]})
    _make_module(monkeypatch, fake)
    _run_args(state="absent", account_ids=["100000000002"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["shared_accounts"] == ["100000000001"]
    assert result["msg"] == "Cancelled sharing with ['100000000002']"
    update = [c for c in fake.calls if c[0] == "ModifyImageSharePermission"][0][1]
    assert update.AccountIds == ["100000000002"]
    assert update.Permission == "CANCEL"
    assert fake.shares["img-abc123"] == ["100000000001"]


def test_absent_no_current_share_is_noop(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["shared_accounts"] == []
    assert result["msg"] == "Image shares already absent"
    assert not any(c[0] == "ModifyImageSharePermission" for c in fake.calls)


def test_absent_disjoint_accounts_is_noop(monkeypatch):
    fake = FakeCvmClient(shares={"img-abc123": ["100000000009"]})
    _make_module(monkeypatch, fake)
    _run_args(state="absent", account_ids=["100000000001", "100000000002"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["shared_accounts"] == ["100000000009"]  # other shares untouched
    assert result["msg"] == "Image shares already absent"
    assert not any(c[0] == "ModifyImageSharePermission" for c in fake.calls)


def test_absent_leaves_other_shares_in_place(monkeypatch):
    fake = FakeCvmClient(shares={"img-abc123": ["100000000001", "100000000002", "100000000009"]})
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["shared_accounts"] == ["100000000009"]
    assert fake.shares["img-abc123"] == ["100000000009"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCvmClient(shares={"img-abc123": ["100000000001", "100000000002"]})
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, state="absent", account_ids=["100000000002"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["shared_accounts"] == ["100000000001"]
    assert result["msg"] == "Would cancel sharing with ['100000000002']"
    assert result["diff"]["after"] == {"SharedAccounts": ["100000000001"]}
    assert not any(c[0] == "ModifyImageSharePermission" for c in fake.calls)
    assert fake.shares["img-abc123"] == ["100000000001", "100000000002"]  # remote untouched


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load_cvm",
        lambda: (FakeModels(), SimpleNamespace(CvmClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeCvmClient(shares={"img-abc123": ["100000000001", "100000000002"]})
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.main)
    assert result["changed"] is False
    assert result["msg"] == "Image shares are up to date"
