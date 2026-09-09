"""Unit tests for the tcm_tracing write module (run_module flows).

``run_module()`` is driven end to end against an in-memory fake TCM client
whose ``ModifyTracingConfig`` operation mutates a per-mesh tracing store, so
the post-write ``DescribeMesh`` refetch used by the waiter converges
immediately.

Scenario matrix:

* idempotent no-op when the live tracing already converges (extra server
  fields tolerated), including a disabled mesh that ignores stale Zipkin
* creation when the mesh has no tracing yet (check mode and real create)
* drift updates (sampling change, destination added, disable an enabled
  mesh)
* argument validation before any SDK call (sampling out of range, apm and
  zipkin mutually exclusive)
* missing mesh and blanket ``sdk_error_payload`` failure paths
* waiter timeout surfaces as a module failure when the write never converges
* legacy helper regression tests (folded from test_tcm_tracing.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tcm_tracing as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

MESH_ID = "mesh-abcdefgh"
ZIPKIN = {"Address": "http://zipkin.collector:9411/api/v2/spans"}


def _base(**overrides):
    params = {"mesh_id": MESH_ID, "enabled": True, "sampling": 1.0}
    params.update(overrides)
    return module_args(**params)


class FakeTcmClient(object):
    """In-memory TCM client holding the per-mesh tracing configuration."""

    def __init__(self, tracing=None, mesh_exists=True, stubborn=False):
        self.tracing = copy.deepcopy(tracing) if tracing is not None else None
        self.mesh_exists = mesh_exists
        self.stubborn = stubborn
        self.calls = []
        self.last_request = None

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _mesh_resource(self):
        if self.tracing is None:
            return FakeResource({"Config": {}})
        return FakeResource({"Config": {"Tracing": self.tracing}})

    def DescribeMesh(self, request):
        self._record("DescribeMesh", request)
        assert request.MeshId == MESH_ID
        if not self.mesh_exists:
            return SimpleNamespace(Mesh=None, RequestId="req-fake")
        return SimpleNamespace(Mesh=self._mesh_resource(), RequestId="req-fake")

    def _as_dict(self, value):
        if value is None:
            return None
        return dict(value.__dict__) if hasattr(value, "__dict__") else dict(value)

    def ModifyTracingConfig(self, request):
        self._record("ModifyTracingConfig", request)
        self.last_request = request
        if self.stubborn:
            # Simulate a server that silently applies a different sampling.
            self.tracing = {"Enable": request.Enable, "Sampling": 0.25, "APM": None, "Zipkin": None}
        else:
            self.tracing = {
                "Enable": request.Enable,
                "Sampling": request.Sampling,
                "APM": self._as_dict(request.APM),
                "Zipkin": self._as_dict(request.Zipkin),
            }
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
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_converged_tracing_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmClient(tracing={"Enable": True, "Sampling": 1.0}))
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["tracing"]["Enable"] is True
    assert result["tracing"]["Sampling"] == 1.0
    assert _names(fake) == ["DescribeMesh"]


def test_converged_tracing_allows_extra_server_fields(monkeypatch):
    fake = _make_module(
        monkeypatch,
        FakeTcmClient(tracing={"Enable": True, "Sampling": 1.0, "APM": {"Enable": True, "InstanceId": "apm-1"}}),
    )
    _base(sampling=1.0)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["tracing"]["APM"]["InstanceId"] == "apm-1"
    assert _names(fake) == ["DescribeMesh"]


def test_disabled_mesh_ignores_stale_zipkin_and_is_idempotent(monkeypatch):
    fake = _make_module(
        monkeypatch,
        FakeTcmClient(tracing={"Enable": False, "Sampling": 0.0, "Zipkin": dict(ZIPKIN, Address="old")}),
    )
    _base(enabled=False, sampling=0.0)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["tracing"]["Zipkin"]["Address"] == "old"
    assert _names(fake) == ["DescribeMesh"]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_tracing_when_absent(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmClient())
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.tracing["Enable"] is True
    assert fake.tracing["Sampling"] == 1.0
    request = _find_call(fake, "ModifyTracingConfig")
    assert request.MeshId == MESH_ID
    assert request.Enable is True
    assert request.Sampling == 1.0
    assert _names(fake) == ["DescribeMesh", "ModifyTracingConfig", "DescribeMesh"]


def test_create_tracing_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmClient())
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["tracing"] == {"Enable": True, "Sampling": 1.0}
    assert "diff" in result
    assert fake.tracing is None
    assert _names(fake) == ["DescribeMesh"]


# ---------------------------------------------------------------------------
# drift update flows
# ---------------------------------------------------------------------------


def test_update_when_sampling_drifts(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmClient(tracing={"Enable": True, "Sampling": 0.5}))
    _base(sampling=1.0)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.tracing["Enable"] is True
    assert fake.tracing["Sampling"] == 1.0
    assert _names(fake) == ["DescribeMesh", "ModifyTracingConfig", "DescribeMesh"]


def test_update_adds_zipkin_destination(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmClient(tracing={"Enable": True, "Sampling": 1.0}))
    _base(zipkin=ZIPKIN)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.tracing["Zipkin"] == ZIPKIN
    request = _find_call(fake, "ModifyTracingConfig")
    assert request.Zipkin is not None
    assert request.Zipkin.Address == ZIPKIN["Address"]
    assert _names(fake) == ["DescribeMesh", "ModifyTracingConfig", "DescribeMesh"]


def test_update_disables_tracing(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmClient(tracing={"Enable": True, "Sampling": 1.0}))
    _base(enabled=False, sampling=0.0)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.tracing["Enable"] is False
    assert fake.tracing["Sampling"] == 0.0
    assert _names(fake) == ["DescribeMesh", "ModifyTracingConfig", "DescribeMesh"]


# ---------------------------------------------------------------------------
# argument validation and failure paths
# ---------------------------------------------------------------------------


def test_sampling_out_of_range_fails_before_sdk(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmClient())
    _base(sampling=200)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "sampling must be between 0 and 100" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_negative_sampling_fails_before_sdk(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmClient())
    _base(sampling=-0.5)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "sampling must be between 0 and 100" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_apm_and_zipkin_are_mutually_exclusive(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmClient())
    _base(apm={"Enable": True}, zipkin=ZIPKIN)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "mutually exclusive" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_missing_mesh_fails(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmClient(mesh_exists=False))
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

    fake = _make_module(monkeypatch, ExplodingClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "tcm endpoint unreachable" in payload["error"]


def test_waiter_times_out_when_update_does_not_converge(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmClient(tracing={"Enable": True, "Sampling": 0.5}, stubborn=True))
    _base(sampling=1.0, waiter_timeout=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Timed out waiting for TCM tracing convergence" in payload["msg"]
    assert payload["expected"] == {"Enable": True, "Sampling": 1.0}
    assert fake.tracing["Sampling"] == 0.25


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tcm_tracing.py)
# ---------------------------------------------------------------------------


def test_tracing_update_request_maps_sampling_and_destination():
    p = {"mesh_id": "mesh-1", "enabled": True, "sampling": 10.0, "apm": {"Enable": True}, "zipkin": None}
    value = mod.update_request(FakeModels(), p)
    assert value.MeshId == "mesh-1"
    assert value.Enable is True
    assert value.Sampling == 10.0
    assert "Enable" in value.APM.__dict__
    assert value.Zipkin is None
    assert "APM" in mod.desired(p)
    assert "Zipkin" not in mod.desired(p)


def test_tracing_convergence_allows_server_fields_and_ignores_destinations_when_disabled():
    assert mod.converged(
        {"Enable": True, "Sampling": 10, "APM": {"Enable": True, "InstanceId": "apm-1"}},
        {"Enable": True, "Sampling": 10.0, "APM": {"Enable": True}},
    )
    assert mod.converged(
        {"Enable": False, "Sampling": 0, "Zipkin": {"Address": "old"}},
        {"Enable": False, "Sampling": 0.0},
    )
    assert not mod.converged({"Enable": True, "Sampling": 0.5}, {"Enable": True, "Sampling": 1.0})
