"""Unit tests for the tsf_vm_deployment_group write module.

Drives ``run_module()`` against an in-memory fake TSF client whose group
describe / create / modify / delete calls mutate a scoped group list so
post-write describes converge immediately.

Deployment-group semantics: the owning scope (application, namespace,
cluster) and resource type are immutable after creation; only the display
metadata (name, description, alias) is mutable. Package deployment and
runtime state are deliberately out of this module's scope.

Scenario matrix:

* present: create, no-drift no-op, description/alias drift update,
  check-mode dry runs, immutable scope drift rejection
* absent: no-op, delete, check mode, rejected delete / update
* lookup ambiguity guard and the blanket SDK failure path
* legacy pure-helper assertions folded from the shallow test file
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tsf_vm_deployment_group as mod
from ansible_collections.susunola.tencentcloud.plugins.modules.tsf_vm_deployment_group import comparable, desired
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP_NAME = "orders"
APP_ID = "app-1"
NAMESPACE_ID = "ns-1"
CLUSTER_ID = "cluster-1"

_STORE_KEYS = ("GroupName", "ApplicationId", "NamespaceId", "ClusterId",
               "GroupDesc", "Alias", "GroupResourceType")
_MUTABLE_KEYS = ("GroupName", "GroupDesc", "Alias")


def _group(group_id, **overrides):
    value = {"GroupId": group_id, "GroupName": GROUP_NAME, "ApplicationId": APP_ID,
             "NamespaceId": NAMESPACE_ID, "ClusterId": CLUSTER_ID,
             "GroupDesc": "prod", "Alias": "Orders", "GroupResourceType": "DEF"}
    value.update(overrides)
    return value


def _group_args(**overrides):
    params = {"name": GROUP_NAME, "application_id": APP_ID, "namespace_id": NAMESPACE_ID,
              "cluster_id": CLUSTER_ID, "description": "prod", "alias": "Orders", "state": "present"}
    params.update(overrides)
    return module_args(**params)


class FakeTsfClient(object):
    """In-memory TSF client backed by a mutable deployment-group list."""

    def __init__(self, groups=None):
        self.groups = [dict(g) for g in groups or []]
        self.calls = []
        self._next_id = 1

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeGroups(self, request):
        self._record("DescribeGroups", request)
        payload = [FakeResource(dict(g)) for g in self.groups]
        return SimpleNamespace(Result=SimpleNamespace(Content=payload), RequestId="req-fake")

    def _copy_fields(self, source, target, keys):
        for key in keys:
            if hasattr(source, key):
                target[key] = getattr(source, key)

    def CreateGroup(self, request):
        self._record("CreateGroup", request)
        value = {"GroupId": "group-%d" % self._next_id}
        self._next_id += 1
        self._copy_fields(request, value, _STORE_KEYS)
        self.groups.append(value)
        return SimpleNamespace(Result=value["GroupId"], RequestId="req-fake")

    def ModifyGroup(self, request):
        self._record("ModifyGroup", request)
        group_id = getattr(request, "GroupId", None)
        for group in self.groups:
            if group["GroupId"] == group_id:
                self._copy_fields(request, group, _MUTABLE_KEYS)
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def DeleteGroup(self, request):
        self._record("DeleteGroup", request)
        self.groups = [g for g in self.groups if g["GroupId"] != getattr(request, "GroupId", None)]
        return SimpleNamespace(Result=True, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TsfClient=object)))
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
# present flows
# ---------------------------------------------------------------------------


def test_present_creates_group(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _group_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deployment_group"]["GroupId"] == "group-1"
    assert result["deployment_group"]["GroupName"] == GROUP_NAME
    assert result["deployment_group"]["ApplicationId"] == APP_ID
    assert result["deployment_group"]["NamespaceId"] == NAMESPACE_ID
    assert result["deployment_group"]["ClusterId"] == CLUSTER_ID
    assert result["deployment_group"]["GroupResourceType"] == "DEF"
    assert "CreateGroup" in _names(fake)
    assert len(fake.groups) == 1


def test_present_no_drift_is_idempotent(monkeypatch):
    fake = FakeTsfClient(groups=[_group("group-7")])
    _make_module(monkeypatch, fake)
    _group_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["deployment_group"]["GroupId"] == "group-7"
    assert "CreateGroup" not in _names(fake)
    assert "ModifyGroup" not in _names(fake)


def test_present_description_drift_triggers_modify(monkeypatch):
    fake = FakeTsfClient(groups=[_group("group-7", GroupDesc="old", Alias="Orders")])
    _make_module(monkeypatch, fake)
    _group_args(description="new")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deployment_group"]["GroupDesc"] == "new"
    assert "ModifyGroup" in _names(fake)
    assert fake.groups[0]["GroupDesc"] == "new"


def test_present_alias_drift_triggers_modify(monkeypatch):
    fake = FakeTsfClient(groups=[_group("group-7", Alias="old-alias")])
    _make_module(monkeypatch, fake)
    _group_args(alias="new-alias")
    result = run(mod.run_module)
    assert result["changed"] is True
    request = _last_request(fake, "ModifyGroup")
    assert request.Alias == "new-alias"
    assert fake.groups[0]["Alias"] == "new-alias"


def test_present_immutable_scope_drift_is_rejected(monkeypatch):
    fake = FakeTsfClient(groups=[_group("group-7")])
    _make_module(monkeypatch, fake)
    _group_args(group_id="group-7", application_id="app-2")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed on an existing" in payload["msg"]
    assert "ApplicationId" in payload["immutable_changes"]
    assert "ModifyGroup" not in _names(fake)


def test_present_check_mode_is_dry_run_for_create(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _group_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deployment_group"]["GroupName"] == GROUP_NAME
    assert "GroupId" not in result["deployment_group"]
    assert "CreateGroup" not in _names(fake)
    assert fake.groups == []


def test_present_check_mode_is_dry_run_for_modify(monkeypatch):
    fake = FakeTsfClient(groups=[_group("group-7", GroupDesc="old")])
    _make_module(monkeypatch, fake)
    _group_args(_ansible_check_mode=True, description="new")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deployment_group"]["GroupDesc"] == "new"
    assert "ModifyGroup" not in _names(fake)
    assert fake.groups[0]["GroupDesc"] == "old"


# ---------------------------------------------------------------------------
# lookup semantics
# ---------------------------------------------------------------------------


def test_multiple_scoped_name_matches_fail(monkeypatch):
    fake = FakeTsfClient(groups=[_group("group-1", GroupDesc="a"), _group("group-2", GroupDesc="b")])
    _make_module(monkeypatch, fake)
    _group_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSF VM deployment groups matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_unregistered_is_idempotent(monkeypatch):
    fake = FakeTsfClient(groups=[_group("group-7", GroupName="other")])
    _make_module(monkeypatch, fake)
    _group_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["deployment_group"] is None
    assert "DeleteGroup" not in _names(fake)


def test_absent_deletes_group(monkeypatch):
    fake = FakeTsfClient(groups=[_group("group-7")])
    _make_module(monkeypatch, fake)
    _group_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deployment_group"] is None
    assert "DeleteGroup" in _names(fake)
    assert fake.groups == []


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfClient(groups=[_group("group-7")])
    _make_module(monkeypatch, fake)
    _group_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deployment_group"] is None
    assert "DeleteGroup" not in _names(fake)
    assert len(fake.groups) == 1


def test_rejected_delete_fails(monkeypatch):
    class RejectingClient(FakeTsfClient):
        def DeleteGroup(self, request):
            self._record("DeleteGroup", request)
            return SimpleNamespace(Result=False, RequestId="req-err")

    fake = RejectingClient(groups=[_group("group-7")])
    _make_module(monkeypatch, fake)
    _group_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rejected the TSF VM deployment group deletion" in exc.value.args[0]["msg"]


def test_rejected_update_fails(monkeypatch):
    class RejectingClient(FakeTsfClient):
        def ModifyGroup(self, request):
            self._record("ModifyGroup", request)
            return SimpleNamespace(Result=False, RequestId="req-err")

    fake = RejectingClient(groups=[_group("group-7", GroupDesc="old")])
    _make_module(monkeypatch, fake)
    _group_args(description="new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rejected the TSF VM deployment group update" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeGroups(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _group_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy pure-helper assertions (folded from the shallow test file)
# ---------------------------------------------------------------------------


def test_legacy_desired_maps_scope_and_mutable_metadata():
    params = {"name": "orders", "application_id": "app-1", "namespace_id": "ns-1",
              "cluster_id": "cluster-1", "description": "prod", "alias": None, "resource_type": "DEF"}
    assert desired(params) == {"GroupName": "orders", "ApplicationId": "app-1",
                               "NamespaceId": "ns-1", "ClusterId": "cluster-1",
                               "GroupDesc": "prod", "GroupResourceType": "DEF"}


def test_legacy_comparison_ignores_runtime_and_package_state():
    target = {"GroupName": "orders", "GroupDesc": "prod"}
    current = dict(target, GroupStatus="Running", PackageVersion="1.2.3", InstanceCount=4)
    assert comparable(current, target) == target
