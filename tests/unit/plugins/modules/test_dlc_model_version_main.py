"""Unit tests for the dlc_model_version write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake DLC client
whose ``CreateModelVersion`` mutates the model-version store, so the
module's post-write ``find`` refetch and ``wait_version`` converge on the
first poll.

Scenario matrix:

* pre-SDK validation (COS requires storage_uri, LOCAL rejects goosefs_config)
* creation (missing version, check mode, wait:false, a create that never
  becomes visible)
* existing (no-drift idempotency, immutable conflicting-metadata drift)
* multiple exact-label matches guard and the blanket ``sdk_error_payload``
  failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_model_version as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

DESCRIPTION = "Quantized production release"
STORAGE_URI = "cos://model-bucket/bge/v2/"


def _version(**overrides):
    item = {
        "VersionId": "mv-1",
        "Version": "v2",
        "Description": DESCRIPTION,
        "StorageUri": STORAGE_URI,
        "UseCustomStorage": True,
        "StorageType": "COS",
    }
    item.update(overrides)
    return item


def _plain(value):
    """Recursively unwrap FakeRequest/model stand-ins into plain data."""
    if value is None or isinstance(value, bool) or isinstance(value, (str, int, float)):
        return value
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return {key: _plain(item) for key, item in vars(value).items()}


class FakeDlcModelVersionClient(object):
    """In-memory DLC model-version client."""

    def __init__(self, versions=None, create_stores=True):
        self.versions = [copy.deepcopy(item) for item in (versions or [])]
        self.calls = []
        self._next = 0
        self.create_stores = create_stores

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def ListModelVersions(self, request):
        self._record("ListModelVersions", request)
        return SimpleNamespace(
            Items=[FakeResource(item) for item in self.versions],
            TotalPages=1,
            RequestId="req-fake",
        )

    def CreateModelVersion(self, request):
        self._record("CreateModelVersion", request)
        if not self.create_stores:
            return SimpleNamespace(VersionId="mv-new", RequestId="req-fake")
        self._next += 1
        item = {"Version": request.ModelVersion, "VersionId": "mv-%03d" % self._next}
        for key, value in vars(request).items():
            if key not in ("ModelUid", "ModelVersion"):
                item[key] = _plain(value)
        self.versions.append(item)
        return SimpleNamespace(VersionId=item["VersionId"], RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _args(**overrides):
    params = {
        "model_uid": "model-bge-managed",
        "version": "v2",
        "description": DESCRIPTION,
        "storage_uri": STORAGE_URI,
        "use_custom_storage": True,
        "storage_type": "COS",
        "wait": True,
    }
    params.update(overrides)
    return module_args(**params)


def _ops(fake):
    return [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# pre-SDK validation
# ---------------------------------------------------------------------------


def test_cos_requires_storage_uri(monkeypatch):
    fake = FakeDlcModelVersionClient(versions=[])
    _make_module(monkeypatch, fake)
    _args(storage_uri=None, storage_type="COS")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "storage_uri is required for CFS, COS and CFSTurbo versions" in exc.value.args[0]["msg"]


def test_local_rejects_goosefs_config(monkeypatch):
    fake = FakeDlcModelVersionClient(versions=[])
    _make_module(monkeypatch, fake)
    _args(storage_uri=None, storage_type="LOCAL", goosefs_config={"Name": "fs"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "goosefs_config cannot be used with LOCAL storage" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_new_model_version(monkeypatch):
    fake = FakeDlcModelVersionClient(versions=[])
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["model_version"]["Version"] == "v2"
    assert result["model_version"]["Description"] == DESCRIPTION
    assert result["model_version"]["StorageUri"] == STORAGE_URI
    assert result["version_id"] == "mv-001"
    assert len(fake.versions) == 1
    assert fake.versions[0]["Version"] == "v2"
    ops = _ops(fake)
    assert "CreateModelVersion" in ops
    assert ops[-1] == "ListModelVersions"


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcModelVersionClient(versions=[])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["model_version"]["Version"] == "v2"
    assert result["model_version"]["Description"] == DESCRIPTION
    assert result["version_id"] is None
    assert fake.versions == []
    assert "CreateModelVersion" not in _ops(fake)


def test_create_with_goosefs_config(monkeypatch):
    fake = FakeDlcModelVersionClient(versions=[])
    _make_module(monkeypatch, fake)
    config = {"Name": "bge-fs", "Type": "HDFS"}
    _args(storage_type="GooseFS", storage_uri=None, goosefs_config=config)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.versions[0]["GooseFSConfig"] == config
    assert fake.versions[0]["Version"] == "v2"


def test_create_without_wait_skips_waiter(monkeypatch):
    fake = FakeDlcModelVersionClient(versions=[])
    _make_module(monkeypatch, fake)
    _args(wait=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["version_id"] == "mv-001"
    # Create is still followed by one post-write find refetch.
    ops = _ops(fake)
    assert "CreateModelVersion" in ops
    assert ops.count("ListModelVersions") == 2


def test_create_wait_timeout_when_version_invisible(monkeypatch):
    fake = FakeDlcModelVersionClient(versions=[], create_stores=False)
    _make_module(monkeypatch, fake)
    _args(waiter_timeout=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Timed out waiting for resource state"
    assert payload["expected_states"] == ["ready"]


# ---------------------------------------------------------------------------
# existing-version flows
# ---------------------------------------------------------------------------


def test_existing_version_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcModelVersionClient(versions=[_version()])
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["model_version"]["VersionId"] == "mv-1"
    assert result["version_id"] == "mv-1"
    assert "CreateModelVersion" not in _ops(fake)


def test_existing_version_conflicting_metadata_fails(monkeypatch):
    fake = FakeDlcModelVersionClient(versions=[_version(Description="old description")])
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "immutable and the requested label already has conflicting metadata" in payload["msg"]
    assert payload["immutable_drift"]["Description"] == ("old description", DESCRIPTION)


def test_multiple_matching_versions_fail(monkeypatch):
    fake = FakeDlcModelVersionClient(versions=[_version(), _version(VersionId="mv-2")])
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DLC model versions matched the exact label" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def ListModelVersions(self, request):
            raise Boom("catalog unavailable")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "catalog unavailable" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_dlc_model_version.py)
# ---------------------------------------------------------------------------


class LegacyModel(object):
    def from_json_string(self, value):
        import json

        for key, item in json.loads(value).items():
            setattr(self, key, item)


class LegacyModels(object):
    ListModelVersionsRequest = CreateModelVersionRequest = GooseFSConfig = LegacyModel


def legacy_params():
    return {
        "model_uid": "model-1",
        "version": "v2",
        "description": "release",
        "storage_uri": "cos://bucket/v2",
        "use_custom_storage": True,
        "storage_type": "COS",
        "goosefs_config": None,
    }


def test_immutable_version_conflict_is_precise():
    p = legacy_params()
    current = {"Version": "v2", "Description": "old", "StorageUri": "cos://bucket/v2", "UseCustomStorage": True}
    assert mod.conflict(p, current) == {"Description": ("old", "release")}
    assert mod.desired(p)["Version"] == "v2"


def test_create_and_list_requests_use_parent_and_exact_version():
    p = legacy_params()
    create = mod.create_request(LegacyModels, p)
    listing = mod.list_request(LegacyModels, p, 4)
    assert create.ModelUid == "model-1" and create.ModelVersion == "v2" and create.StorageType == "COS"
    assert listing.ModelUid == "model-1" and listing.Page == 4 and listing.PageSize == 200
