"""Unit tests for the cdwpg_hba_config write module (run_module flows).

The module replaces the complete user-managed pg_hba rule list while
preserving order. There is no delete lifecycle, so coverage centers on the
no-op, apply-drift, allow-empty clearing and validation flows. The fake CDW
PostgreSQL client mutates a rule store so the post-write describe refetch
converges.

Scenario matrix:

* argument validation (missing rules, emptying without allow_empty)
* no-op when the ordered rule list already matches
* drift applies the full replacement via ``ModifyUserHba``
* explicit clearing with ``allow_empty=true``
* check-mode dry run
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdwpg_hba_config as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "cdwpg-xxxxxxxx"


def _rule(**overrides):
    item = {"type": "hostssl", "database": "all", "user": "analysts", "address": "10.0.0.0/16", "method": "md5"}
    item.update(overrides)
    return item


def _args(**overrides):
    params = {"instance_id": INSTANCE_ID, "rules": [_rule()]}
    params.update(overrides)
    return module_args(**params)


class FakeCdwpgClient(object):
    """In-memory CDW PostgreSQL client mutating an ordered HBA rule store."""

    def __init__(self, rules=None):
        self.rules = [copy.deepcopy(r) for r in (rules or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeUserHbaConfig(self, request):
        self._record("DescribeUserHbaConfig", request)
        return SimpleNamespace(HbaConfigs=[FakeResource(r) for r in self.rules], ErrorMsg=None)

    def ModifyUserHba(self, request):
        self._record("ModifyUserHba", request)
        self.rules = []
        for item in getattr(request, "HbaConfigs", None) or []:
            self.rules.append(copy.deepcopy(vars(item)))
        return SimpleNamespace(TaskId=99, ErrorMsg=None, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(CdwpgClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_missing_rules_fails(monkeypatch):
    fake = FakeCdwpgClient()
    _make_module(monkeypatch, fake)
    module_args(instance_id=INSTANCE_ID)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rules" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_empty_rules_without_allow_empty_fails(monkeypatch):
    fake = FakeCdwpgClient()
    _make_module(monkeypatch, fake)
    _args(rules=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_empty=true" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_idempotent_when_rules_match(monkeypatch):
    current = [{"Type": "hostssl", "Database": "all", "User": "analysts", "Address": "10.0.0.0/16", "Method": "md5"}]
    fake = FakeCdwpgClient(rules=current)
    _make_module(monkeypatch, fake)
    _args(rules=[_rule()])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rules"][0]["User"] == "analysts"
    assert [c for c, unused in fake.calls] == ["DescribeUserHbaConfig"]


def test_drift_applies_full_replacement(monkeypatch):
    fake = FakeCdwpgClient(
        rules=[{"Type": "host", "Database": "all", "User": "all", "Address": "0.0.0.0/0", "Method": "reject"}]
    )
    _make_module(monkeypatch, fake)
    new_rules = [_rule(), _rule(type="host", user="all", address="0.0.0.0/0", method="reject")]
    _args(rules=new_rules)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["task_id"] == 99
    assert [rule["User"] for rule in result["rules"]] == ["analysts", "all"]
    modify_call = next((c, r) for c, r in fake.calls if c == "ModifyUserHba")
    assert len(getattr(modify_call[1], "HbaConfigs")) == 2
    assert getattr(getattr(modify_call[1], "HbaConfigs")[0], "User") == "analysts"


def test_clear_rules_with_allow_empty(monkeypatch):
    fake = FakeCdwpgClient(
        rules=[{"Type": "hostssl", "Database": "all", "User": "analysts", "Address": "10.0.0.0/16", "Method": "md5"}]
    )
    _make_module(monkeypatch, fake)
    _args(rules=[], allow_empty=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rules"] == []
    assert fake.rules == []


def test_drift_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdwpgClient(
        rules=[{"Type": "host", "Database": "all", "User": "all", "Address": "0.0.0.0/0", "Method": "reject"}]
    )
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, rules=[_rule()])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["task_id"] is None
    assert result["rules"] == [{"Type": "hostssl", "Database": "all", "User": "analysts", "Address": "10.0.0.0/16", "Method": "md5"}]
    assert "ModifyUserHba" not in [c for c, unused in fake.calls]
    assert len(fake.rules) == 1


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeUserHbaConfig(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(rules=[_rule()])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_cdwpg_hba_config.py)
# ---------------------------------------------------------------------------


def test_normalize_preserves_security_rule_order():
    rules = [
        {"type": "hostssl", "database": "all", "user": "admins", "address": "10.0.0.0/24", "method": "cert"},
        {"type": "host", "database": "all", "user": "all", "address": "0.0.0.0/0", "method": "reject"},
    ]
    assert [rule["User"] for rule in mod.normalize(rules)] == ["admins", "all"]


def test_normalize_omits_optional_mask():
    assert mod.normalize([{"type": "host", "database": "db", "user": "u", "address": "10.0.0.1/32", "method": "md5", "mask": None}])[0] == {
        "Type": "host",
        "Database": "db",
        "User": "u",
        "Address": "10.0.0.1/32",
        "Method": "md5",
    }


def test_normalize_projects_sdk_output_and_drops_nulls():
    assert mod.normalize([{"Type": "host", "Database": "db", "User": "u", "Address": "10.0.0.1/32", "Method": "md5", "Mask": None}]) == [
        {"Type": "host", "Database": "db", "User": "u", "Address": "10.0.0.1/32", "Method": "md5"}
    ]
