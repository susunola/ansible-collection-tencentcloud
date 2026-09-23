"""Unit tests for the waf_threat_intelligence write module (run_module flows).

Drives ``run_module()`` against an in-memory fake WAF client that serves
the account-level threat-intelligence configuration and records modify
calls. ``enabled=false`` switches ``DefenseStatus`` off; the exact tag set
is sorted before comparison.

Scenario matrix:

* a matching configuration is idempotent
* tag-set and enabled-state drift trigger ModifyWafThreatenIntelligence
* an unset remote configuration reads as disabled/empty and drifts
* check-mode dry run and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import waf_threat_intelligence as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CONFIG = {"Tags": ["botnet", "scanner"], "DefenseStatus": 1}


def _config(**overrides):
    item = copy.deepcopy(CONFIG)
    item.update(overrides)
    return item


def _args(enabled=True, tags=None, **overrides):
    params = {"enabled": enabled, "tags": copy.deepcopy(list(tags)) if tags is not None else ["botnet", "scanner"]}
    params.update(overrides)
    return module_args(**params)


class FakeWafClient(object):
    """In-memory WAF client holding the account threat-intelligence config."""

    def __init__(self, config=None):
        self.config = copy.deepcopy(config)  # None means "API reports nothing yet"
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeWafThreatenIntelligence(self, request):
        self._record("DescribeWafThreatenIntelligence", request)
        details = FakeResource(copy.deepcopy(self.config)) if self.config is not None else None
        return SimpleNamespace(WafThreatenIntelligenceDetails=details)

    def ModifyWafThreatenIntelligence(self, request):
        self._record("ModifyWafThreatenIntelligence", request)
        details = getattr(request, "WafThreatenIntelligenceDetails", None)
        if details is not None:
            self.config = {"Tags": sorted(getattr(details, "Tags", None) or []), "DefenseStatus": getattr(details, "DefenseStatus", 0)}
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(WafClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_no_drift_is_idempotent(monkeypatch):
    fake = FakeWafClient(config=CONFIG)
    _make_module(monkeypatch, fake)
    _args(tags=["botnet", "scanner"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["threat_intelligence"] == CONFIG
    assert [c for c, unused in fake.calls] == ["DescribeWafThreatenIntelligence"]


def test_tag_order_does_not_matter(monkeypatch):
    fake = FakeWafClient(config=CONFIG)
    _make_module(monkeypatch, fake)
    _args(tags=["scanner", "botnet"])
    result = run(mod.run_module)
    assert result["changed"] is False


def test_tag_set_drift_updates(monkeypatch):
    fake = FakeWafClient(config=CONFIG)
    _make_module(monkeypatch, fake)
    _args(tags=["botnet", "malware"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["threat_intelligence"]["Tags"] == ["botnet", "malware"]
    modify_call = [r for c, r in fake.calls if c == "ModifyWafThreatenIntelligence"][0]
    assert sorted(modify_call.WafThreatenIntelligenceDetails.Tags) == ["botnet", "malware"]
    assert modify_call.WafThreatenIntelligenceDetails.DefenseStatus == 1


def test_disabling_turns_defense_off(monkeypatch):
    fake = FakeWafClient(config=CONFIG)
    _make_module(monkeypatch, fake)
    _args(enabled=False, tags=["botnet", "scanner"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["threat_intelligence"]["DefenseStatus"] == 0
    modify_call = [r for c, r in fake.calls if c == "ModifyWafThreatenIntelligence"][0]
    assert modify_call.WafThreatenIntelligenceDetails.DefenseStatus == 0


def test_unset_remote_configuration_drifts(monkeypatch):
    fake = FakeWafClient(config=None)
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["threat_intelligence"] == CONFIG
    assert "ModifyWafThreatenIntelligence" in [c for c, unused in fake.calls]


def test_clearing_tags_with_disabled_state(monkeypatch):
    fake = FakeWafClient(config=CONFIG)
    _make_module(monkeypatch, fake)
    _args(enabled=False, tags=[])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["threat_intelligence"] == {"Tags": [], "DefenseStatus": 0}


def test_check_mode_is_dry_run(monkeypatch):
    fake = FakeWafClient(config=CONFIG)
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, tags=["botnet"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["threat_intelligence"]["Tags"] == ["botnet"]
    assert fake.config == CONFIG
    assert not [c for c, unused in fake.calls if c != "DescribeWafThreatenIntelligence"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeWafThreatenIntelligence(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
