"""Unit tests for the config_aggregator write module (helpers + run_module).

Creates (and discovers) Tencent Cloud Config cross-account aggregators.
Because the Config API exposes no update or delete operation, every
attribute is immutable: an existing aggregator whose desired state drifts
fails immediately (even in check mode, since the immutability check
precedes the check-mode gate). Lookup is two-phase: ListAggregators is
paged looking for an exact AccountGroupId (when given) or Name match, then
the matched entry is enriched through DescribeAggregator. No ``state``
parameter exists and nothing is ever deleted.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import config_aggregator as mod
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
        "name": "agg-main",
        "description": "",
        "aggregator_type": "CUSTOM",
        "accounts": [{"member_uin": 100000000001, "member_name": "prod"}],
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    return module_args(**{k: v for k, v in _params(**extra).items() if v is not None})


def _stored(name, group_id, type_="CUSTOM", description="", accounts=None, uins=(100000000001,)):
    """A full aggregator record as stored by the fake client."""
    return {
        "AccountGroupId": group_id,
        "Name": name,
        "Type": type_,
        "Description": description,
        "AggregatorAccounts": [{"MemberUin": u, "MemberName": "acct-%d" % u} for u in uins],
    }


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or {}

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeConfigClient(object):
    """In-memory ConfigClient stand-in storing aggregators by group id.

    ListAggregators pages over the stored collection (Offset/Limit slicing
    so multi-page finds are observable); DescribeAggregator enriches a
    stored record with fields the list omits (Status) plus a RequestId that
    the module pops; CreateAggregator assigns a fresh AccountGroupId and
    stores the request payload.
    """

    def __init__(self, aggregators=None):
        # list of full record dicts (see _stored)
        self.aggregators = [dict(a) for a in (aggregators or [])]
        self.calls = []
        self._next_id = 1

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def ListAggregators(self, request):
        self._record("ListAggregators", request)
        offset = request.Offset or 0
        limit = request.Limit or 100
        items = [FakeResource({"AccountGroupId": a["AccountGroupId"], "Name": a["Name"]}) for a in self.aggregators]
        page = items[offset:offset + limit]
        return SimpleNamespace(Items=page, Total=len(self.aggregators), RequestId="req-fake")

    def DescribeAggregator(self, request):
        self._record("DescribeAggregator", request)
        for a in self.aggregators:
            if a["AccountGroupId"] == request.AccountGroupId:
                return FakeResource(dict(a, Status="Active", RequestId="req-fake"))
        return FakeResource({})

    def CreateAggregator(self, request):
        self._record("CreateAggregator", request)
        group_id = "agg-%d" % self._next_id
        self._next_id += 1
        item = {
            "AccountGroupId": group_id,
            "Name": request.Name,
            "Type": request.Type,
            "Description": request.Description or "",
            "AggregatorAccounts": [
                {"MemberUin": acct.MemberUin, "MemberName": acct.MemberName} for acct in (request.AggregatorAccounts or [])
            ],
        }
        self.aggregators.append(item)
        return SimpleNamespace(AccountGroupId=group_id, RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(ConfigClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# request-builder helper tests
# ---------------------------------------------------------------------------


def test_list_request_sets_offset_and_limit():
    models = FakeModels()
    request = mod.list_request(models)
    assert request.Offset == 0
    assert request.Limit == 100
    request = mod.list_request(models, offset=50)
    assert request.Offset == 50
    assert request.Limit == 100


def test_describe_request_sets_account_group_id():
    request = mod.describe_request(FakeModels(), "agg-7")
    assert request.AccountGroupId == "agg-7"


def test_create_request_carries_fields_and_accounts():
    models = FakeModels()
    request = mod.create_request(models, _params())
    assert request.Name == "agg-main"
    assert request.Description == ""
    assert request.Type == "CUSTOM"
    assert [(item.MemberUin, item.MemberName) for item in request.AggregatorAccounts] == [
        (100000000001, "prod"),
    ]


def test_create_request_empty_accounts():
    request = mod.create_request(FakeModels(), _params(accounts=[]))
    assert request.AggregatorAccounts == []


# ---------------------------------------------------------------------------
# _accounts normalization tests
# ---------------------------------------------------------------------------


def test_accounts_normalizes_api_style_keys():
    values = [{"MemberUin": 100000000001, "MemberName": "prod"}]
    assert mod._accounts(values) == [{"MemberUin": 100000000001, "MemberName": "prod"}]


def test_accounts_normalizes_param_style_keys():
    values = [{"member_uin": 100000000002, "member_name": "staging"}]
    assert mod._accounts(values) == [{"MemberUin": 100000000002, "MemberName": "staging"}]


def test_accounts_missing_name_yields_none():
    assert mod._accounts([{"MemberUin": 100000000001}]) == [{"MemberUin": 100000000001, "MemberName": None}]


def test_accounts_sorts_by_member_uin():
    values = [
        {"MemberUin": 100000000002, "MemberName": "b"},
        {"MemberUin": 100000000001, "MemberName": "a"},
    ]
    assert [item["MemberUin"] for item in mod._accounts(values)] == [100000000001, 100000000002]


def test_accounts_empty_inputs():
    assert mod._accounts([]) == []
    assert mod._accounts(None) == []


# ---------------------------------------------------------------------------
# find_aggregator helper tests
# ---------------------------------------------------------------------------


def test_find_matches_by_name_and_describes(monkeypatch):
    fake = FakeConfigClient([_stored("agg-main", "agg-1")])
    params = {"name": "agg-main"}
    found = mod.find_aggregator(FakeModule(params), fake, FakeModels(), params)
    assert found["AccountGroupId"] == "agg-1"
    assert found["Name"] == "agg-main"
    assert found["Status"] == "Active"  # describe-only enrichment
    assert "RequestId" not in found  # popped from the describe payload
    assert [name for name, _ in fake.calls] == ["ListAggregators", "DescribeAggregator"]
    describe = [req for name, req in fake.calls if name == "DescribeAggregator"][0]
    assert describe.AccountGroupId == "agg-1"


def test_find_prefers_account_group_id_over_name(monkeypatch):
    fake = FakeConfigClient([_stored("agg-a", "g1"), _stored("agg-b", "g2")])
    params = {"account_group_id": "g2", "name": "agg-a"}
    found = mod.find_aggregator(FakeModule(params), fake, FakeModels(), params)
    assert found["AccountGroupId"] == "g2"  # matched by id, name ignored
    assert found["Name"] == "agg-b"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeConfigClient([_stored("actual", "agg-1")])
    params = {"name": "other-name"}
    assert mod.find_aggregator(FakeModule(params), fake, FakeModels(), params) is None


def test_find_empty_store_returns_none(monkeypatch):
    fake = FakeConfigClient()
    params = {"name": "agg-main"}
    assert mod.find_aggregator(FakeModule(params), fake, FakeModels(), params) is None


def test_find_multiple_name_matches_fail(monkeypatch):
    fake = FakeConfigClient([_stored("dup", "agg-1"), _stored("dup", "agg-2")])
    params = {"name": "dup"}
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find_aggregator(FakeModule(params), fake, FakeModels(), params)
    assert exc.value.args[0]["msg"] == "Multiple Config aggregators matched; specify account_group_id"


def test_find_pages_until_target_found(monkeypatch):
    records = [_stored("agg-%d" % i, "g-%d" % i) for i in range(205)]
    records[150] = _stored("target", "g-150")
    fake = FakeConfigClient(records)
    params = {"name": "target"}
    found = mod.find_aggregator(FakeModule(params), fake, FakeModels(), params)
    assert found["AccountGroupId"] == "g-150"
    list_calls = [req for name, req in fake.calls if name == "ListAggregators"]
    assert [req.Offset for req in list_calls] == [0, 100, 200]
    assert found["Status"] == "Active"


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_missing_name_fails_validation():
    _run_args(name=None, aggregator_type="CUSTOM")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name" in exc.value.args[0]["msg"]


def test_present_creates_aggregator_and_refinds(monkeypatch):
    fake = FakeConfigClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["aggregator"]["AccountGroupId"] == "agg-1"
    assert result["aggregator"]["Name"] == "agg-main"
    assert result["aggregator"]["Type"] == "CUSTOM"
    assert result["aggregator"]["Status"] == "Active"  # describe enrichment after re-find
    assert "RequestId" not in result["aggregator"]
    assert [name for name, _ in fake.calls] == [
        "ListAggregators",
        "CreateAggregator",
        "ListAggregators",
        "DescribeAggregator",
    ]


def test_present_create_payload_carries_accounts(monkeypatch):
    fake = FakeConfigClient()
    _make_module(monkeypatch, fake)
    _run_args(accounts=[
        {"member_uin": 100000000002, "member_name": "staging"},
        {"member_uin": 100000000001, "member_name": "prod"},
    ])
    run(mod.run_module)
    create = [req for name, req in fake.calls if name == "CreateAggregator"][0]
    assert create.Name == "agg-main"
    assert create.Type == "CUSTOM"
    assert [(item.MemberUin, item.MemberName) for item in create.AggregatorAccounts] == [
        (100000000002, "staging"),
        (100000000001, "prod"),
    ]
    assert fake.aggregators[0]["AccountGroupId"] == "agg-1"


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeConfigClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["aggregator"] is None  # nothing created or re-fetched
    assert [name for name, _ in fake.calls] == ["ListAggregators"]
    assert result["diff"]["before"] is None
    assert result["diff"]["after"] == {
        "Name": "agg-main",
        "Type": "CUSTOM",
        "AggregatorAccounts": [{"MemberName": "prod", "MemberUin": 100000000001}],
    }


def test_present_exists_unchanged_is_noop(monkeypatch):
    fake = FakeConfigClient([_stored("agg-main", "agg-1", description=None)])
    _make_module(monkeypatch, fake)
    _run_args(accounts=[{"member_uin": 100000000001, "member_name": "acct-100000000001"}])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["aggregator"]["AccountGroupId"] == "agg-1"
    assert result["aggregator"]["Status"] == "Active"
    assert not any(name == "CreateAggregator" for name, _ in fake.calls)


def test_noop_ignores_account_order(monkeypatch):
    stored = _stored(
        "agg-main",
        "agg-1",
        uins=(100000000002, 100000000001),
    )
    fake = FakeConfigClient([stored])
    _make_module(monkeypatch, fake)
    _run_args(accounts=[
        {"member_uin": 100000000001, "member_name": "acct-100000000001"},
        {"member_uin": 100000000002, "member_name": "acct-100000000002"},
    ])
    result = run(mod.run_module)
    assert result["changed"] is False


def test_name_drift_fails_immutable(monkeypatch):
    fake = FakeConfigClient([_stored("other-name", "agg-9")])
    _make_module(monkeypatch, fake)
    _run_args(account_group_id="agg-9", name="new-name")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Config aggregator attributes are immutable because the API exposes no update or delete operation"
    assert payload["aggregator"]["AccountGroupId"] == "agg-9"
    assert payload["desired"]["Name"] == "new-name"


def test_type_drift_fails_immutable(monkeypatch):
    fake = FakeConfigClient([_stored("agg-main", "agg-1", type_="ORG")])
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "immutable" in payload["msg"]
    assert payload["desired"]["Type"] == "CUSTOM"
    assert payload["aggregator"]["Type"] == "ORG"


def test_description_drift_fails_immutable(monkeypatch):
    fake = FakeConfigClient([_stored("agg-main", "agg-1", description="old-desc")])
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["desired"]["Description"] == ""


def test_account_membership_drift_fails_immutable(monkeypatch):
    fake = FakeConfigClient([_stored("agg-main", "agg-1", uins=(100000000001, 100000000002))])
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "immutable" in payload["msg"]
    assert payload["desired"]["AggregatorAccounts"] == [{"MemberUin": 100000000001, "MemberName": "prod"}]
    assert payload["aggregator"]["AggregatorAccounts"] == [
        {"MemberUin": 100000000001, "MemberName": "acct-100000000001"},
        {"MemberUin": 100000000002, "MemberName": "acct-100000000002"},
    ]


def test_type_drift_fails_even_in_check_mode(monkeypatch):
    fake = FakeConfigClient([_stored("agg-main", "agg-1", type_="ORG")])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "immutable" in exc.value.args[0]["msg"]  # immutability precedes the check-mode gate


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(ConfigClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: _BoomClient())
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeConfigClient([_stored("agg-main", "agg-1", description=None)])
    _make_module(monkeypatch, fake)
    _run_args(accounts=[{"member_uin": 100000000001, "member_name": "acct-100000000001"}])
    result = run(mod.main)
    assert result["changed"] is False
    assert result["aggregator"]["AccountGroupId"] == "agg-1"
