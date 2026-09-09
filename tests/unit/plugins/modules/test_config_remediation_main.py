"""Unit tests for the config_remediation write module (run_module flows).

Drives ``run_module()`` against an in-memory fake Config client whose
create / update / delete operations mutate a remediation store so
post-write describes converge immediately.

Scenario matrix:

* absent on a missing remediation (idempotent no-op, by rule or by id)
* absent with a matching remediation (check-mode dry run, real delete)
* present requires remediation_type/template_id/invoke_type/source_type
* creation when missing (happy path, check mode, follow-up id lookup)
* no-op when the remediation already matches
* drift triggers an update and the ambiguous-match guard
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import config_remediation as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

REMEDIATION = {
    "RemediationId": "remediation-1001",
    "RuleId": "cr-111",
    "RemediationType": "predefined",
    "RemediationTemplateId": "rt-1",
    "InvokeType": "AUTO",
    "RemediationSourceType": "CONFIG",
}


def _remediation(**overrides):
    item = copy.deepcopy(REMEDIATION)
    item.update(overrides)
    return item


def _present_args(**overrides):
    params = {
        "state": "present",
        "rule_id": "cr-111",
        "remediation_type": "predefined",
        "remediation_template_id": "rt-1",
        "invoke_type": "AUTO",
        "source_type": "CONFIG",
    }
    params.update(overrides)
    return module_args(**params)


class FakeConfigClient(object):
    """In-memory Config client mutating a small remediation store."""

    def __init__(self, remediations=None):
        self.remediations = [copy.deepcopy(t) for t in (remediations or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, remediation_id):
        for item in self.remediations:
            if item.get("RemediationId") == remediation_id:
                return item
        return None

    def ListRemediations(self, request):
        self._record("ListRemediations", request)
        rule_ids = set(getattr(request, "RuleIds", None) or [])
        matches = [t for t in self.remediations if t.get("RuleId") in rule_ids]
        return SimpleNamespace(Remediations=[FakeResource(t) for t in matches])

    def CreateRemediation(self, request):
        self._record("CreateRemediation", request)
        self._next += 1
        item = {
            "RemediationId": "remediation-%d" % (2000 + self._next),
            "RuleId": getattr(request, "RuleId", None),
            "RemediationType": getattr(request, "RemediationType", None),
            "RemediationTemplateId": getattr(request, "RemediationTemplateId", None),
            "InvokeType": getattr(request, "InvokeType", None),
            "RemediationSourceType": getattr(request, "SourceType", None),
        }
        self.remediations.append(item)
        return SimpleNamespace(RemediationId=item["RemediationId"])

    def UpdateRemediation(self, request):
        self._record("UpdateRemediation", request)
        item = self._by_id(getattr(request, "RemediationId", None))
        if item is not None:
            item["RemediationType"] = getattr(request, "RemediationType", item.get("RemediationType"))
            item["RemediationTemplateId"] = getattr(request, "RemediationTemplateId", item.get("RemediationTemplateId"))
            item["InvokeType"] = getattr(request, "InvokeType", item.get("InvokeType"))
            item["RemediationSourceType"] = getattr(request, "SourceType", item.get("RemediationSourceType"))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteRemediations(self, request):
        self._record("DeleteRemediations", request)
        ids = list(getattr(request, "RemediationIds", None) or [])
        self.remediations = [t for t in self.remediations if t.get("RemediationId") not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(ConfigClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_by_rule_is_idempotent(monkeypatch):
    fake = FakeConfigClient(remediations=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", rule_id="cr-999")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["remediation"] is None
    assert [c for c, unused in fake.calls] == ["ListRemediations"]


def test_absent_missing_by_id_is_idempotent(monkeypatch):
    fake = FakeConfigClient(remediations=[_remediation()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", rule_id="cr-111", remediation_id="remediation-9999")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["remediation"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeConfigClient(remediations=[_remediation()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", rule_id="cr-111")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["remediation"]["RemediationId"] == "remediation-1001"
    assert len(fake.remediations) == 1
    assert "DeleteRemediations" not in [c for c, unused in fake.calls]


def test_absent_deletes_remediation(monkeypatch):
    fake = FakeConfigClient(remediations=[_remediation()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", rule_id="cr-111")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["remediation"] is None
    assert fake.remediations == []
    assert "DeleteRemediations" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# present guards and creation
# ---------------------------------------------------------------------------


def test_present_requires_full_remediation_params(monkeypatch):
    fake = FakeConfigClient(remediations=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", rule_id="cr-111", remediation_type="predefined")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == (
        "remediation_type, remediation_template_id, invoke_type and source_type are required when state=present"
    )


def test_create_remediation(monkeypatch):
    fake = FakeConfigClient(remediations=[])
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["remediation"]["RemediationId"] == "remediation-2001"
    assert result["remediation"]["RuleId"] == "cr-111"
    assert result["remediation"]["InvokeType"] == "AUTO"
    assert len(fake.remediations) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "ListRemediations"
    assert "CreateRemediation" in ops
    assert ops[-1] == "ListRemediations"
    create_call = [r for c, r in fake.calls if c == "CreateRemediation"][0]
    assert create_call.SourceType == "CONFIG"


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeConfigClient(remediations=[])
    _make_module(monkeypatch, fake)
    _present_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["remediation"] is None
    assert fake.remediations == []
    assert "CreateRemediation" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing remediation flows
# ---------------------------------------------------------------------------


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeConfigClient(remediations=[_remediation()])
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["remediation"]["RemediationId"] == "remediation-1001"
    assert "UpdateRemediation" not in [c for c, unused in fake.calls]


def test_invoke_type_drift_updates(monkeypatch):
    fake = FakeConfigClient(remediations=[_remediation()])
    _make_module(monkeypatch, fake)
    _present_args(invoke_type="MANUAL")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["remediation"]["InvokeType"] == "MANUAL"
    assert "UpdateRemediation" in [c for c, unused in fake.calls]
    update_call = [r for c, r in fake.calls if c == "UpdateRemediation"][0]
    assert update_call.RemediationId == "remediation-1001"
    assert update_call.SourceType == "CONFIG"


def test_template_drift_updates(monkeypatch):
    fake = FakeConfigClient(remediations=[_remediation()])
    _make_module(monkeypatch, fake)
    _present_args(remediation_template_id="rt-2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["remediation"]["RemediationTemplateId"] == "rt-2"


def test_update_by_remediation_id(monkeypatch):
    # remediation_id pointing at a different rule's remediation: the lookup
    # prefers id, so update keys off the matched remediation, not rule_id.
    other = _remediation(RemediationId="remediation-2001", RuleId="cr-222", InvokeType="AUTO")
    fake = FakeConfigClient(remediations=[_remediation(), other])
    _make_module(monkeypatch, fake)
    _present_args(remediation_id="remediation-2001", rule_id="cr-222", invoke_type="MANUAL")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["remediation"]["RemediationId"] == "remediation-2001"
    assert result["remediation"]["InvokeType"] == "MANUAL"
    assert [t["RuleId"] for t in fake.remediations] == ["cr-111", "cr-222"]


def test_multiple_rule_matches_fail(monkeypatch):
    fake = FakeConfigClient(remediations=[_remediation(), _remediation(RemediationId="remediation-1002")])
    _make_module(monkeypatch, fake)
    _present_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "specify remediation_id" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def ListRemediations(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _present_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
