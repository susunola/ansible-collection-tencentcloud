"""Unit tests for the dlc_database write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake DLC client whose
write operations mutate the metadata-database store, so the post-write
describe refetch and waiters converge immediately.

Scenario matrix:

* argument validation (comment length)
* absent on a missing database (idempotent) / allow_delete guard /
  non-empty guard / check-mode dry run / real delete
* creation when missing (check mode, real create)
* no-op when nothing drifts
* immutable drift failure (comment and governance policy)
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_database as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

DATABASE = {
    "DatabaseName": "analytics",
    "Comment": "Curated analytics datasets",
}


class NotFoundError(Exception):
    def get_code(self):
        return "ResourceNotFound.Database"

    def get_request_id(self):
        return "req-404"


def _database(**overrides):
    item = copy.deepcopy(DATABASE)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "analytics"}
    params.update(overrides)
    return module_args(**params)


class FakeDlcClient(object):
    """In-memory DLC client mutating a metadata-database store."""

    def __init__(self, databases=None, table_counts=None):
        self.databases = [copy.deepcopy(t) for t in (databases or [])]
        self.table_counts = dict(table_counts or {})
        self.calls = []
        self._next = 0

    def _find(self, name):
        for item in self.databases:
            if item.get("DatabaseName") == name:
                return item
        raise NotFoundError("database %s not found" % name)

    def DescribeDatabase(self, request):
        self.calls.append("DescribeDatabase")
        item = self._find(getattr(request, "DatabaseName", None))
        return SimpleNamespace(DatabaseInfo=FakeResource(dict(item)), RequestId="req-fake")

    def DescribeTables(self, request):
        self.calls.append("DescribeTables")
        name = getattr(request, "DatabaseName", None)
        count = self.table_counts.get(name, 0)
        return SimpleNamespace(TotalCount=count, RequestId="req-fake")

    def CreateMetaDatabase(self, request):
        self.calls.append("CreateMetaDatabase")
        self._next += 1
        info = getattr(request, "MetaDatabaseInfo", None)
        item = {"DatabaseName": getattr(info, "DatabaseName", None), "Comment": getattr(info, "Comment", None)}
        govern = getattr(request, "GovernPolicy", None)
        if govern is not None:
            item["GovernPolicy"] = dict(getattr(govern, "__dict__", {}) or {})
        self.databases.append(item)
        return SimpleNamespace(BatchId="batch-%03d" % self._next, RequestId="req-fake")

    def DeleteMetaDatabase(self, request):
        self.calls.append("DeleteMetaDatabase")
        self.databases = [t for t in self.databases if t.get("DatabaseName") != getattr(request, "DatabaseName", None)]
        return SimpleNamespace(BatchId="batch-del", RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# argument validation
# ---------------------------------------------------------------------------


def test_comment_too_long_fails(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    _base(state="absent", comment="x" * 2049)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "comment must not exceed 2048 characters" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_database_is_idempotent(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["database"] is None
    assert result["batch_id"] is None
    assert list(fake.calls) == ["DescribeDatabase"]


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeDlcClient(databases=[_database()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]


def test_absent_nonempty_database_requires_guard(monkeypatch):
    fake = FakeDlcClient(databases=[_database()], table_counts={"analytics": 3})
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete_nonempty=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(databases=[_database()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["batch_id"] is None
    assert len(fake.databases) == 1
    assert "DeleteMetaDatabase" not in fake.calls


def test_absent_deletes_database(monkeypatch):
    fake = FakeDlcClient(databases=[_database()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["batch_id"] == "batch-del"
    assert fake.databases == []
    ops = list(fake.calls)
    assert "DeleteMetaDatabase" in ops


def test_absent_deletes_nonempty_database(monkeypatch):
    fake = FakeDlcClient(databases=[_database()], table_counts={"analytics": 3})
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True, allow_delete_nonempty=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.databases == []
    ops = list(fake.calls)
    assert "DescribeTables" in ops
    assert "DeleteMetaDatabase" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_database(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    _base(comment="Curated analytics datasets", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["database"]["DatabaseName"] == "analytics"
    assert result["database"]["Comment"] == "Curated analytics datasets"
    assert result["batch_id"].startswith("batch-")
    assert len(fake.databases) == 1
    ops = list(fake.calls)
    assert ops[0] == "DescribeDatabase"
    assert "CreateMetaDatabase" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient()
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, comment="Curated analytics datasets")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["database"]["Comment"] == "Curated analytics datasets"
    assert result["batch_id"] is None
    assert fake.databases == []
    assert "CreateMetaDatabase" not in fake.calls


# ---------------------------------------------------------------------------
# existing-database flows
# ---------------------------------------------------------------------------


def test_existing_database_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcClient(databases=[_database()])
    _make_module(monkeypatch, fake)
    _base(comment="Curated analytics datasets")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["database"]["DatabaseName"] == "analytics"
    assert result["batch_id"] is None
    ops = list(fake.calls)
    assert "CreateMetaDatabase" not in ops


def test_immutable_comment_drift_fails(monkeypatch):
    fake = FakeDlcClient(databases=[_database()])
    _make_module(monkeypatch, fake)
    _base(comment="changed comment")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "immutable" in payload["msg"]
    assert "Comment" in payload["immutable_drift"]


def test_immutable_govern_policy_drift_fails(monkeypatch):
    govern = {"GovernanceLevel": "L1", "RuleName": "anonymize"}
    fake = FakeDlcClient(databases=[_database(GovernPolicy=govern)])
    _make_module(monkeypatch, fake)
    _base(govern_policy={"GovernanceLevel": "L2", "RuleName": "anonymize"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "GovernPolicy" in payload["immutable_drift"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeDatabase(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
