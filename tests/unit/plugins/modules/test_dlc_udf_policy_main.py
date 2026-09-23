"""Unit tests for the dlc_udf_policy write module (run_module flows).

The module reconciles the complete user/work-group access policy for one
exact DLC UDF identity (catalog + database + name). The DLC API exposes no
per-identity policy delete; ``policy_infos=[]`` with ``allow_empty=true``
replaces the set with an empty one through ``UpdateUDFPolicy``.

Scenario matrix:

* argument validation (missing name, missing accesses suboption)
* the ``allow_empty`` authorization guard for a full clear
* each entry still requires users or groups
* no-op when the normalized remote policy already matches
* set-semantics drift (duplicate/out-of-order users and accesses)
* drift reconciliation applies ``UpdateUDFPolicy`` and returns the set
* check-mode dry run
* ``wait`` on/off differences in SDK call shape
* clearing an existing policy once ``allow_empty`` is authorized
* SDK failures on describe and update
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_udf_policy as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

NAME = "normalize_email"
DATABASE = "analytics"
CATALOG = "DataLakeCatalog"

# Module-style desired rows (lowercase keys, arbitrary ordering).
POLICY_INFOS = [
    {"accesses": ["select", "select"], "users": ["u2", "u1"], "groups": ["g1"]},
]

# The normalized target those rows collapse to (set + sort semantics).
TARGET = [{"Accesses": ["select"], "Users": ["u1", "u2"], "Groups": ["g1"]}]


def _args(**overrides):
    params = {
        "name": NAME,
        "database_name": DATABASE,
        "catalog_name": CATALOG,
        "policy_infos": POLICY_INFOS,
    }
    params.update(overrides)
    return module_args(**params)


class FakeDlcClient(object):
    """In-memory DLC client mutating a per-identity UDF policy store."""

    def __init__(self, policy=None):
        # Store keyed by (catalog, database, name) -> raw SDK policy rows.
        self.store = {}
        if policy is not None:
            self.store[(CATALOG, DATABASE, NAME)] = policy
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _identity(self, request):
        return (request.CatalogName, request.DatabaseName, request.Name)

    def DescribeUDFPolicy(self, request):
        self._record("DescribeUDFPolicy", request)
        rows = [FakeResource(copy.deepcopy(x)) for x in self.store.get(self._identity(request), [])]
        return SimpleNamespace(UDFPolicyInfos=rows or None, RequestId="req-desc")

    def UpdateUDFPolicy(self, request):
        self._record("UpdateUDFPolicy", request)
        rows = []
        for item in (request.UDFPolicyInfos or []):
            rows.append({
                "Accesses": list(getattr(item, "Accesses", None) or []),
                "Users": list(getattr(item, "Users", None) or []),
                "Groups": list(getattr(item, "Groups", None) or []),
            })
        self.store[self._identity(request)] = rows
        return SimpleNamespace(RequestId="req-upd", UDFPolicyInfos=None)


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_missing_required_args_fails(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "missing required arguments" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_policy_entry_missing_accesses_suboption_fails(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    _args(policy_infos=[{"users": ["u1"], "groups": ["g1"]}])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "accesses" in exc.value.args[0]["msg"]


def test_clearing_policy_without_allow_empty_fails(monkeypatch):
    fake = FakeDlcClient(policy=[{"Accesses": ["select"], "Users": ["u1"], "Groups": ["g1"]}])
    _make_module(monkeypatch, fake)
    _args(policy_infos=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "set allow_empty=true to authorize clearing all DLC UDF policy entries" in payload["msg"]
    assert fake.calls == []


def test_policy_entry_without_users_or_groups_fails(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    _args(policy_infos=[{"accesses": ["select"]}])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "each UDF policy entry requires users or groups" in payload["msg"]
    assert fake.calls == []


def test_idempotent_when_remote_policy_matches_after_normalization(monkeypatch):
    # Remote rows carry duplicate accesses and reversed user order; the set
    # semantics of the module make them compare equal to the desired target.
    remote = [{"Accesses": ["select", "select"], "Users": ["u2", "u1"], "Groups": ["g1"]}]
    fake = FakeDlcClient(policy=remote)
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["udf_policy"] == TARGET
    assert [c for c, unused in fake.calls] == ["DescribeUDFPolicy"]
    assert fake.store[(CATALOG, DATABASE, NAME)] == remote


def test_drift_applies_update_with_exact_identity(monkeypatch):
    # Remote also grants "drop"; only "select" is desired, so an update runs.
    remote = [{"Accesses": ["select", "drop"], "Users": ["u2", "u1"], "Groups": ["g1"]}]
    fake = FakeDlcClient(policy=remote)
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["udf_policy"] == TARGET
    update_call = next((c, r) for c, r in fake.calls if c == "UpdateUDFPolicy")
    request = update_call[1]
    assert request.CatalogName == CATALOG
    assert request.DatabaseName == DATABASE
    assert request.Name == NAME
    assert len(request.UDFPolicyInfos) == 1
    assert request.UDFPolicyInfos[0].Accesses == ["select"]
    assert request.UDFPolicyInfos[0].Users == ["u1", "u2"]
    assert fake.store[(CATALOG, DATABASE, NAME)] == TARGET


def test_multiple_rows_merge_users_and_groups_per_access(monkeypatch):
    infos = [
        {"accesses": ["select"], "users": ["u1"]},
        {"accesses": ["select"], "users": ["u2"], "groups": ["g1"]},
    ]
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    _args(policy_infos=infos)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["udf_policy"] == TARGET
    update_call = next((c, r) for c, r in fake.calls if c == "UpdateUDFPolicy")
    rows = update_call[1].UDFPolicyInfos
    assert len(rows) == 1
    assert rows[0].Users == ["u1", "u2"]
    assert rows[0].Groups == ["g1"]


def test_wait_false_skips_post_write_polls(monkeypatch):
    remote = [{"Accesses": ["select", "drop"], "Users": ["u1"], "Groups": ["g1"]}]
    fake = FakeDlcClient(policy=remote)
    _make_module(monkeypatch, fake)
    _args(wait=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert [c for c, unused in fake.calls] == ["DescribeUDFPolicy", "UpdateUDFPolicy"]


def test_wait_true_polls_until_policy_converges(monkeypatch):
    remote = [{"Accesses": ["select", "drop"], "Users": ["u1"], "Groups": ["g1"]}]
    fake = FakeDlcClient(policy=remote)
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    # Initial read, waiter poll and post-wait re-read describe the store.
    assert [c for c, unused in fake.calls] == [
        "DescribeUDFPolicy",
        "UpdateUDFPolicy",
        "DescribeUDFPolicy",
        "DescribeUDFPolicy",
    ]
    assert fake.store[(CATALOG, DATABASE, NAME)] == TARGET


def test_update_check_mode_is_dry_run(monkeypatch):
    remote = [{"Accesses": ["select", "drop"], "Users": ["u1"], "Groups": ["g1"]}]
    fake = FakeDlcClient(policy=remote)
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["udf_policy"] == TARGET
    assert result["diff"]["after"] == TARGET
    assert "UpdateUDFPolicy" not in [c for c, unused in fake.calls]
    assert fake.store[(CATALOG, DATABASE, NAME)] == remote


def test_allow_empty_replaces_existing_policy_with_empty_set(monkeypatch):
    remote = [{"Accesses": ["select"], "Users": ["u1"], "Groups": ["g1"]}]
    fake = FakeDlcClient(policy=remote)
    _make_module(monkeypatch, fake)
    _args(policy_infos=[], allow_empty=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["udf_policy"] == []
    update_call = next((c, r) for c, r in fake.calls if c == "UpdateUDFPolicy")
    assert update_call[1].UDFPolicyInfos == []
    assert fake.store[(CATALOG, DATABASE, NAME)] == []


def test_already_cleared_policy_is_idempotent(monkeypatch):
    fake = FakeDlcClient(policy=[])
    _make_module(monkeypatch, fake)
    _args(policy_infos=[], allow_empty=True)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["udf_policy"] == []
    assert [c for c, unused in fake.calls] == ["DescribeUDFPolicy"]


def test_sdk_describe_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeUDFPolicy(self, request):
            raise Boom("policy lookup dropped")

    _make_module(monkeypatch, ExplodingClient())
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "policy lookup dropped" in payload["error"]


def test_sdk_update_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeUDFPolicy(self, request):
            return SimpleNamespace(UDFPolicyInfos=None, RequestId="req-desc")

        def UpdateUDFPolicy(self, request):
            raise Boom("policy write dropped")

    _make_module(monkeypatch, ExplodingClient())
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "policy write dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_dlc_udf_policy.py)
# ---------------------------------------------------------------------------


def legacy_params():
    return {
        "name": NAME,
        "database_name": DATABASE,
        "catalog_name": CATALOG,
        "policy_infos": POLICY_INFOS,
    }


def test_policy_normalization_is_set_semantic():
    expected = [{"Accesses": ["select"], "Users": ["u1", "u2"], "Groups": ["g1"]}]
    assert mod.normalize(POLICY_INFOS) == expected
    assert mod.normalize([{"Groups": ["g1"], "Users": ["u1", "u2"], "Accesses": ["select"]}]) == expected
    assert mod.normalize([{"accesses": ["select"], "users": ["u1"]}, {"accesses": ["select"], "users": ["u2"], "groups": ["g1"]}]) == expected


def test_describe_and_update_requests_preserve_exact_udf_identity():
    p = legacy_params()
    describe = mod.describe_request(FakeModels(), p)
    update = mod.update_request(FakeModels(), p)
    assert describe.Name == NAME
    assert describe.DatabaseName == DATABASE
    assert describe.CatalogName == CATALOG
    assert update.Name == NAME
    assert update.DatabaseName == DATABASE
    assert update.CatalogName == CATALOG
    assert update.UDFPolicyInfos[0].Users == ["u1", "u2"]
    assert update.UDFPolicyInfos[0].Accesses == ["select"]
