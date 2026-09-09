"""Unit tests for the cdwpg_parameter write module (run_module flows).

The module reconciles one CN or DN parameter across its node type, restoring
the service default for ``state=default``. The fake CDW PostgreSQL client
mutates a detail store so the post-write describe refetch converges.

Scenario matrix:

* argument validation (missing required args, present without value)
* a parameter that does not exist fails
* no-op when the effective value already matches
* explicit value changes and ``state=default`` restoration
* check-mode dry run
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdwpg_parameter as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "cdwpg-xxxxxxxx"
NAME = "max_connections"


def _args(**overrides):
    params = {"instance_id": INSTANCE_ID, "node_type": "cn", "name": NAME, "state": "present", "value": "200"}
    params.update(overrides)
    return module_args(**params)


class FakeCdwpgClient(object):
    """In-memory CDW PostgreSQL client with mutable per-node parameter details."""

    def __init__(self, details=None, node_type="CN"):
        self.details = [copy.deepcopy(d) for d in (details or [])]
        self.node_type = node_type
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeDBParams(self, request):
        self._record("DescribeDBParams", request)
        return SimpleNamespace(
            Items=[SimpleNamespace(NodeType=self.node_type, Details=[FakeResource(d) for d in self.details])],
            TotalCount=str(len(self.details)),
            ErrorMsg=None,
        )

    def ModifyDBParameters(self, request):
        self._record("ModifyDBParameters", request)
        node = getattr(request, "NodeConfigParams", None)[0]
        config = getattr(node, "ConfigParams", None)[0]
        for detail in self.details:
            if detail.get("ParamName") == config.ParameterName:
                detail["LatestValue"] = config.ParameterValue
        return SimpleNamespace(TaskId=42, ErrorMsg=None, RequestId="req-fake")


def _detail(**overrides):
    item = {"ParamName": NAME, "RunningValue": "100", "LatestValue": "", "DefaultValue": "100", "NeedRestart": True}
    item.update(overrides)
    return item


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(CdwpgClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_missing_required_args_fails(monkeypatch):
    fake = FakeCdwpgClient()
    _make_module(monkeypatch, fake)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "missing required arguments" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_present_without_value_fails(monkeypatch):
    fake = FakeCdwpgClient(details=[_detail()])
    _make_module(monkeypatch, fake)
    module_args(instance_id=INSTANCE_ID, node_type="cn", name=NAME, state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "value" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_unknown_parameter_fails(monkeypatch):
    fake = FakeCdwpgClient()
    _make_module(monkeypatch, fake)
    _args(value="200")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "parameter was not found" in exc.value.args[0]["msg"]


def test_idempotent_when_value_matches(monkeypatch):
    fake = FakeCdwpgClient(details=[_detail(LatestValue="")])
    _make_module(monkeypatch, fake)
    _args(value="100")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["parameter"]["EffectiveValue"] == "100"
    assert result["restart_required"] is True
    assert [c for c, unused in fake.calls] == ["DescribeDBParams"]


def test_change_value_applies_parameter(monkeypatch):
    fake = FakeCdwpgClient(details=[_detail()])
    _make_module(monkeypatch, fake)
    _args(value="200")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["task_id"] == 42
    assert result["parameter"]["EffectiveValue"] == "200"
    modify_call = next((c, r) for c, r in fake.calls if c == "ModifyDBParameters")
    config = getattr(getattr(modify_call[1], "NodeConfigParams")[0], "ConfigParams")[0]
    assert config.ParameterName == NAME
    assert config.ParameterValue == "200"
    assert config.ParameterOldValue == "100"


def test_change_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdwpgClient(details=[_detail()])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, value="200")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter"] == {"ParamName": NAME, "EffectiveValue": "200"}
    assert result["task_id"] is None
    assert "ModifyDBParameters" not in [c for c, unused in fake.calls]


def test_restore_default_when_drifted(monkeypatch):
    fake = FakeCdwpgClient(details=[_detail(RunningValue="200", LatestValue="200")])
    _make_module(monkeypatch, fake)
    _args(state="default", value=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter"]["EffectiveValue"] == "100"
    modify_call = next((c, r) for c, r in fake.calls if c == "ModifyDBParameters")
    config = getattr(getattr(modify_call[1], "NodeConfigParams")[0], "ConfigParams")[0]
    assert config.ParameterValue == "100"
    assert config.ParameterOldValue == "200"


def test_restore_default_is_idempotent(monkeypatch):
    fake = FakeCdwpgClient(details=[_detail()])
    _make_module(monkeypatch, fake)
    _args(state="default", value=None)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "ModifyDBParameters" not in [c for c, unused in fake.calls]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeDBParams(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(value="200")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_cdwpg_parameter.py)
# ---------------------------------------------------------------------------


def test_effective_value_prefers_pending_latest_value():
    assert mod.effective_value({"RunningValue": "100", "LatestValue": "200"}) == "200"


def test_effective_value_falls_back_to_running_value():
    assert mod.effective_value({"RunningValue": "100", "LatestValue": ""}) == "100"
