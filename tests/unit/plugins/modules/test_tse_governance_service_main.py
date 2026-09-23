"""Unit tests for the tse_governance_service write module.

Drives ``run_module()`` against an in-memory fake TSE governance client
whose create / modify / delete service calls mutate a (name, namespace)-
keyed store so post-write describes converge immediately.

Operator-set semantics: ``user_ids`` / ``group_ids`` and the visibility
set ``export_to`` are exact. Drift on operator sets is translated into
add/remove lists on modify, which the fake client applies to the store.

Scenario matrix:

* present: create, idempotent no-op, comment drift, operator-set delta
  request shape, export_to drift, check-mode dry runs
* absent: no-op, delete, check mode
* lookup ambiguity guard and the blanket SDK failure path
* legacy pure-helper assertions folded from the shallow test file
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_governance_service as mod
from ansible_collections.susunola.tencentcloud.plugins.modules.tse_governance_service import (
    comparable,
    desired,
    mutation,
)
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "ins-1"
NAMESPACE = "prod"
SERVICE_NAME = "orders"

_FIELD_KEYS = ("Comment", "Department", "Business", "Metadatas", "ExportTo", "SyncToGlobalRegistry", "Type")


def _service(**fields):
    value = {"Name": SERVICE_NAME, "Namespace": NAMESPACE, "Type": 0}
    value.update(fields)
    return value


def _service_args(**overrides):
    params = {"instance_id": INSTANCE_ID, "namespace": NAMESPACE, "name": SERVICE_NAME, "state": "present"}
    params.update(overrides)
    return module_args(**params)


class FakeGovernanceClient(object):
    """In-memory TSE governance client backed by a (name, namespace)-keyed list."""

    def __init__(self, services=None):
        self.services = [dict(s) for s in services or []]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeGovernanceServices(self, request):
        self._record("DescribeGovernanceServices", request)
        payload = [FakeResource(dict(s)) for s in self.services]
        return SimpleNamespace(Content=payload, RequestId="req-fake")

    def _scalar_fields(self, source):
        return {key: getattr(source, key) for key in _FIELD_KEYS if hasattr(source, key)}

    def CreateGovernanceServices(self, request):
        self._record("CreateGovernanceServices", request)
        item = request.GovernanceServices[0]
        value = _service(**self._scalar_fields(item))
        self.services.append(value)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyGovernanceServices(self, request):
        self._record("ModifyGovernanceServices", request)
        item = request.GovernanceServices[0]
        for service in self.services:
            if service["Name"] == getattr(item, "Name", None) and service["Namespace"] == getattr(item, "Namespace", None):
                self._apply_deltas(service, item)
        return SimpleNamespace(RequestId="req-fake")

    def _apply_deltas(self, service, item):
        for key in ("Comment", "Department", "Business", "Metadatas", "ExportTo", "SyncToGlobalRegistry", "Type"):
            if hasattr(item, key):
                service[key] = getattr(item, key)
        for key, remove_key in (("UserIds", "RemoveUserIds"), ("GroupIds", "RemoveGroupIds")):
            service[key] = [v for v in service.get(key, []) if v not in getattr(item, remove_key, [])]
            service[key].extend(getattr(item, key, []))
            service[key] = sorted(set(service[key]))

    def DeleteGovernanceServices(self, request):
        self._record("DeleteGovernanceServices", request)
        item = request.GovernanceServices[0]
        self.services = [s for s in self.services
                         if not (s["Name"] == getattr(item, "Name", None)
                                 and s["Namespace"] == getattr(item, "Namespace", None))]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [c for c, unused in fake.calls]


def _last_request(fake, api):
    for name, request in reversed(fake.calls):
        if name == api:
            return request
    return None


# ---------------------------------------------------------------------------
# lookup semantics
# ---------------------------------------------------------------------------


def test_multiple_name_matches_fail(monkeypatch):
    fake = FakeGovernanceClient(services=[_service(Comment="a"), _service(Comment="b")])
    _make_module(monkeypatch, fake)
    _service_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE governance services matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_creates_service(monkeypatch):
    fake = FakeGovernanceClient()
    _make_module(monkeypatch, fake)
    _service_args(comment="Ordering API", export_to=["shared"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["Name"] == SERVICE_NAME
    assert result["service"]["Namespace"] == NAMESPACE
    assert result["service"]["Comment"] == "Ordering API"
    assert result["service"]["ExportTo"] == ["shared"]
    assert result["service"]["Type"] == 0
    assert "CreateGovernanceServices" in _names(fake)
    assert len(fake.services) == 1


def test_present_no_drift_is_idempotent(monkeypatch):
    current = _service(Comment="Ordering API", UserIds=["u1"], ExportTo=["shared"])
    fake = FakeGovernanceClient(services=[current])
    _make_module(monkeypatch, fake)
    _service_args(comment="Ordering API", user_ids=["u1"], export_to=["shared"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["service"]["Comment"] == "Ordering API"
    assert "CreateGovernanceServices" not in _names(fake)
    assert "ModifyGovernanceServices" not in _names(fake)


def test_present_comment_drift_triggers_modify(monkeypatch):
    fake = FakeGovernanceClient(services=[_service(Comment="Old")])
    _make_module(monkeypatch, fake)
    _service_args(comment="New")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["Comment"] == "New"
    assert "ModifyGovernanceServices" in _names(fake)


def test_present_operator_set_drift_builds_delta_request(monkeypatch):
    fake = FakeGovernanceClient(services=[_service(UserIds=["u1", "u2"], GroupIds=["g1"])])
    _make_module(monkeypatch, fake)
    _service_args(user_ids=["u2", "u3"], group_ids=[])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["UserIds"] == ["u2", "u3"]
    assert result["service"]["GroupIds"] == []
    payload = _last_request(fake, "ModifyGovernanceServices").GovernanceServices[0]
    assert payload.UserIds == ["u3"]
    assert payload.RemoveUserIds == ["u1"]
    assert payload.GroupIds == []
    assert payload.RemoveGroupIds == ["g1"]


def test_present_export_set_drift_replaces_visibility(monkeypatch):
    fake = FakeGovernanceClient(services=[_service(ExportTo=["shared", "legacy"])])
    _make_module(monkeypatch, fake)
    _service_args(export_to=["shared"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["ExportTo"] == ["shared"]
    assert "ModifyGovernanceServices" in _names(fake)


def test_present_check_mode_is_dry_run_for_create(monkeypatch):
    fake = FakeGovernanceClient()
    _make_module(monkeypatch, fake)
    _service_args(_ansible_check_mode=True, comment="Preview")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["Comment"] == "Preview"
    assert "CreateGovernanceServices" not in _names(fake)
    assert fake.services == []


def test_present_check_mode_is_dry_run_for_modify(monkeypatch):
    fake = FakeGovernanceClient(services=[_service(Comment="Old")])
    _make_module(monkeypatch, fake)
    _service_args(_ansible_check_mode=True, comment="New")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"]["Comment"] == "New"
    assert "ModifyGovernanceServices" not in _names(fake)
    assert fake.services[0]["Comment"] == "Old"


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_unregistered_is_idempotent(monkeypatch):
    fake = FakeGovernanceClient()
    _make_module(monkeypatch, fake)
    _service_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["service"] is None
    assert "DeleteGovernanceServices" not in _names(fake)


def test_absent_deletes_service(monkeypatch):
    fake = FakeGovernanceClient(services=[_service(Comment="Old")])
    _make_module(monkeypatch, fake)
    _service_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"] is None
    assert "DeleteGovernanceServices" in _names(fake)
    assert fake.services == []


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeGovernanceClient(services=[_service(Comment="Old")])
    _make_module(monkeypatch, fake)
    _service_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service"] is None
    assert "DeleteGovernanceServices" not in _names(fake)
    assert len(fake.services) == 1


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeGovernanceServices(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _service_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy pure-helper assertions (folded from the shallow test file)
# ---------------------------------------------------------------------------


def test_legacy_identity_and_exact_access_sets():
    params = {"name": SERVICE_NAME, "namespace": NAMESPACE, "comment": None, "department": None,
              "business": None, "metadata": None, "user_ids": ["u2"], "group_ids": [],
              "export_to": ["shared"], "sync_to_global_registry": None, "service_type": 0}
    target = desired(params)
    current = {"Name": SERVICE_NAME, "Namespace": NAMESPACE, "UserIds": ["u1"], "GroupIds": [],
               "ExportTo": ["shared"], "Type": 0, "HealthyInstanceCount": 3}
    value = mutation(current, target)
    assert value["UserIds"] == ["u2"]
    assert value["RemoveUserIds"] == ["u1"]
    assert comparable(dict(current, UserIds=["u2"]), target) == target
