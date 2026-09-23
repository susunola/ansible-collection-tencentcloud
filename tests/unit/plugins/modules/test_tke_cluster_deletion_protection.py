"""Unit tests for the tke_cluster_deletion_protection write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TKE client whose
Enable/Disable operations mutate the stored ``DeletionProtection`` flag, so the
module's post-write ``describe_state`` refetch observes the new state
immediately.

Scenario matrix:

* enable on an unprotected cluster (real Enable + converged refetch)
* disable on a protected cluster (real Disable + converged refetch)
* idempotent no-op when already enabled (state=present, flag already True)
* idempotent no-op when already disabled (state=absent, flag already False)
* check-mode dry run for enable (no Enable call, reports desired state)
* check-mode dry run for disable (no Disable call, reports desired state)
* cluster-not-found failure path (fail_json with a clear message)
* SDK failure maps to the standard error envelope via fail_sdk_error
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tke_cluster_deletion_protection as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _cluster(cluster_id, deletion_protection):
    return FakeResource({"ClusterId": cluster_id, "DeletionProtection": deletion_protection})


class FakeTkeClient(object):
    """In-memory TKE client mutating a per-cluster DeletionProtection flag."""

    def __init__(self, clusters=None):
        # clusters: list of (cluster_id, deletion_protection) tuples
        self.flags = dict(clusters or [])
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeClusters(self, request):
        self._record("DescribeClusters", request)
        cluster_id = (request.ClusterIds or [None])[0]
        if cluster_id in self.flags:
            response = SimpleNamespace(
                Clusters=[_cluster(cluster_id, self.flags[cluster_id])],
                RequestId="req-fake",
            )
        else:
            response = SimpleNamespace(Clusters=[], RequestId="req-fake")
        return response

    def EnableClusterDeletionProtection(self, request):
        self._record("EnableClusterDeletionProtection", request)
        self.flags[request.ClusterId] = True
        return SimpleNamespace(RequestId="req-fake")

    def DisableClusterDeletionProtection(self, request):
        self._record("DisableClusterDeletionProtection", request)
        self.flags[request.ClusterId] = False
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_tke", lambda: (models or FakeModels(), SimpleNamespace(TkeClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# enable / disable flows
# ---------------------------------------------------------------------------


def test_enable_on_unprotected_cluster(monkeypatch):
    fake = FakeTkeClient(clusters=[("cls-abc123", False)])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster_id"] == "cls-abc123"
    assert result["deletion_protection"] is True
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeClusters"
    assert "EnableClusterDeletionProtection" in ops
    assert "DisableClusterDeletionProtection" not in ops
    assert fake.flags["cls-abc123"] is True


def test_disable_on_protected_cluster(monkeypatch):
    fake = FakeTkeClient(clusters=[("cls-abc123", True)])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["cluster_id"] == "cls-abc123"
    assert result["deletion_protection"] is False
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeClusters"
    assert "DisableClusterDeletionProtection" in ops
    assert "EnableClusterDeletionProtection" not in ops
    assert fake.flags["cls-abc123"] is False


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_already_enabled_is_idempotent(monkeypatch):
    fake = FakeTkeClient(clusters=[("cls-abc123", True)])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["deletion_protection"] is True
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribeClusters"]
    assert "EnableClusterDeletionProtection" not in ops


def test_already_disabled_is_idempotent(monkeypatch):
    fake = FakeTkeClient(clusters=[("cls-abc123", False)])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["deletion_protection"] is False
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribeClusters"]
    assert "DisableClusterDeletionProtection" not in ops


# ---------------------------------------------------------------------------
# check-mode dry runs
# ---------------------------------------------------------------------------


def test_enable_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient(clusters=[("cls-abc123", False)])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", state="present", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deletion_protection"] is True
    assert "EnableClusterDeletionProtection" not in [c for c, unused in fake.calls]
    assert fake.flags["cls-abc123"] is False


def test_disable_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient(clusters=[("cls-abc123", True)])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deletion_protection"] is False
    assert "DisableClusterDeletionProtection" not in [c for c, unused in fake.calls]
    assert fake.flags["cls-abc123"] is True


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_cluster_not_found_fails(monkeypatch):
    fake = FakeTkeClient(clusters=[])
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-ghost", state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "TKE cluster cls-ghost not found"
    assert payload["cluster_id"] == "cls-ghost"
    assert "EnableClusterDeletionProtection" not in [c for c, unused in fake.calls]


def test_sdk_failure_maps_to_error_envelope(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeClusters(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    module_args(cluster_id="cls-abc123", state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud TKE deletion protection request failed"
    assert "connection dropped" in payload["error"]
