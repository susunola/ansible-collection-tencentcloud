"""Unit tests for the elasticsearch_index write module (run_module flows).

Creates, updates and deletes normal or autonomous Elasticsearch indexes. The
index is resolved through ``DescribeIndexMeta``; a missing index surfaces
either as a ``ResourceNotFound``-style SDK error or as an empty
``IndexMetaField`` and both read as absent. Metadata comparison is
containment-based: service-added settings and mappings are tolerated as long
as every requested key matches.

Scenario matrix:

* absent on a missing index is idempotent (SDK not-found and empty response)
* absent deletes the index (check mode is a dry run)
* creation when missing (happy path and check mode)
* no-op when the returned metadata contains every requested setting/mapping
* metadata drift triggers an update
* SDK failure maps to the standard error envelope
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import elasticsearch_index as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

META = {
    "settings": {"number_of_shards": 3, "number_of_replicas": 1},
    "mappings": {"properties": {"order_id": {"type": "keyword"}}},
}


def _meta(**overrides):
    item = copy.deepcopy(META)
    _deep_update(item, overrides)
    return item


def _deep_update(base, patch):
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def _index(**overrides):
    record = {
        "InstanceId": "es-abc123",
        "IndexType": "normal",
        "IndexName": "orders",
        "Username": "elastic",
        "IndexMetaJson": json.dumps(META, sort_keys=True, separators=(",", ":")),
        "RequestId": "req-fake",
    }
    record.update(overrides)
    return record


def _params(**overrides):
    params = {
        "instance_id": "es-abc123",
        "name": "orders",
        "index_type": "normal",
        "username": "elastic",
        "password": "cluster-secret",
    }
    params.update(overrides)
    return params


def _run_args(**overrides):
    return module_args(**_params(**overrides))


class _NotFound(Exception):
    """ResourceNotFound-style SDK error with a get_code hook."""

    def get_code(self):
        return "ResourceNotFound"


class FakeEsClient(object):
    """In-memory ES client holding indexes keyed by name.

    ``missing_mode`` selects how a missing index reads back: ``raise``
    (the SDK raises ResourceNotFound), ``empty`` (the response carries a
    ``None`` IndexMetaField) or ``message`` (the exception text mentions
    "not found" but carries no code).
    """

    def __init__(self, indexes=None, missing_mode="raise"):
        self.indexes = {}
        for record in indexes or []:
            self.indexes[record["IndexName"]] = copy.deepcopy(record)
        self.missing_mode = missing_mode
        self.calls = []

    def DescribeIndexMeta(self, request):
        self.calls.append(("DescribeIndexMeta", request))
        name = getattr(request, "IndexName", None)
        if name not in self.indexes:
            if self.missing_mode == "empty":
                return SimpleNamespace(IndexMetaField=None, RequestId="req-fake")
            if self.missing_mode == "message":
                raise RuntimeError("index was not found")
            raise _NotFound()
        return SimpleNamespace(IndexMetaField=FakeResource(self.indexes[name]), RequestId="req-fake")

    def CreateIndex(self, request):
        self.calls.append(("CreateIndex", request))
        record = {
            "InstanceId": request.InstanceId,
            "IndexType": request.IndexType,
            "IndexName": request.IndexName,
            "Username": request.Username,
            "IndexMetaJson": request.IndexMetaJson,
        }
        self.indexes[request.IndexName] = record
        return SimpleNamespace(RequestId="req-fake")

    def UpdateIndex(self, request):
        self.calls.append(("UpdateIndex", request))
        if request.IndexName in self.indexes:
            self.indexes[request.IndexName]["IndexMetaJson"] = request.UpdateMetaJson
        return SimpleNamespace(RequestId="req-fake")

    def DeleteIndex(self, request):
        self.calls.append(("DeleteIndex", request))
        self.indexes.pop(request.IndexName, None)
        return SimpleNamespace(RequestId="req-fake")


class _BoomClient(object):
    """Every SDK call raises so the wrapped SDK failure path is reached."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("connection dropped")

        return boom


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(EsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_index_is_idempotent(monkeypatch):
    fake = FakeEsClient(indexes=[])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["index"] is None
    assert [name for name, unused in fake.calls] == ["DescribeIndexMeta"]


def test_absent_missing_index_via_message_is_idempotent(monkeypatch):
    # An exception whose text mentions "not found" also reads as absent.
    fake = FakeEsClient(indexes=[], missing_mode="message")
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["index"] is None


def test_absent_empty_index_meta_field_is_idempotent(monkeypatch):
    fake = FakeEsClient(indexes=[], missing_mode="empty")
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["index"] is None


def test_absent_deletes_index(monkeypatch):
    fake = FakeEsClient(indexes=[_index()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["index"] is None
    assert fake.indexes == {}
    ops = [name for name, unused in fake.calls]
    assert ops == ["DescribeIndexMeta", "DeleteIndex"]


def test_absent_in_check_mode_is_dry_run(monkeypatch):
    fake = FakeEsClient(indexes=[_index()])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["index"]["IndexName"] == "orders"  # existing index shown as preview
    assert len(fake.indexes) == 1
    assert "DeleteIndex" not in [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_index(monkeypatch):
    fake = FakeEsClient(indexes=[])
    _make_module(monkeypatch, fake)
    _run_args(state="present", index_type="normal", metadata=META)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["index"]["IndexName"] == "orders"
    assert result["index"]["IndexType"] == "normal"
    assert result["index"]["Metadata"]["settings"]["number_of_shards"] == 3
    assert len(fake.indexes) == 1
    ops = [name for name, unused in fake.calls]
    assert ops[0] == "DescribeIndexMeta"
    assert "CreateIndex" in ops
    create = [request for name, request in fake.calls if name == "CreateIndex"][0]
    assert create.IndexName == "orders"
    assert json.loads(create.IndexMetaJson)["settings"]["number_of_shards"] == 3


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeEsClient(indexes=[])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, state="present", metadata=META)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["index"] is None
    assert fake.indexes == {}
    assert "CreateIndex" not in [name for name, unused in fake.calls]


def test_autonomous_index_create(monkeypatch):
    fake = FakeEsClient(indexes=[])
    _make_module(monkeypatch, fake)
    _run_args(state="present", index_type="auto", metadata={"settings": {"number_of_shards": 1}})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["index"]["IndexType"] == "auto"
    create = [request for name, request in fake.calls if name == "CreateIndex"][0]
    assert create.IndexType == "auto"


# ---------------------------------------------------------------------------
# existing-index flows
# ---------------------------------------------------------------------------


def test_matching_metadata_is_idempotent(monkeypatch):
    # The service may add settings/mappings of its own; containment wins.
    extra = {
        "settings": {"number_of_shards": 3, "number_of_replicas": 1, "refresh_interval": "1s"},
        "mappings": {
            "properties": {"order_id": {"type": "keyword"}, "customer_id": {"type": "keyword"}},
            "dynamic": False,
        },
    }
    fake = FakeEsClient(indexes=[_index(IndexMetaJson=json.dumps(extra, sort_keys=True, separators=(",", ":")))])
    _make_module(monkeypatch, fake)
    _run_args(state="present", metadata=META)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["index"]["Metadata"]["settings"]["refresh_interval"] == "1s"
    assert "UpdateIndex" not in [name for name, unused in fake.calls]


def test_matching_list_value_is_idempotent(monkeypatch):
    # _contains requires exact equality for list-valued metadata entries.
    meta = {"settings": {"number_of_shards": 3}, "aliases": ["orders-a", "orders-b"]}
    fake = FakeEsClient(indexes=[_index(IndexMetaJson=json.dumps(meta, sort_keys=True, separators=(",", ":")))])
    _make_module(monkeypatch, fake)
    _run_args(state="present", metadata=meta)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["index"]["Metadata"]["aliases"] == ["orders-a", "orders-b"]


def test_metadata_drift_updates_index(monkeypatch):
    drift = _meta(**{"settings": {"number_of_replicas": 2}})
    fake = FakeEsClient(indexes=[_index(IndexMetaJson=json.dumps(drift, sort_keys=True, separators=(",", ":")))])
    _make_module(monkeypatch, fake)
    _run_args(state="present", metadata=META)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["index"]["Metadata"]["settings"]["number_of_replicas"] == 1
    ops = [name for name, unused in fake.calls]
    assert ops == ["DescribeIndexMeta", "UpdateIndex", "DescribeIndexMeta"]
    update = [request for name, request in fake.calls if name == "UpdateIndex"][0]
    assert update.IndexName == "orders"
    assert json.loads(update.UpdateMetaJson)["settings"]["number_of_replicas"] == 1


def test_unparsable_metadata_falls_back_to_raw_json(monkeypatch):
    # A non-JSON IndexMetaJson is kept as the raw string and treated as drift.
    fake = FakeEsClient(indexes=[_index(IndexMetaJson="not-valid-json")])
    _make_module(monkeypatch, fake)
    _run_args(state="present", metadata=META)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "UpdateIndex" in [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    _make_module(monkeypatch, _BoomClient())
    _run_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeEsClient(indexes=[_index()])
    _make_module(monkeypatch, fake)
    _run_args(state="present", metadata=META)
    result = run(mod.main)
    assert result["changed"] is False
    assert result["index"]["IndexName"] == "orders"
