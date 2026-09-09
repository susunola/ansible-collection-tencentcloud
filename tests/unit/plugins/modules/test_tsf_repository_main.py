"""Unit tests for the tsf_repository write module.

Drives ``run_module()`` against an in-memory fake TSF client whose
repository describe / create / update / delete calls mutate a repository
list so post-write describes converge immediately.

Repository semantics: storage placement (name, type, bucket, directory) is
immutable after creation. Only the description is mutable, so a present-run
with description drift updates while placement drift is rejected.

Scenario matrix:

* present: create private and default repositories, description drift
  update, no-drift no-op, check-mode dry run, private-bucket guard,
  immutable placement drift rejection
* absent: no-op, delete, check mode, rejected delete
* lookup ambiguity guard and the blanket SDK failure path
* legacy pure-helper assertions folded from the shallow test file
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tsf_repository as mod
from ansible_collections.susunola.tencentcloud.plugins.modules.tsf_repository import desired
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

REPO_NAME = "packages"
STORE_KEYS = ("RepositoryName", "RepositoryType", "RepositoryDesc", "BucketName", "BucketRegion", "Directory")


def _repository(repository_id, **overrides):
    value = {"RepositoryId": repository_id, "RepositoryName": REPO_NAME,
             "RepositoryType": "default", "RepositoryDesc": "production"}
    value.update(overrides)
    return value


def _repo_args(**overrides):
    params = {"name": REPO_NAME, "repository_type": "default", "description": "production", "state": "present"}
    params.update(overrides)
    return module_args(**params)


class FakeTsfClient(object):
    """In-memory TSF client backed by a mutable repository list."""

    def __init__(self, repositories=None):
        self.repositories = [dict(r) for r in repositories or []]
        self.calls = []
        self._next_id = 1

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeRepository(self, request):
        self._record("DescribeRepository", request)
        for repository in self.repositories:
            if repository["RepositoryId"] == getattr(request, "RepositoryId", None):
                return SimpleNamespace(Result=FakeResource(dict(repository)), RequestId="req-fake")
        return SimpleNamespace(Result=None, RequestId="req-fake")

    def DescribeRepositories(self, request):
        self._record("DescribeRepositories", request)
        payload = [FakeResource(dict(r)) for r in self.repositories]
        return SimpleNamespace(Result=SimpleNamespace(Content=payload), RequestId="req-fake")

    def CreateRepository(self, request):
        self._record("CreateRepository", request)
        repository = {"RepositoryId": "repo-%d" % self._next_id}
        self._next_id += 1
        for key in STORE_KEYS:
            if hasattr(request, key):
                repository[key] = getattr(request, key)
        self.repositories.append(repository)
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def UpdateRepository(self, request):
        self._record("UpdateRepository", request)
        for repository in self.repositories:
            if repository["RepositoryId"] == getattr(request, "RepositoryId", None):
                if hasattr(request, "RepositoryDesc"):
                    repository["RepositoryDesc"] = getattr(request, "RepositoryDesc")
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def DeleteRepository(self, request):
        self._record("DeleteRepository", request)
        self.repositories = [r for r in self.repositories
                             if r["RepositoryId"] != getattr(request, "RepositoryId", None)]
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


def test_present_creates_default_repository(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _repo_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["repository"]["RepositoryId"] == "repo-1"
    assert result["repository"]["RepositoryName"] == REPO_NAME
    assert result["repository"]["RepositoryType"] == "default"
    assert result["repository"]["RepositoryDesc"] == "production"
    assert "CreateRepository" in _names(fake)
    assert len(fake.repositories) == 1


def test_present_creates_private_repository_with_bucket(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _repo_args(repository_type="private", bucket_name="packages-1250000000",
               bucket_region="ap-guangzhou", directory="releases")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["repository"]["RepositoryType"] == "private"
    assert result["repository"]["BucketName"] == "packages-1250000000"
    assert result["repository"]["BucketRegion"] == "ap-guangzhou"
    assert result["repository"]["Directory"] == "releases"


def test_present_no_drift_is_idempotent(monkeypatch):
    fake = FakeTsfClient(repositories=[_repository("repo-7")])
    _make_module(monkeypatch, fake)
    _repo_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["repository"]["RepositoryId"] == "repo-7"
    assert "CreateRepository" not in _names(fake)
    assert "UpdateRepository" not in _names(fake)


def test_present_description_drift_triggers_update(monkeypatch):
    fake = FakeTsfClient(repositories=[_repository("repo-7", RepositoryDesc="old")])
    _make_module(monkeypatch, fake)
    _repo_args(description="new")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["repository"]["RepositoryDesc"] == "new"
    assert "UpdateRepository" in _names(fake)
    assert fake.repositories[0]["RepositoryDesc"] == "new"


def test_present_private_without_bucket_fails(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _repo_args(repository_type="private")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "bucket_name and bucket_region are required" in exc.value.args[0]["msg"]


def test_present_immutable_placement_drift_is_rejected(monkeypatch):
    current = _repository("repo-7", RepositoryType="private", BucketName="bucket-1", BucketRegion="ap-guangzhou")
    fake = FakeTsfClient(repositories=[current])
    _make_module(monkeypatch, fake)
    _repo_args(repository_type="private", bucket_name="bucket-2", bucket_region="ap-guangzhou")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed on an existing" in payload["msg"]
    assert "BucketName" in payload["immutable_changes"]
    assert "UpdateRepository" not in _names(fake)


def test_present_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _repo_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["repository"]["RepositoryName"] == REPO_NAME
    assert "RepositoryId" not in result["repository"]
    assert "CreateRepository" not in _names(fake)
    assert fake.repositories == []


# ---------------------------------------------------------------------------
# lookup semantics
# ---------------------------------------------------------------------------


def test_multiple_matching_repositories_fail(monkeypatch):
    fake = FakeTsfClient(repositories=[_repository("repo-1", RepositoryDesc="a"),
                                       _repository("repo-2", RepositoryDesc="b")])
    _make_module(monkeypatch, fake)
    _repo_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSF repositories matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_unregistered_is_idempotent(monkeypatch):
    fake = FakeTsfClient(repositories=[_repository("repo-7", RepositoryName="other")])
    _make_module(monkeypatch, fake)
    _repo_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["repository"] is None
    assert "DeleteRepository" not in _names(fake)


def test_absent_deletes_repository(monkeypatch):
    fake = FakeTsfClient(repositories=[_repository("repo-7")])
    _make_module(monkeypatch, fake)
    _repo_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["repository"] is None
    assert "DeleteRepository" in _names(fake)
    assert fake.repositories == []


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfClient(repositories=[_repository("repo-7")])
    _make_module(monkeypatch, fake)
    _repo_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["repository"] is None
    assert "DeleteRepository" not in _names(fake)
    assert len(fake.repositories) == 1


def test_rejected_delete_fails(monkeypatch):
    class RejectingClient(FakeTsfClient):
        def DeleteRepository(self, request):
            self._record("DeleteRepository", request)
            return SimpleNamespace(Result=False, RequestId="req-err")

    fake = RejectingClient(repositories=[_repository("repo-7")])
    _make_module(monkeypatch, fake)
    _repo_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rejected the TSF repository deletion" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeRepositories(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _repo_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy pure-helper assertions (folded from the shallow test file)
# ---------------------------------------------------------------------------


def test_legacy_desired_maps_storage_and_description():
    params = {"name": "packages", "repository_type": "private", "description": "production",
              "bucket_name": "packages-1250000000", "bucket_region": "ap-guangzhou", "directory": "releases"}
    assert desired(params) == {
        "RepositoryName": "packages",
        "RepositoryType": "private",
        "RepositoryDesc": "production",
        "BucketName": "packages-1250000000",
        "BucketRegion": "ap-guangzhou",
        "Directory": "releases",
    }
