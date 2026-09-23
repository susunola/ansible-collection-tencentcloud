"""Unit tests for the oceanus_resource write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake Oceanus client
whose write operations mutate the resource store so the post-write describe
refetch and the ``wait_for_state`` waiter converge on the first poll.

Scenario matrix:

* absent on a missing resource (idempotent no-op)
* absent with a matching resource (check-mode dry run, real delete, and the
  in-use reference guard with and without ``allow_delete_in_use``)
* creation when missing (missing name/location guards, check-mode dry run
  and the happy path)
* no-op when nothing drifts
* the immutable name/type drift guard
* the resource_type choice guard and the required_one_of guard
* the blanket ``Tencent Cloud API request failed`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import oceanus_resource as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RESOURCE_ID = "r-8a1b2c3d"

RESOURCE_LOC = {
    "StorageType": 1,
    "Param": {"Bucket": "flink-artifacts-1250000000", "Path": "jars/orders-1.0.jar", "Region": "ap-guangzhou"},
}

RESOURCE = {
    "ResourceId": RESOURCE_ID,
    "Name": "orders-processor",
    "ResourceType": 1,
    "ResourceLoc": copy.deepcopy(RESOURCE_LOC),
    "Remark": "orders pipeline",
    "FolderId": "root",
    "WorkSpaceId": "space-abc",
    "LatestResourceConfigVersion": 3,
}


def _resource(**overrides):
    item = copy.deepcopy(RESOURCE)
    item.update(overrides)
    return item


def _base(**overrides):
    # NOTE: keys carrying ``choices`` (state, resource_type) must not be
    # pre-filled with None. resource_id/name are a required_one_of pair so the
    # _name_args/_id_args helpers supply exactly one of them.
    params = {"workspace_id": "space-abc"}
    params.update(overrides)
    return module_args(**params)


def _name_args(**overrides):
    params = {"name": "orders-processor", "workspace_id": "space-abc"}
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {"resource_id": RESOURCE_ID, "workspace_id": "space-abc"}
    params.update(overrides)
    return module_args(**params)


class FakeOceanusClient(object):
    """In-memory Oceanus client mutating a small resource store."""

    def __init__(self, resources=None, ref_jobs=None):
        self.resources = [copy.deepcopy(t) for t in (resources or [])]
        self.ref_jobs = [copy.deepcopy(t) for t in (ref_jobs or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeResources(self, request):
        self._record("DescribeResources", request)
        ids = list(getattr(request, "ResourceIds", None) or [])
        if ids:
            page = [dict(t) for t in self.resources if t.get("ResourceId") in ids]
        else:
            wanted = None
            for item in (getattr(request, "Filters", None) or []):
                if getattr(item, "Name", None) == "ResourceName":
                    values = list(getattr(item, "Values", None) or [])
                    wanted = values[0] if values else None
            if wanted is not None:
                page = [dict(t) for t in self.resources if t.get("Name") == wanted]
            else:
                page = [dict(t) for t in self.resources]
        return SimpleNamespace(
            ResourceSet=[FakeResource(t) for t in page],
            TotalCount=len(page),
        )

    def DescribeResourceRelatedJobs(self, request):
        self._record("DescribeResourceRelatedJobs", request)
        page = [dict(t) for t in self.ref_jobs]
        return SimpleNamespace(
            RefJobInfos=[FakeResource(t) for t in page],
            TotalCount=len(page),
        )

    def CreateResource(self, request):
        self._record("CreateResource", request)
        version = 1
        item = {
            "ResourceId": "r-new-%d" % (len(self.resources) + 1),
            "Name": getattr(request, "Name", None),
            "ResourceType": getattr(request, "ResourceType", 1),
            "ResourceLoc": copy.deepcopy(RESOURCE_LOC),
            "Remark": getattr(request, "Remark", None),
            "FolderId": getattr(request, "FolderId", "root"),
            "WorkSpaceId": getattr(request, "WorkSpaceId", None),
            "LatestResourceConfigVersion": version,
        }
        self.resources.append(item)
        return SimpleNamespace(ResourceId=item["ResourceId"], Version=version, RequestId="req-fake")

    def DeleteResources(self, request):
        self._record("DeleteResources", request)
        ids = list(getattr(request, "ResourceIds", None) or [])
        self.resources = [t for t in self.resources if t.get("ResourceId") not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(OceanusClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_resource_is_idempotent(monkeypatch):
    fake = FakeOceanusClient(resources=[])
    _make_module(monkeypatch, fake)
    _id_args(state="absent", resource_id="r-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["resource"] is None
    assert [c for c, unused in fake.calls] == ["DescribeResources"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeOceanusClient(resources=[_resource()])
    _make_module(monkeypatch, fake)
    _id_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource"] is None
    assert len(fake.resources) == 1
    assert "DeleteResources" not in [c for c, unused in fake.calls]


def test_absent_deletes_resource(monkeypatch):
    fake = FakeOceanusClient(resources=[_resource()])
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource"] is None
    assert fake.resources == []
    assert "DeleteResources" in [c for c, unused in fake.calls]


def test_absent_referenced_fails_without_authorization(monkeypatch):
    fake = FakeOceanusClient(
        resources=[_resource()],
        ref_jobs=[{"ResourceId": RESOURCE_ID, "JobId": "job-1", "JobName": "orders"}],
    )
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "referenced by job configurations" in payload["msg"]
    assert "allow_delete_in_use=true" in payload["msg"]
    assert payload["references"][0]["JobName"] == "orders"
    assert fake.resources  # nothing deleted


def test_absent_referenced_deletes_when_authorized(monkeypatch):
    fake = FakeOceanusClient(
        resources=[_resource()],
        ref_jobs=[{"ResourceId": RESOURCE_ID, "JobId": "job-1", "JobName": "orders"}],
    )
    _make_module(monkeypatch, fake)
    _id_args(state="absent", allow_delete_in_use=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource"] is None
    assert fake.resources == []
    assert "DeleteResources" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_name_and_location(monkeypatch):
    fake = FakeOceanusClient(resources=[])
    _make_module(monkeypatch, fake)
    # resource_id references a resource that does not exist, so creation would
    # be required, but neither name nor resource_location are available.
    _id_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "name and resource_location are required to create" in payload["msg"]
    assert "name" in payload["missing"]
    assert "resource_location" in payload["missing"]


def test_create_requires_resource_location(monkeypatch):
    fake = FakeOceanusClient(resources=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", name="orders-processor")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "name and resource_location are required to create" in payload["msg"]
    assert "resource_location" in payload["missing"]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeOceanusClient(resources=[])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="present", resource_location=copy.deepcopy(RESOURCE_LOC))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["version"] is None
    assert result["resource"]["Name"] == "orders-processor"
    assert fake.resources == []
    assert "CreateResource" not in [c for c, unused in fake.calls]


def test_create_resource(monkeypatch):
    fake = FakeOceanusClient(resources=[])
    _make_module(monkeypatch, fake)
    _name_args(
        state="present",
        resource_location=copy.deepcopy(RESOURCE_LOC),
        remark="orders pipeline",
        version_remark="initial upload",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource"]["Name"] == "orders-processor"
    assert result["resource"]["ResourceType"] == 1
    assert result["version"] == 1
    assert len(fake.resources) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeResources"
    assert "CreateResource" in ops


# ---------------------------------------------------------------------------
# existing-resource flows
# ---------------------------------------------------------------------------


def test_existing_resource_no_drift_is_idempotent(monkeypatch):
    fake = FakeOceanusClient(resources=[_resource()])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["resource"]["ResourceId"] == RESOURCE_ID
    assert result["version"] == 3
    assert "CreateResource" not in [c for c, unused in fake.calls]


def test_existing_resource_immutable_name_drift_fails(monkeypatch):
    fake = FakeOceanusClient(resources=[_resource()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="renamed-processor")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "name and type are immutable" in payload["msg"]
    assert "Name" in payload["immutable_drift"]
    assert len(fake.resources) == 1


def test_existing_resource_remark_is_ignored(monkeypatch):
    # remark/version_remark only apply at creation time and must not be
    # reported as drift on an existing resource.
    fake = FakeOceanusClient(resources=[_resource()])
    _make_module(monkeypatch, fake)
    _name_args(state="present", remark="new purpose")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["resource"]["Name"] == "orders-processor"


# ---------------------------------------------------------------------------
# guards / validation / failure paths
# ---------------------------------------------------------------------------


def test_invalid_resource_type_choice_fails(monkeypatch):
    fake = FakeOceanusClient(resources=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", resource_type=2, resource_location=copy.deepcopy(RESOURCE_LOC))
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "value of resource_type must be one of" in exc.value.args[0]["msg"]


def test_missing_identity_fails(monkeypatch):
    fake = FakeOceanusClient(resources=[])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "resource_id" in payload["msg"]
    assert "name" in payload["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeResources(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _id_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_oceanus_resource.py)
# ---------------------------------------------------------------------------


class LegacyModel(object):
    def from_json_string(self, value):
        self.value = value


class LegacyModels(object):
    ResourceLoc = LegacyModel
    CreateResourceRequest = type("LegacyRequest", (), {})


def test_create_request_preserves_workspace_and_initial_version_metadata():
    p = {
        "name": "app",
        "workspace_id": "space-1",
        "resource_location": {"StorageType": 1},
        "resource_type": 1,
        "remark": "r",
        "version_remark": "v1",
        "folder_id": "root",
    }
    r = mod.create_request(LegacyModels, p)
    assert r.Name == "app" and r.WorkSpaceId == "space-1" and r.ResourceConfigRemark == "v1"
