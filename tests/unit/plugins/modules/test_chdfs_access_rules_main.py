"""Unit tests for the chdfs_access_rules write module (run_module flows).

Drives ``run_module()`` against an in-memory fake CHDFS client whose
create / modify / delete operations mutate an access-rule store so
post-write describes converge immediately. The module reconciles the
*complete* rule set of an access group, matched by ``address``.

Scenario matrix:

* no drift is idempotent (order-insensitive rule comparison)
* address, access-mode and priority drift create/update rules
* removed addresses are deleted by ``AccessRuleId``
* check-mode dry run and the blanket SDK failure path
* input guards: duplicate addresses, >10 rules, out-of-range priority
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import chdfs_access_rules as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ACCESS_GROUP_ID = "ag-1001"

RULES = [
    {"AccessRuleId": "ar-11", "Address": "10.0.0.0/16", "AccessMode": 2, "Priority": 10},
    {"AccessRuleId": "ar-12", "Address": "192.168.1.0/24", "AccessMode": 1, "Priority": 20},
]


def _store_rules(items):
    return [copy.deepcopy(t) for t in items]


def _desired(*items):
    return [{"address": t["Address"], "access_mode": t["AccessMode"], "priority": t["Priority"]} for t in items]


def _args(*items):
    return module_args(access_group_id=ACCESS_GROUP_ID, rules=_desired(*items))


class FakeChdfsClient(object):
    """In-memory CHDFS client mutating a small access-rule store."""

    def __init__(self, rules=None):
        self.rules = _store_rules(rules or [])
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, rule_id):
        for item in self.rules:
            if item.get("AccessRuleId") == rule_id:
                return item
        return None

    def DescribeAccessRules(self, request):
        self._record("DescribeAccessRules", request)
        return SimpleNamespace(AccessRules=[FakeResource(t) for t in self.rules])

    def CreateAccessRules(self, request):
        self._record("CreateAccessRules", request)
        for value in getattr(request, "AccessRules", None) or []:
            self._next += 1
            self.rules.append(
                {
                    "AccessRuleId": "ar-%d" % (100 + self._next),
                    "Address": getattr(value, "Address", None),
                    "AccessMode": getattr(value, "AccessMode", None),
                    "Priority": getattr(value, "Priority", None),
                }
            )
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAccessRules(self, request):
        self._record("ModifyAccessRules", request)
        for value in getattr(request, "AccessRules", None) or []:
            item = self._by_id(getattr(value, "AccessRuleId", None))
            if item is not None:
                item["AccessMode"] = getattr(value, "AccessMode", item.get("AccessMode"))
                item["Priority"] = getattr(value, "Priority", item.get("Priority"))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAccessRules(self, request):
        self._record("DeleteAccessRules", request)
        ids = list(getattr(request, "AccessRuleIds", None) or [])
        self.rules = [t for t in self.rules if t.get("AccessRuleId") not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(ChdfsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_no_drift_is_idempotent(monkeypatch):
    fake = FakeChdfsClient(rules=RULES)
    _make_module(monkeypatch, fake)
    _args(*RULES)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert [r["Address"] for r in result["rules"]] == ["10.0.0.0/16", "192.168.1.0/24"]
    assert [c for c, unused in fake.calls] == ["DescribeAccessRules"]


def test_order_does_not_matter(monkeypatch):
    fake = FakeChdfsClient(rules=list(reversed(RULES)))
    _make_module(monkeypatch, fake)
    _args(*RULES)
    result = run(mod.run_module)
    assert result["changed"] is False


def test_creates_new_rule(monkeypatch):
    fake = FakeChdfsClient(rules=RULES)
    _make_module(monkeypatch, fake)
    extra = {"AccessRuleId": "ar-13", "Address": "172.16.0.0/16", "AccessMode": 1, "Priority": 30}
    _args(*RULES + [extra])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(result["rules"]) == 3
    ops = [c for c, unused in fake.calls]
    assert "CreateAccessRules" in ops
    create_call = [r for c, r in fake.calls if c == "CreateAccessRules"][0]
    assert [getattr(x, "Address", None) for x in create_call.AccessRules] == ["172.16.0.0/16"]


def test_deletes_removed_rule(monkeypatch):
    fake = FakeChdfsClient(rules=RULES)
    _make_module(monkeypatch, fake)
    keep = RULES[0]
    _args(keep)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert [r["Address"] for r in result["rules"]] == ["10.0.0.0/16"]
    ops = [c for c, unused in fake.calls]
    assert "DeleteAccessRules" in ops
    delete_call = [r for c, r in fake.calls if c == "DeleteAccessRules"][0]
    assert list(delete_call.AccessRuleIds) == ["ar-12"]


def test_updates_drifted_rule(monkeypatch):
    fake = FakeChdfsClient(rules=RULES)
    _make_module(monkeypatch, fake)
    drifted = [
        {"AccessRuleId": "ar-11", "Address": "10.0.0.0/16", "AccessMode": 1, "Priority": 10},
        {"AccessRuleId": "ar-12", "Address": "192.168.1.0/24", "AccessMode": 2, "Priority": 40},
    ]
    _args(*drifted)
    result = run(mod.run_module)
    assert result["changed"] is True
    ops = [c for c, unused in fake.calls]
    assert "ModifyAccessRules" in ops
    assert "CreateAccessRules" not in ops
    assert "DeleteAccessRules" not in ops
    modify_call = [r for c, r in fake.calls if c == "ModifyAccessRules"][0]
    assert len(modify_call.AccessRules) == 2
    result["rules"].sort(key=lambda r: r["Address"])
    assert result["rules"][0]["AccessMode"] == 1
    assert result["rules"][1]["Priority"] == 40


def test_check_mode_is_dry_run(monkeypatch):
    fake = FakeChdfsClient(rules=RULES)
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, access_group_id=ACCESS_GROUP_ID, rules=_desired(RULES[0]))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rules"] == _desired(RULES[0])
    assert [r["Address"] for r in fake.rules] == ["10.0.0.0/16", "192.168.1.0/24"]
    assert not [c for c, unused in fake.calls if c != "DescribeAccessRules"]


def test_duplicate_addresses_fail(monkeypatch):
    fake = FakeChdfsClient(rules=[])
    _make_module(monkeypatch, fake)
    module_args(
        access_group_id=ACCESS_GROUP_ID,
        rules=[
            {"address": "10.0.0.0/16", "access_mode": 1, "priority": 10},
            {"address": "10.0.0.0/16", "access_mode": 2, "priority": 20},
        ],
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "addresses must be unique" in exc.value.args[0]["msg"]


def test_more_than_ten_rules_fail(monkeypatch):
    fake = FakeChdfsClient(rules=[])
    _make_module(monkeypatch, fake)
    module_args(
        access_group_id=ACCESS_GROUP_ID,
        rules=[{"address": "10.0.%d.0/24" % i, "access_mode": 1, "priority": i} for i in range(11)],
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "at most 10 access rules" in exc.value.args[0]["msg"]


def test_invalid_priority_fails(monkeypatch):
    fake = FakeChdfsClient(rules=[])
    _make_module(monkeypatch, fake)
    module_args(
        access_group_id=ACCESS_GROUP_ID,
        rules=[
            {"address": "10.0.0.0/16", "access_mode": 1, "priority": 10},
            {"address": "10.0.1.0/24", "access_mode": 1, "priority": 200},
        ],
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "priority must be between 1 and 100" in payload["msg"]
    assert payload["priorities"] == [200]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAccessRules(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(*RULES)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
