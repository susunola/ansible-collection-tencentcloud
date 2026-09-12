"""Unit tests for the tcr_webhook_trigger write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TCR client that
mutates a webhook-trigger store keyed by (registry, namespace, name), so the
module's post-write ``DescribeWebhookTrigger`` refetch observes the new state
immediately.

Scenario matrix:

* create when missing (real Create + converged refetch)
* idempotent no-op when the trigger already exists
* absent when missing (no-op)
* delete when present (real Delete + converged refetch)
* check-mode dry run for create (no Create call)
* check-mode dry run for delete (no Delete call)
* missing Name fails
* SDK failure surfaces via fail_sdk_error
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tcr_webhook_trigger as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _trigger(tid, ns, name, enabled=True):
    return FakeResource({
        "Id": str(tid),
        "NamespaceName": ns,
        "Name": name,
        "Description": "",
        "Enabled": enabled,
        "Condition": "all",
        "EventTypes": ["PUSH_IMAGE"],
        "Targets": [],
    })


class FakeTcrClient(object):
    """In-memory TCR client mutating a webhook-trigger store."""

    def __init__(self, triggers=None):
        self.triggers = list(triggers or [])
        self._seq = 0
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeWebhookTrigger(self, request):
        self._record("DescribeWebhookTrigger", request)
        registry = getattr(request, "RegistryId", None)
        ns = getattr(request, "Namespace", None)
        matched = [t for t in self.triggers
                   if t._data.get("RegistryId", registry) == registry and t.NamespaceName == ns]
        return SimpleNamespace(Triggers=[FakeResource(dict(t._data)) for t in matched],
                               TotalCount=len(matched), RequestId="req-fake")

    def CreateWebhookTrigger(self, request):
        self._record("CreateWebhookTrigger", request)
        self._seq += 1
        trig = request.Trigger if isinstance(getattr(request, "Trigger", None), dict) else {}
        item = _trigger(self._seq, getattr(request, "Namespace", ""), trig.get("Name"), trig.get("Enabled", True))
        item._data["RegistryId"] = getattr(request, "RegistryId", None)
        self.triggers.append(item)
        return SimpleNamespace(Trigger=FakeResource(dict(item._data)), RequestId="req-fake")

    def DeleteWebhookTrigger(self, request):
        self._record("DeleteWebhookTrigger", request)
        registry = getattr(request, "RegistryId", None)
        ns = getattr(request, "Namespace", None)
        tid = getattr(request, "Id", None)
        self.triggers = [t for t in self.triggers
                         if not (t._data.get("RegistryId", registry) == registry
                                 and t.NamespaceName == ns and t.Id == tid)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_tcr", lambda: (models or FakeModels(), SimpleNamespace(TcrClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


TRIGGER = {"Name": "push-notify", "Enabled": True, "Condition": "all", "EventTypes": ["PUSH_IMAGE"], "Targets": ["https://hooks.example.com/tcr"]}


# ---------------------------------------------------------------------------
# create / delete flows
# ---------------------------------------------------------------------------


def test_create_when_missing(monkeypatch):
    fake = FakeTcrClient(triggers=[])
    _make_module(monkeypatch, fake)
    module_args(registry_id="tcr-abc", namespace="prod", trigger=dict(TRIGGER), state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is True
    assert result["trigger_id"] is not None
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeWebhookTrigger"
    assert "CreateWebhookTrigger" in ops
    assert "DeleteWebhookTrigger" not in ops
    created = [r for c, r in fake.calls if c == "CreateWebhookTrigger"][0]
    assert created.Trigger["Name"] == "push-notify"
    assert created.Namespace == "prod"


def test_delete_when_present(monkeypatch):
    fake = FakeTcrClient(triggers=[_trigger(1, "prod", "push-notify")])
    fake.triggers[0]._data["RegistryId"] = "tcr-abc"
    _make_module(monkeypatch, fake)
    module_args(registry_id="tcr-abc", namespace="prod", trigger=dict(TRIGGER), state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["exists"] is False
    assert "DeleteWebhookTrigger" in [c for c, unused in fake.calls]
    assert "CreateWebhookTrigger" not in [c for c, unused in fake.calls]
    assert fake.triggers == []


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_already_present_is_idempotent(monkeypatch):
    fake = FakeTcrClient(triggers=[_trigger(1, "prod", "push-notify")])
    fake.triggers[0]._data["RegistryId"] = "tcr-abc"
    _make_module(monkeypatch, fake)
    module_args(registry_id="tcr-abc", namespace="prod", trigger=dict(TRIGGER), state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["trigger_id"] == "1"
    assert [c for c, unused in fake.calls] == ["DescribeWebhookTrigger"]
    assert "CreateWebhookTrigger" not in [c for c, unused in fake.calls]


def test_absent_when_missing_is_idempotent(monkeypatch):
    fake = FakeTcrClient(triggers=[])
    _make_module(monkeypatch, fake)
    module_args(registry_id="tcr-abc", namespace="prod", trigger=dict(TRIGGER), state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "DeleteWebhookTrigger" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# check-mode dry runs
# ---------------------------------------------------------------------------


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTcrClient(triggers=[])
    _make_module(monkeypatch, fake)
    module_args(registry_id="tcr-abc", namespace="prod", trigger=dict(TRIGGER), state="present",
                _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "CreateWebhookTrigger" not in [c for c, unused in fake.calls]
    assert fake.triggers == []


def test_delete_check_mode_is_dry_run(monkeypatch):
    fake = FakeTcrClient(triggers=[_trigger(1, "prod", "push-notify")])
    fake.triggers[0]._data["RegistryId"] = "tcr-abc"
    _make_module(monkeypatch, fake)
    module_args(registry_id="tcr-abc", namespace="prod", trigger=dict(TRIGGER), state="absent",
                _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "DeleteWebhookTrigger" not in [c for c, unused in fake.calls]
    assert len(fake.triggers) == 1


# ---------------------------------------------------------------------------
# error / validation paths
# ---------------------------------------------------------------------------


def test_missing_name_fails(monkeypatch):
    fake = FakeTcrClient(triggers=[])
    _make_module(monkeypatch, fake)
    module_args(registry_id="tcr-abc", namespace="prod", trigger={"Enabled": True}, state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        payload = getattr(exc, "args", [{}])[0]
        assert payload.get("failed")
    else:
        raise AssertionError("expected missing-name validation to fail the module")


def test_sdk_failure_fails(monkeypatch):
    fake = FakeTcrClient(triggers=[])

    def _raise_error(request):
        raise RuntimeError("boom")
    fake.CreateWebhookTrigger = _raise_error
    _make_module(monkeypatch, fake)
    module_args(registry_id="tcr-abc", namespace="prod", trigger=dict(TRIGGER), state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        payload = getattr(exc, "args", [{}])[0]
        assert payload.get("failed")
    else:
        raise AssertionError("expected SDK failure to fail the module")
