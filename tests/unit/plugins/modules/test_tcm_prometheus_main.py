"""Unit tests for the tcm_prometheus write module (run_module flows).

``run_module()`` is driven end to end against an in-memory fake TCM client
whose link/unlink operations mutate a per-mesh Prometheus store, so the
post-write ``DescribeMesh`` refetch used by the waiter converges immediately.

Scenario matrix:

* absent with no linked Prometheus (idempotent) / check-mode unlink / real
  unlink with post-unlink waiter refetch
* present with no linked Prometheus (check mode and real link)
* idempotent no-op when the live config already converges (secrets redacted)
* ``rotate_credentials`` forces a relink even when converged
* missing mesh and missing ``config`` failure paths before any mutation
* waiter timeout surfaces as a module failure (unlink never converges)
* the blanket ``sdk_error_payload`` failure path
* legacy helper regression tests (folded from test_tcm_prometheus.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tcm_prometheus as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

MESH_ID = "mesh-abcdefgh"
PROM_CONFIG = {
    "Region": "ap-guangzhou",
    "InstanceId": "prom-abcdefgh",
    "CustomProm": {"Username": "monitor", "Password": "s3cret-value"},
}


def _base(**overrides):
    params = {"mesh_id": MESH_ID, "state": "present", "config": PROM_CONFIG}
    params.update(overrides)
    return module_args(**params)


class FakeTcmPrometheusClient(object):
    """In-memory TCM client holding the linked Prometheus config per mesh."""

    def __init__(self, prom=None, mesh_exists=True, unlink_noop=False):
        self.prom = copy.deepcopy(prom) if prom is not None else None
        self.mesh_exists = mesh_exists
        self.unlink_noop = unlink_noop
        self.calls = []
        self.last_request = None

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeMesh(self, request):
        self._record("DescribeMesh", request)
        assert request.MeshId == MESH_ID
        if not self.mesh_exists:
            return SimpleNamespace(Mesh=None, RequestId="req-fake")
        return SimpleNamespace(Mesh=FakeResource({"Config": {"Prometheus": self.prom}}), RequestId="req-fake")

    def LinkPrometheus(self, request):
        self._record("LinkPrometheus", request)
        self.last_request = request
        self.prom = copy.deepcopy(request.Prometheus.__dict__)
        return SimpleNamespace(RequestId="req-fake")

    def UnlinkPrometheus(self, request):
        self._record("UnlinkPrometheus", request)
        if not self.unlink_noop:
            self.prom = None
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TcmClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _find_call(fake, operation):
    return next(request for name, request in fake.calls if name == operation)


def _names(fake):
    return [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_without_prometheus_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmPrometheusClient())
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["prometheus"] is None
    assert _names(fake) == ["DescribeMesh"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmPrometheusClient(prom=PROM_CONFIG))
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["prometheus"] is None
    assert fake.prom == PROM_CONFIG
    assert "UnlinkPrometheus" not in _names(fake)


def test_absent_unlinks_prometheus(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmPrometheusClient(prom=PROM_CONFIG))
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["prometheus"] is None
    assert fake.prom is None
    request = _find_call(fake, "UnlinkPrometheus")
    assert request.MeshID == MESH_ID
    assert _names(fake) == ["DescribeMesh", "UnlinkPrometheus", "DescribeMesh"]


def test_absent_waiter_times_out_when_unlink_does_not_converge(monkeypatch):
    _make_module(monkeypatch, FakeTcmPrometheusClient(prom=PROM_CONFIG, unlink_noop=True))
    _base(state="absent", waiter_timeout=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Timed out waiting for TCM Prometheus" in payload["msg"]
    assert payload["expected"] is None


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_links_prometheus(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmPrometheusClient())
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["prometheus"]["InstanceId"] == "prom-abcdefgh"
    assert "Password" not in result["prometheus"]["CustomProm"]
    assert len(fake.prom["CustomProm"]) == 2  # secrets persisted server-side
    request = _find_call(fake, "LinkPrometheus")
    assert request.MeshID == MESH_ID
    assert request.Prometheus.InstanceId == "prom-abcdefgh"
    ops = [name for name, unused in fake.calls]
    assert ops == ["DescribeMesh", "LinkPrometheus", "DescribeMesh"]


def test_present_link_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmPrometheusClient())
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["prometheus"] == mod.without_secrets(PROM_CONFIG)
    assert fake.prom is None
    assert "LinkPrometheus" not in _names(fake)


def test_present_converged_config_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmPrometheusClient(prom=dict(PROM_CONFIG, DisplayName="managed")))
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["prometheus"]["InstanceId"] == "prom-abcdefgh"
    assert "Password" not in result["prometheus"]["CustomProm"]
    assert _names(fake) == ["DescribeMesh"]


def test_rotate_credentials_forces_relink(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmPrometheusClient(prom=PROM_CONFIG))
    _base(rotate_credentials=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "LinkPrometheus" in _names(fake)


# ---------------------------------------------------------------------------
# argument validation and failure paths
# ---------------------------------------------------------------------------


def test_present_requires_config(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmPrometheusClient())
    module_args(mesh_id=MESH_ID, state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "config" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_missing_mesh_fails(monkeypatch):
    _make_module(monkeypatch, FakeTcmPrometheusClient(mesh_exists=False))
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "mesh was not found" in payload["msg"]
    assert payload["mesh_id"] == MESH_ID


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeMesh(self, request):
            raise Boom("tcm endpoint unreachable")

    _make_module(monkeypatch, ExplodingClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "tcm endpoint unreachable" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tcm_prometheus.py)
# ---------------------------------------------------------------------------


def test_prometheus_request_uses_sdk_mesh_id_spelling():
    value = mod.link_request(FakeModels(), "mesh-1", {"InstanceId": "prom-1"})
    assert value.MeshID == "mesh-1"
    assert value.Prometheus.InstanceId == "prom-1"


def test_prometheus_comparison_redacts_password_and_allows_returned_fields():
    current = {"InstanceId": "prom-1", "CustomProm": {"Username": "u", "Password": None}, "DisplayName": "managed"}
    desired = {"InstanceId": "prom-1", "CustomProm": {"Username": "u", "Password": "secret"}}
    assert mod.converged(current, desired)
    assert "Password" not in mod.without_secrets(desired)["CustomProm"]
