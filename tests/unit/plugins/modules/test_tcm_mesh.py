"""Unit tests for the tcm_mesh write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/tcm_mesh.py`` with an in-memory fake TCM client whose write
operations mutate the mesh store, so the module's post-write ``find``
refetch converges immediately. Meshes are matched by ``mesh_id``
(DescribeMesh) or by ``DisplayName`` across the paged DescribeMeshList;
MeshVersion / Type are immutable after creation and drift on them fails with
a replacement-required error. The SDK Config payload is merged with a
contains() partial-match so an already-satisfied config is left untouched.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tcm_mesh as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

MESH = {
    "MeshId": "mesh-1",
    "DisplayName": "production-mesh",
    "Version": "1.20.5",
    "Type": "HOSTED",
    "Config": {"Istio": {"DisablePolicyChecks": False}},
}


def _mesh(**overrides):
    """API-shaped mesh dict isolated from the shared constant."""
    item = copy.deepcopy(MESH)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec."""
    params = {
        "state": "present",
        "mesh_id": None,
        "name": "production-mesh",
        "mesh_version": None,
        "mesh_type": None,
        "config": None,
        "clusters": None,
        "tags": None,
        "delete_cls": False,
        "delete_tmp": False,
        "delete_apm": False,
        "delete_grafana": False,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter (None dropped)."""
    args = dict(_params())
    args.update(extra)
    return module_args(**{k: v for k, v in args.items() if v is not None})


class _JsonModel(object):
    """SDK model whose config sub-objects round-trip through from_json_string."""

    def from_json_string(self, payload):
        for key, value in json.loads(payload).items():
            setattr(self, key, value)
        return self


class FakeTcmModels(FakeModels):
    """FakeModels whose config classes implement from_json_string."""

    def __getattr__(self, name):
        if name in ("MeshConfig", "Cluster"):
            return _JsonModel
        return super(FakeTcmModels, self).__getattr__(name)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or _params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeTcmClient(object):
    """In-memory TcmClient stand-in.

    Stores API-shaped mesh dicts. DescribeMesh resolves by MeshId and raises
    a not-found error for unknown ids (mirroring the SDK); DescribeMeshList
    pages over the store honouring Offset/Limit; write operations mutate the
    store so post-write refetches converge.
    """

    def __init__(self, meshes=None):
        self.meshes = [copy.deepcopy(m) for m in (meshes or [])]
        self.calls = []
        self._next_id = 1000

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _new_id(self):
        self._next_id += 1
        return "mesh-%d" % self._next_id

    @staticmethod
    def _as_dict(value):
        return dict(vars(value)) if value is not None else None

    def DescribeMesh(self, request):
        self._record("DescribeMesh", request)
        for stored in self.meshes:
            if stored.get("MeshId") == request.MeshId:
                return SimpleNamespace(Mesh=FakeResource(dict(stored)), RequestId="req-fake")
        raise RuntimeError("mesh not found")

    def DescribeMeshList(self, request):
        self._record("DescribeMeshList", request)
        page = self.meshes[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            MeshList=[FakeResource(dict(m)) for m in page],
            Total=len(self.meshes),
            RequestId="req-fake",
        )

    def CreateMesh(self, request):
        self._record("CreateMesh", request)
        mesh_id = self._new_id()
        self.meshes.append(
            {
                "MeshId": mesh_id,
                "DisplayName": request.DisplayName,
                "Version": request.MeshVersion,
                "Type": request.Type,
                "Config": self._as_dict(request.Config),
            }
        )
        return SimpleNamespace(MeshId=mesh_id, RequestId="req-fake")

    def ModifyMesh(self, request):
        self._record("ModifyMesh", request)
        for stored in self.meshes:
            if stored.get("MeshId") != request.MeshId:
                continue
            stored["DisplayName"] = request.DisplayName
            stored["Config"] = self._as_dict(request.Config)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteMesh(self, request):
        self._record("DeleteMesh", request)
        self.meshes = [m for m in self.meshes if m.get("MeshId") != request.MeshId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeTcmModels(), SimpleNamespace(TcmClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# request-builder / model helper tests
# ---------------------------------------------------------------------------


def test_model_returns_none_for_none_value():
    assert mod._model(FakeTcmModels().MeshConfig, None) is None


def test_model_round_trips_payload():
    item = mod._model(FakeTcmModels().MeshConfig, {"Istio": {"DisablePolicyChecks": True}})
    assert item.Istio == {"DisablePolicyChecks": True}


def test_tags_builder_sorted():
    items = mod._tags(FakeTcmModels(), {"z": "2", "a": "1"})
    assert [(x.Key, x.Value) for x in items] == [("a", "1"), ("z", "2")]


def test_tags_builder_empty_and_none():
    assert mod._tags(FakeTcmModels(), None) == []
    assert mod._tags(FakeTcmModels(), {}) == []


def test_list_request_pagination_fields():
    assert mod.list_request(FakeTcmModels(), 0).Limit == 100
    assert mod.list_request(FakeTcmModels(), 100).Offset == 100


def test_describe_request_fields():
    request = mod.describe_request(FakeTcmModels(), "mesh-9")
    assert request.MeshId == "mesh-9"


def test_create_request_fields():
    request = mod.create_request(
        FakeTcmModels(),
        _params(name="mesh-x", mesh_version="1.22.0", mesh_type="HOSTED", config={"Istio": {"DisablePolicyChecks": True}}),
    )
    assert request.DisplayName == "mesh-x"
    assert request.MeshVersion == "1.22.0"
    assert request.Type == "HOSTED"
    assert request.Config.Istio == {"DisablePolicyChecks": True}
    assert request.ClusterList == []
    assert request.TagList == []


def test_create_request_with_clusters_and_tags():
    params = _params(clusters=[{"ClusterId": "cls-1"}, {"ClusterId": "cls-2"}], tags={"env": "prod"})
    request = mod.create_request(FakeTcmModels(), params)
    assert [c.ClusterId for c in request.ClusterList] == ["cls-1", "cls-2"]
    assert [(t.Key, t.Value) for t in request.TagList] == [("env", "prod")]


def test_update_request_fields():
    request = mod.update_request(FakeTcmModels(), "mesh-1", {"DisplayName": "renamed", "Config": {"Istio": {"DisablePolicyChecks": False}}})
    assert request.MeshId == "mesh-1"
    assert request.DisplayName == "renamed"
    assert request.Config.Istio == {"DisablePolicyChecks": False}


def test_delete_request_fields():
    request = mod.delete_request(
        FakeTcmModels(),
        _params(delete_cls=True, delete_tmp=True, delete_apm=True, delete_grafana=True),
        "mesh-1",
    )
    assert request.MeshId == "mesh-1"
    assert request.NeedDeleteCLS is True
    assert request.NeedDeleteTMP is True
    assert request.NeedDeleteAPM is True
    assert request.NeedDeleteGrafana is True


def test_comparable_maps_version_field():
    value = mod.comparable(_mesh())
    assert value["DisplayName"] == "production-mesh"
    assert value["MeshVersion"] == "1.20.5"
    assert value["Type"] == "HOSTED"
    assert value["Config"] == {"Istio": {"DisablePolicyChecks": False}}


def test_contains_scalar_and_dict_partial():
    assert mod.contains({"a": {"b": 1}}, {"a": {"b": 1}}) is True
    assert mod.contains({"a": {"b": 1, "c": 2}}, {"a": {"b": 1}}) is True  # subset ok
    assert mod.contains({"a": {"b": 1}}, {"a": {"c": 2}}) is False
    assert mod.contains({"a": 1}, {"a": 2}) is False
    assert mod.contains("same", "same") is True
    assert mod.contains(None, {"a": 1}) is False


def test_contains_list_matches_positionally():
    assert mod.contains([{"a": 1}, {"b": 2}], [{"a": 1}, {"b": 2}]) is True
    assert mod.contains([{"a": 1, "c": 3}], [{"a": 1}]) is True
    assert mod.contains([{"a": 1}, {"b": 2}], [{"b": 2}, {"a": 1}]) is False


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_by_mesh_id(monkeypatch):
    fake = FakeTcmClient([_mesh(), _mesh(MeshId="mesh-2", DisplayName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(mesh_id="mesh-2"))
    value = mod.find(module, fake, FakeTcmModels(), module.params)
    assert value["MeshId"] == "mesh-2"


def test_find_by_name(monkeypatch):
    fake = FakeTcmClient([_mesh(DisplayName="other"), _mesh()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="production-mesh"))
    value = mod.find(module, fake, FakeTcmModels(), module.params)
    assert value["MeshId"] == "mesh-1"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeTcmClient([_mesh()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeTcmModels(), module.params) is None


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeTcmClient([_mesh(), _mesh(MeshId="mesh-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="production-mesh"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeTcmModels(), module.params)
    assert "Multiple TCM meshes matched" in exc.value.args[0]["msg"]


def test_find_by_name_paginates_past_100(monkeypatch):
    meshes = [_mesh(MeshId="bulk-%04d" % i, DisplayName="bulk-%04d" % i) for i in range(101)]
    meshes.append(_mesh())
    fake = FakeTcmClient(meshes)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="production-mesh"))
    value = mod.find(module, fake, FakeTcmModels(), module.params)
    assert value["MeshId"] == "mesh-1"
    list_calls = [c for c in fake.calls if c[0] == "DescribeMeshList"]
    assert len(list_calls) == 2  # pages of 100
    assert [c[1].Offset for c in list_calls] == [0, 100]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced():
    module_args(state="present")  # neither mesh_id nor name
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_creates_mesh(monkeypatch):
    fake = FakeTcmClient()
    _make_module(monkeypatch, fake)
    _run_args(name="mesh-x", mesh_version="1.22.0", mesh_type="HOSTED")
    result = run(mod.run_module)
    assert result["changed"] is True
    mesh = result["mesh"]
    assert mesh["MeshId"] == "mesh-1001"
    assert mesh["DisplayName"] == "mesh-x"
    assert mesh["Version"] == "1.22.0"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeMeshList") == 1  # initial find by name
    assert names.count("DescribeMesh") == 1  # post-create refetch by id
    assert names.count("CreateMesh") == 1
    create = [c for c in fake.calls if c[0] == "CreateMesh"][0][1]
    assert create.MeshVersion == "1.22.0"


def test_present_requires_creation_params(monkeypatch):
    fake = FakeTcmClient()
    _make_module(monkeypatch, fake)
    _run_args(name="ghost-mesh", mesh_version=None, mesh_type=None)  # no match
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required for a TCM mesh" in payload["msg"]
    assert set(payload["missing"]) == {"mesh_version", "mesh_type"}


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeTcmClient([_mesh()])
    _make_module(monkeypatch, fake)
    _run_args(name="production-mesh", mesh_version="1.20.5", mesh_type="HOSTED")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["mesh"]["MeshId"] == "mesh-1"
    names = [c[0] for c in fake.calls]
    assert "ModifyMesh" not in names
    assert "CreateMesh" not in names


def test_present_rename_triggers_update(monkeypatch):
    fake = FakeTcmClient([_mesh()])
    _make_module(monkeypatch, fake)
    _run_args(mesh_id="mesh-1", name="renamed-mesh")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["mesh"]["DisplayName"] == "renamed-mesh"
    modify = [c for c in fake.calls if c[0] == "ModifyMesh"][0][1]
    assert modify.MeshId == "mesh-1"
    assert modify.DisplayName == "renamed-mesh"


def test_present_config_replaced_when_not_contained(monkeypatch):
    fake = FakeTcmClient([_mesh()])
    _make_module(monkeypatch, fake)
    _run_args(mesh_id="mesh-1", config={"Telemetry": {"Enable": True}})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["mesh"]["Config"] == {"Telemetry": {"Enable": True}}
    modify = [c for c in fake.calls if c[0] == "ModifyMesh"][0][1]
    assert modify.Config.Telemetry == {"Enable": True}


def test_present_config_already_contained_is_noop(monkeypatch):
    # desired config is a subset of the remote one -> left untouched.
    fake = FakeTcmClient([_mesh(Config={"Istio": {"DisablePolicyChecks": False, "Extra": 1}})])
    _make_module(monkeypatch, fake)
    _run_args(mesh_id="mesh-1", config={"Istio": {"DisablePolicyChecks": False}})
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["mesh"]["Config"] == {"Istio": {"DisablePolicyChecks": False, "Extra": 1}}
    assert not any("ModifyMesh" == c[0] for c in fake.calls)


def test_present_immutable_mesh_version_drift_fails(monkeypatch):
    fake = FakeTcmClient([_mesh()])
    _make_module(monkeypatch, fake)
    _run_args(mesh_id="mesh-1", mesh_version="1.22.0")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["replacement_required"] is True
    assert payload["immutable_changes"]["MeshVersion"]["before"] == "1.20.5"
    assert payload["immutable_changes"]["MeshVersion"]["after"] == "1.22.0"
    assert not any("ModifyMesh" == c[0] for c in fake.calls)


def test_present_immutable_type_drift_fails(monkeypatch):
    fake = FakeTcmClient([_mesh()])
    _make_module(monkeypatch, fake)
    _run_args(mesh_id="mesh-1", mesh_type="MANAGED")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["immutable_changes"]["Type"]["before"] == "HOSTED"


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeTcmModels(), SimpleNamespace(TcmClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args(name="mesh-x", mesh_version="1.22.0", mesh_type="HOSTED")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTcmClient()
    _make_module(monkeypatch, fake)
    module_args(
        _ansible_check_mode=True,
        name="mesh-x",
        mesh_version="1.22.0",
        mesh_type="HOSTED",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["mesh"]["DisplayName"] == "mesh-x"  # desired reported
    assert not any("CreateMesh" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeTcmClient([_mesh()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, mesh_id="mesh-1", name="renamed")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["mesh"]["DisplayName"] == "renamed"  # desired reported
    assert not any("ModifyMesh" == c[0] for c in fake.calls)


def test_absent_removes_mesh(monkeypatch):
    fake = FakeTcmClient([_mesh()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="production-mesh")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["mesh"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteMesh"][0][1]
    assert delete.MeshId == "mesh-1"
    assert fake.meshes == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeTcmClient([_mesh()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["mesh"] is None
    assert not any("DeleteMesh" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTcmClient([_mesh()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", name="production-mesh")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["mesh"] is None
    assert not any("DeleteMesh" == c[0] for c in fake.calls)
    assert len(fake.meshes) == 1
