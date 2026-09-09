"""Unit tests for the cdwch_parameter write module (run_module flows).

The module reconciles one instance key/value parameter: adds it when the
service exposes it unconfigured, updates it when the value drifts and
deletes it for ``state=absent``. The fake CDW ClickHouse client moves items
between its configured/unconfigured lists so the post-write describe and
the optional waiter converge immediately.

Scenario matrix:

* argument validation (missing required args, present without value)
* no-op when the configured value already matches
* add / update / delete flows plus their check-mode dry runs
* delete of an unconfigured parameter is idempotent
* an unexposed parameter cannot be added
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdwch_parameter as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "cdwch-xxxxxxxx"
NAME = "max_concurrent_queries"


def _args(**overrides):
    params = {"instance_id": INSTANCE_ID, "name": NAME, "state": "present", "value": "200"}
    params.update(overrides)
    return module_args(**params)


class FakeCdwchClient(object):
    """In-memory CDW ClickHouse client with configured/unconfigured items."""

    def __init__(self, configured=None, available=None):
        self.configured = [copy.deepcopy(i) for i in (configured or [])]
        self.available = [copy.deepcopy(i) for i in (available or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _describe_items(self, name):
        configured = [i for i in self.configured if i.get("ConfKey") == name]
        available = [i for i in self.available if i.get("ConfKey") == name]
        return configured, available

    def DescribeInstanceKeyValConfigs(self, request):
        self._record("DescribeInstanceKeyValConfigs", request)
        configured, available = self._describe_items(getattr(request, "SearchConfigName", None))
        return SimpleNamespace(
            ConfigItems=[FakeResource(i) for i in configured],
            UnConfigItems=[FakeResource(i) for i in available],
            ErrorMsg=None,
        )

    def ModifyInstanceKeyValConfigs(self, request):
        self._record("ModifyInstanceKeyValConfigs", request)
        for item in getattr(request, "AddItems", None) or []:
            self.configured.append({"ConfKey": item.ConfKey, "ConfValue": item.ConfValue, "NeedRestart": item.NeedRestart})
        for item in getattr(request, "UpdateItems", None) or []:
            for entry in self.configured:
                if entry.get("ConfKey") == item.ConfKey:
                    entry["ConfValue"] = item.ConfValue
        for item in getattr(request, "DelItems", None) or []:
            self.configured = [i for i in self.configured if i.get("ConfKey") != item.ConfKey]
        return SimpleNamespace(FlowId=777, ErrorMsg=None, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(CdwchClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_missing_required_args_fails(monkeypatch):
    fake = FakeCdwchClient()
    _make_module(monkeypatch, fake)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "missing required arguments" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_present_without_value_fails(monkeypatch):
    fake = FakeCdwchClient(available=[{"ConfKey": NAME}])
    _make_module(monkeypatch, fake)
    params = {"instance_id": INSTANCE_ID, "name": NAME, "state": "present"}
    module_args(**params)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "value" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_idempotent_when_value_matches(monkeypatch):
    fake = FakeCdwchClient(configured=[{"ConfKey": NAME, "ConfValue": "200", "NeedRestart": False}])
    _make_module(monkeypatch, fake)
    _args(value="200")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["parameter"]["ConfValue"] == "200"
    assert result["restart_required"] is False
    assert [c for c, unused in fake.calls] == ["DescribeInstanceKeyValConfigs"]


def test_add_unconfigured_parameter(monkeypatch):
    fake = FakeCdwchClient(available=[{"ConfKey": NAME, "ConfValue": None, "NeedRestart": True}])
    _make_module(monkeypatch, fake)
    _args(value="200", remark="Managed by Ansible")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter"]["ConfValue"] == "200"
    assert result["flow_id"] == 777
    add_call = next((c, r) for c, r in fake.calls if c == "ModifyInstanceKeyValConfigs")
    assert getattr(add_call[1], "AddItems")[0].ConfKey == NAME
    assert getattr(add_call[1], "AddItems")[0].ModifyType == "add"
    assert fake.configured[0]["ConfValue"] == "200"


def test_update_drift_changes_value(monkeypatch):
    fake = FakeCdwchClient(configured=[{"ConfKey": NAME, "ConfValue": "16", "NeedRestart": True}])
    _make_module(monkeypatch, fake)
    _args(value="32")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter"]["ConfValue"] == "32"
    assert result["restart_required"] is True
    update_call = next((c, r) for c, r in fake.calls if c == "ModifyInstanceKeyValConfigs")
    item = getattr(update_call[1], "UpdateItems")[0]
    assert item.ModifyType == "update"
    assert item.OriginalConfValue == "16"
    assert item.ConfValue == "32"


def test_add_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdwchClient(available=[{"ConfKey": NAME, "ConfValue": None, "NeedRestart": False}])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, value="200")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter"] == {"ConfKey": NAME, "ConfValue": "200"}
    assert result["flow_id"] is None
    assert "ModifyInstanceKeyValConfigs" not in [c for c, unused in fake.calls]
    assert fake.configured == []


def test_unexposed_parameter_cannot_be_added(monkeypatch):
    fake = FakeCdwchClient()
    _make_module(monkeypatch, fake)
    _args(value="200")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "not exposed as configurable" in exc.value.args[0]["msg"]


def test_absent_deletes_configured_parameter(monkeypatch):
    fake = FakeCdwchClient(configured=[{"ConfKey": NAME, "ConfValue": "16", "NeedRestart": False}])
    _make_module(monkeypatch, fake)
    _args(state="absent", value=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter"] is None
    assert fake.configured == []
    delete_call = next((c, r) for c, r in fake.calls if c == "ModifyInstanceKeyValConfigs")
    assert getattr(delete_call[1], "DelItems")[0].ModifyType == "delete"


def test_absent_unconfigured_parameter_is_idempotent(monkeypatch):
    fake = FakeCdwchClient()
    _make_module(monkeypatch, fake)
    _args(state="absent", value=None)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["parameter"] is None
    assert "ModifyInstanceKeyValConfigs" not in [c for c, unused in fake.calls]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdwchClient(configured=[{"ConfKey": NAME, "ConfValue": "16", "NeedRestart": False}])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent", value=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.configured) == 1
    assert "ModifyInstanceKeyValConfigs" not in [c for c, unused in fake.calls]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeInstanceKeyValConfigs(self, request):
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
# legacy helper regression tests (folded from test_cdwch_parameter.py)
# ---------------------------------------------------------------------------


def test_update_request_preserves_original_and_restart_metadata():
    params = {"instance_id": "cdwch-1", "name": "max_threads", "value": "32", "remark": "managed", "state": "present"}
    request = mod.change_request(FakeModels(), params, {"ConfValue": "16", "NeedRestart": True}, None)
    assert request.UpdateItems[0].ModifyType == "update"
    assert request.UpdateItems[0].OriginalConfValue == "16"
    assert request.UpdateItems[0].NeedRestart is True


def test_absent_uses_del_items():
    params = {"instance_id": "cdwch-1", "name": "max_threads", "value": None, "remark": None, "state": "absent"}
    assert mod.change_request(FakeModels(), params, {"ConfValue": "16"}, None).DelItems[0].ModifyType == "delete"
