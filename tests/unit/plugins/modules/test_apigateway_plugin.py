"""Unit tests for the apigateway_plugin write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake API GW client that
mutates a plugin store keyed by name, so the module's post-write
``DescribePlugins`` refetch observes the new state immediately. The API GW
describe/create responses wrap the object in a C(Result) field
(C(PluginSummary.PluginSet) for describe, C(Plugin.PluginId) for create), which
the module unwraps.

Scenario matrix:

* create when missing (real Create + converged refetch)
* idempotent no-op when the plugin already exists
* absent when missing (no-op)
* delete when present (real Delete + converged refetch)
* check-mode dry run for create (no Create call)
* check-mode dry run for delete (no Delete call)
* missing plugin_type/plugin_data on present fails (required_if)
* SDK failure surfaces via fail_sdk_error
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import apigateway_plugin as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _plugin(pid, name):
    return FakeResource({"PluginId": str(pid), "PluginName": name, "PluginType": "IPControl", "PluginData": "{}"})


class FakeApigwClient(object):
    """In-memory API GW client mutating a plugin store keyed by name."""

    def __init__(self, plugins=None):
        self.plugins = list(plugins or [])
        self._seq = 0
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribePlugins(self, request):
        self._record("DescribePlugins", request)
        wanted = getattr(request, "PluginName", None)
        if wanted:
            matched = [p for p in self.plugins if p.PluginName == wanted]
        else:
            matched = list(self.plugins)
        summary = SimpleNamespace(PluginSet=[FakeResource(dict(p._data)) for p in matched],
                                  TotalCount=len(matched))
        return SimpleNamespace(Result=summary, RequestId="req-fake")

    def CreatePlugin(self, request):
        self._record("CreatePlugin", request)
        self._seq += 1
        item = _plugin(self._seq, getattr(request, "PluginName", ""))
        self.plugins.append(item)
        return SimpleNamespace(Result=SimpleNamespace(PluginId=item.PluginId), RequestId="req-fake")

    def DeletePlugin(self, request):
        self._record("DeletePlugin", request)
        pid = getattr(request, "PluginId", None)
        self.plugins = [p for p in self.plugins if p.PluginId != pid]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(ApigatewayClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


PLUGIN_DATA = '{"type":"ALLOW","ipList":["10.0.0.0/8"]}'


# ---------------------------------------------------------------------------
# create / delete flows
# ---------------------------------------------------------------------------


def test_create_when_missing(monkeypatch):
    fake = FakeApigwClient(plugins=[])
    _make_module(monkeypatch, fake)
    module_args(plugin_name="allow-office", plugin_type="IPControl", plugin_data=PLUGIN_DATA, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is True
    assert result["plugin_id"] is not None
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribePlugins"
    assert "CreatePlugin" in ops
    assert "DeletePlugin" not in ops
    created = [r for c, r in fake.calls if c == "CreatePlugin"][0]
    assert created.PluginName == "allow-office"
    assert created.PluginType == "IPControl"


def test_delete_when_present(monkeypatch):
    fake = FakeApigwClient(plugins=[_plugin(1, "allow-office")])
    _make_module(monkeypatch, fake)
    module_args(plugin_name="allow-office", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is False
    assert "DeletePlugin" in [c for c, unused in fake.calls]
    assert "CreatePlugin" not in [c for c, unused in fake.calls]
    assert fake.plugins == []


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_already_present_is_idempotent(monkeypatch):
    fake = FakeApigwClient(plugins=[_plugin(1, "allow-office")])
    _make_module(monkeypatch, fake)
    module_args(plugin_name="allow-office", plugin_type="IPControl", plugin_data=PLUGIN_DATA, state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["plugin_id"] == "1"
    assert [c for c, unused in fake.calls] == ["DescribePlugins"]
    assert "CreatePlugin" not in [c for c, unused in fake.calls]


def test_absent_when_missing_is_idempotent(monkeypatch):
    fake = FakeApigwClient(plugins=[])
    _make_module(monkeypatch, fake)
    module_args(plugin_name="allow-office", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "DeletePlugin" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# check-mode dry runs
# ---------------------------------------------------------------------------


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeApigwClient(plugins=[])
    _make_module(monkeypatch, fake)
    module_args(plugin_name="allow-office", plugin_type="IPControl", plugin_data=PLUGIN_DATA,
                state="present", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "CreatePlugin" not in [c for c, unused in fake.calls]
    assert fake.plugins == []


def test_delete_check_mode_is_dry_run(monkeypatch):
    fake = FakeApigwClient(plugins=[_plugin(1, "allow-office")])
    _make_module(monkeypatch, fake)
    module_args(plugin_name="allow-office", state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "DeletePlugin" not in [c for c, unused in fake.calls]
    assert len(fake.plugins) == 1


# ---------------------------------------------------------------------------
# error / validation paths
# ---------------------------------------------------------------------------


def test_missing_plugin_type_on_present_fails(monkeypatch):
    fake = FakeApigwClient(plugins=[])
    _make_module(monkeypatch, fake)
    module_args(plugin_name="allow-office", plugin_data=PLUGIN_DATA, state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        payload = getattr(exc, "args", [{}])[0]
        assert payload.get("failed")
    else:
        raise AssertionError("expected required_if plugin_type/plugin_data to fail the module")


def test_sdk_failure_fails(monkeypatch):
    fake = FakeApigwClient(plugins=[])
    fake.CreatePlugin = lambda request: (_ for _ in ()).throw(RuntimeError("boom"))
    _make_module(monkeypatch, fake)
    module_args(plugin_name="allow-office", plugin_type="IPControl", plugin_data=PLUGIN_DATA, state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        payload = getattr(exc, "args", [{}])[0]
        assert payload.get("failed")
    else:
        raise AssertionError("expected SDK failure to fail the module")
