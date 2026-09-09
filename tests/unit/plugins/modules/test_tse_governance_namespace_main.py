"""Unit tests for the tse_governance_namespace write module.

Drives ``run_module()`` against an in-memory fake TSE governance client
whose create / modify / delete namespace calls mutate a name-keyed store so
post-write describes converge immediately.

Access-set semantics: ``user_ids`` / ``group_ids`` are exact sets. The
module translates drift into add and remove lists on modify so the fake
client applies those deltas to the stored namespace.

Scenario matrix:

* present: create, idempotent no-op, comment drift, access-set delta
  request shape, check-mode dry runs
* absent: no-op, delete, check mode
* lookup ambiguity guard and the blanket SDK failure path
* legacy pure-helper assertions folded from the shallow test file
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_governance_namespace as mod
from ansible_collections.susunola.tencentcloud.plugins.modules.tse_governance_namespace import (
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
NS_NAME = "prod"

_FIELD_KEYS = ("Comment", "UserIds", "GroupIds", "ServiceExportTo", "SyncToGlobalRegistry")


def _namespace(**fields):
    value = {"Name": NS_NAME}
    value.update(fields)
    return value


def _ns_args(**overrides):
    params = {"instance_id": INSTANCE_ID, "name": NS_NAME, "state": "present"}
    params.update(overrides)
    return module_args(**params)


class FakeGovernanceClient(object):
    """In-memory TSE governance client backed by a name-keyed namespace list."""

    def __init__(self, namespaces=None):
        self.namespaces = [dict(n) for n in namespaces or []]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeGovernanceNamespaces(self, request):
        self._record("DescribeGovernanceNamespaces", request)
        payload = [FakeResource(dict(n)) for n in self.namespaces]
        return SimpleNamespace(Content=payload, RequestId="req-fake")

    def _scalar_fields(self, source):
        return {key: getattr(source, key) for key in _FIELD_KEYS if hasattr(source, key)}

    def CreateGovernanceNamespaces(self, request):
        self._record("CreateGovernanceNamespaces", request)
        item = request.GovernanceNamespaces[0]
        value = _namespace(**self._scalar_fields(item))
        self.namespaces.append(value)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyGovernanceNamespaces(self, request):
        self._record("ModifyGovernanceNamespaces", request)
        item = request.GovernanceNamespaces[0]
        for namespace in self.namespaces:
            if namespace["Name"] == getattr(item, "Name", None):
                self._apply_deltas(namespace, item)
        return SimpleNamespace(RequestId="req-fake")

    def _apply_deltas(self, namespace, item):
        for key in ("Comment", "ServiceExportTo", "SyncToGlobalRegistry"):
            if hasattr(item, key):
                namespace[key] = getattr(item, key)
        for key, remove_key in (("UserIds", "RemoveUserIds"), ("GroupIds", "RemoveGroupIds")):
            namespace[key] = [value for value in namespace.get(key, []) if value not in getattr(item, remove_key, [])]
            namespace[key].extend(getattr(item, key, []))
            namespace[key] = sorted(set(namespace[key]))

    def DeleteGovernanceNamespaces(self, request):
        self._record("DeleteGovernanceNamespaces", request)
        item = request.GovernanceNamespaces[0]
        self.namespaces = [n for n in self.namespaces if n["Name"] != getattr(item, "Name", None)]
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
    fake = FakeGovernanceClient(namespaces=[_namespace(Comment="a"), _namespace(Comment="b")])
    _make_module(monkeypatch, fake)
    _ns_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE governance namespaces matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_creates_namespace(monkeypatch):
    fake = FakeGovernanceClient()
    _make_module(monkeypatch, fake)
    _ns_args(comment="Production services", service_export_to=["shared"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"]["Name"] == NS_NAME
    assert result["namespace"]["Comment"] == "Production services"
    assert result["namespace"]["ServiceExportTo"] == ["shared"]
    assert "CreateGovernanceNamespaces" in _names(fake)
    assert len(fake.namespaces) == 1


def test_present_no_drift_is_idempotent(monkeypatch):
    current = _namespace(Comment="Production services", UserIds=["u1"], ServiceExportTo=["shared"])
    fake = FakeGovernanceClient(namespaces=[current])
    _make_module(monkeypatch, fake)
    _ns_args(comment="Production services", user_ids=["u1"], service_export_to=["shared"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["namespace"]["Comment"] == "Production services"
    assert "CreateGovernanceNamespaces" not in _names(fake)
    assert "ModifyGovernanceNamespaces" not in _names(fake)


def test_present_comment_drift_triggers_modify(monkeypatch):
    fake = FakeGovernanceClient(namespaces=[_namespace(Comment="Old")])
    _make_module(monkeypatch, fake)
    _ns_args(comment="New")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"]["Comment"] == "New"
    assert "ModifyGovernanceNamespaces" in _names(fake)


def test_present_access_set_drift_builds_delta_request(monkeypatch):
    fake = FakeGovernanceClient(namespaces=[_namespace(UserIds=["u1", "u2"], GroupIds=["g1"])])
    _make_module(monkeypatch, fake)
    _ns_args(user_ids=["u2", "u3"], group_ids=[])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"]["UserIds"] == ["u2", "u3"]
    assert result["namespace"]["GroupIds"] == []
    payload = _last_request(fake, "ModifyGovernanceNamespaces").GovernanceNamespaces[0]
    assert payload.UserIds == ["u3"]
    assert payload.RemoveUserIds == ["u1"]
    assert payload.GroupIds == []
    assert payload.RemoveGroupIds == ["g1"]


def test_present_check_mode_is_dry_run_for_create(monkeypatch):
    fake = FakeGovernanceClient()
    _make_module(monkeypatch, fake)
    _ns_args(_ansible_check_mode=True, comment="Preview")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"]["Comment"] == "Preview"
    assert "CreateGovernanceNamespaces" not in _names(fake)
    assert fake.namespaces == []


def test_present_check_mode_is_dry_run_for_modify(monkeypatch):
    fake = FakeGovernanceClient(namespaces=[_namespace(Comment="Old")])
    _make_module(monkeypatch, fake)
    _ns_args(_ansible_check_mode=True, comment="New")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"]["Comment"] == "New"
    assert "ModifyGovernanceNamespaces" not in _names(fake)
    assert fake.namespaces[0]["Comment"] == "Old"


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_unregistered_is_idempotent(monkeypatch):
    fake = FakeGovernanceClient()
    _make_module(monkeypatch, fake)
    _ns_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["namespace"] is None
    assert "DeleteGovernanceNamespaces" not in _names(fake)


def test_absent_deletes_namespace(monkeypatch):
    fake = FakeGovernanceClient(namespaces=[_namespace(Comment="Old")])
    _make_module(monkeypatch, fake)
    _ns_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"] is None
    assert "DeleteGovernanceNamespaces" in _names(fake)
    assert fake.namespaces == []


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeGovernanceClient(namespaces=[_namespace(Comment="Old")])
    _make_module(monkeypatch, fake)
    _ns_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"] is None
    assert "DeleteGovernanceNamespaces" not in _names(fake)
    assert len(fake.namespaces) == 1


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeGovernanceNamespaces(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _ns_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy pure-helper assertions (folded from the shallow test file)
# ---------------------------------------------------------------------------


def test_legacy_access_sets_generate_adds_and_removes():
    current = {"Name": "prod", "UserIds": ["u1", "u2"], "GroupIds": ["g1"]}
    target = {"Name": "prod", "UserIds": ["u2", "u3"], "GroupIds": []}
    value = mutation(current, target)
    assert value["UserIds"] == ["u3"]
    assert value["RemoveUserIds"] == ["u1"]
    assert value["GroupIds"] == []
    assert value["RemoveGroupIds"] == ["g1"]


def test_legacy_comparison_ignores_server_statistics():
    params = {"name": "prod", "comment": "x", "user_ids": [], "group_ids": None,
              "service_export_to": None, "sync_to_global_registry": None}
    target = desired(params)
    assert comparable({"Name": "prod", "Comment": "x", "TotalServiceCount": 9, "UserIds": None}, target) == target
