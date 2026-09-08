"""Unit tests for the tsf_namespace write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TSF client
whose write operations mutate the namespace store, so the module's
post-write ``find`` refetch converges immediately.

Scenario matrix:

* absent on a missing namespace (idempotent no-op), rejected-deletion guard
  and the real delete path
* cluster_id required for a non-global namespace, no-drift idempotency,
  immutable placement drift failure
* creation (cluster namespace and global namespace) and description/ha
  updates, with a check-mode dry run
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tsf_namespace as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

NAMESPACE = {
    "NamespaceId": "namespace-1",
    "NamespaceName": "production",
    "ClusterId": "cluster-xxx",
    "NamespaceDesc": "production services",
    "NamespaceResourceType": "DEF",
    "NamespaceType": "DEF",
    "IsHaEnable": "1",
}


def _namespace(**overrides):
    item = copy.deepcopy(NAMESPACE)
    item.update(overrides)
    return item


class FakeTsfNamespaceClient(object):
    """In-memory TSF client mutating a namespace store."""

    def __init__(self, namespaces=None):
        self.namespaces = [copy.deepcopy(t) for t in (namespaces or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _matches(self, request):
        namespace_id = getattr(request, "NamespaceId", None)
        if namespace_id:
            return [item for item in self.namespaces if item.get("NamespaceId") == namespace_id]
        name = getattr(request, "NamespaceName", None)
        cluster = getattr(request, "ClusterId", None)
        return [
            item
            for item in self.namespaces
            if item.get("NamespaceName") == name and (not cluster or item.get("ClusterId") == cluster)
        ]

    def DescribeSimpleNamespaces(self, request):
        self._record("DescribeSimpleNamespaces", request)
        return SimpleNamespace(
            Result=SimpleNamespace(Content=[FakeResource(item) for item in self._matches(request)], TotalCount=len(self._matches(request)))
        )

    def DeleteNamespace(self, request):
        self._record("DeleteNamespace", request)
        namespace_id = getattr(request, "NamespaceId", None)
        self.namespaces = [item for item in self.namespaces if item.get("NamespaceId") != namespace_id]
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def CreateNamespace(self, request):
        self._record("CreateNamespace", request)
        self._next += 1
        item = {"NamespaceId": "namespace-new-%03d" % self._next}
        for key, value in vars(request).items():
            item[key] = copy.deepcopy(value)
        self.namespaces.append(item)
        return SimpleNamespace(Result=item["NamespaceId"], RequestId="req-fake")

    def ModifyNamespace(self, request):
        self._record("ModifyNamespace", request)
        namespace = next((item for item in self.namespaces if item.get("NamespaceId") == getattr(request, "NamespaceId", None)), None)
        if namespace is not None:
            for key in ("NamespaceName", "NamespaceDesc", "IsHaEnable"):
                if getattr(request, key, None) is not None:
                    namespace[key] = getattr(request, key)
        return SimpleNamespace(Result=True, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TsfClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _namespace_args(**overrides):
    params = {
        "name": "production",
        "cluster_id": "cluster-xxx",
        "description": "production services",
        "resource_type": "DEF",
        "high_availability": True,
    }
    params.update(overrides)
    return module_args(**params)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_namespace_is_idempotent(monkeypatch):
    fake = FakeTsfNamespaceClient(namespaces=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["namespace"] is None


def test_absent_deletes_namespace(monkeypatch):
    fake = FakeTsfNamespaceClient(namespaces=[_namespace()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="production", cluster_id="cluster-xxx")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.namespaces == []
    assert "DeleteNamespace" in [c for c, unused in fake.calls]


def test_absent_deletion_rejected(monkeypatch):
    class RejectingClient(FakeTsfNamespaceClient):
        def DeleteNamespace(self, request):
            self._record("DeleteNamespace", request)
            return SimpleNamespace(Result=False, RequestId="req-fake")

    fake = RejectingClient(namespaces=[_namespace()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="production", cluster_id="cluster-xxx")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rejected the TSF namespace deletion" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_cluster_id(monkeypatch):
    fake = FakeTsfNamespaceClient(namespaces=[])
    _make_module(monkeypatch, fake)
    module_args(name="production")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "cluster_id is required when creating a non-global" in exc.value.args[0]["msg"]


def test_create_cluster_namespace(monkeypatch):
    fake = FakeTsfNamespaceClient(namespaces=[])
    _make_module(monkeypatch, fake)
    _namespace_args(create_k8s_namespace=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"]["NamespaceName"] == "production"
    assert result["namespace"]["NamespaceType"] == "DEF"
    assert len(fake.namespaces) == 1
    assert "CreateNamespace" in [c for c, unused in fake.calls]


def test_create_global_namespace_without_cluster(monkeypatch):
    fake = FakeTsfNamespaceClient(namespaces=[])
    _make_module(monkeypatch, fake)
    module_args(name="global-ns", namespace_type="GLOBAL", description="global")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"]["NamespaceType"] == "GLOBAL"
    assert fake.namespaces[0].get("ClusterId") is None


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfNamespaceClient(namespaces=[])
    _make_module(monkeypatch, fake)
    _namespace_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"]["NamespaceName"] == "production"
    assert fake.namespaces == []
    assert "CreateNamespace" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-namespace flows
# ---------------------------------------------------------------------------


def test_existing_namespace_no_drift_is_idempotent(monkeypatch):
    fake = FakeTsfNamespaceClient(namespaces=[_namespace()])
    _make_module(monkeypatch, fake)
    _namespace_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["namespace"]["NamespaceId"] == "namespace-1"
    assert "ModifyNamespace" not in [c for c, unused in fake.calls]


def test_immutable_placement_drift_fails(monkeypatch):
    fake = FakeTsfNamespaceClient(namespaces=[_namespace()])
    _make_module(monkeypatch, fake)
    _namespace_args(namespace_type="GLOBAL")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert "NamespaceType" in payload["immutable_changes"]


def test_update_namespace_description(monkeypatch):
    fake = FakeTsfNamespaceClient(namespaces=[_namespace()])
    _make_module(monkeypatch, fake)
    _namespace_args(description="re-titled production", high_availability=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["namespace"]["NamespaceDesc"] == "re-titled production"
    assert result["namespace"]["IsHaEnable"] == "0"
    assert "ModifyNamespace" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeSimpleNamespaces(self, request):
            raise Boom("namespace lookup exploded")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _namespace_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "namespace lookup exploded" in payload["error"]
