"""Unit tests for the cls_index write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake CLS client
whose write operations mutate the topic-index store, so the module's
post-write ``find`` refetch converges immediately.

Scenario matrix:

* absent on a missing index (idempotent no-op)
* absent with an existing index (check-mode dry run and the real delete)
* creation when missing (check mode and the happy path)
* no-op when the index matches the desired full-text configuration
* drift updates (enabled flag, case sensitivity, coverage field)
* the blanket ``Tencent Cloud API request failed`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cls_index as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

TOPIC = "b96f4d4e-2a11-4b1a-9f2c-abcdef123456"

INDEX = {
    "Status": True,
    "IncludeInternalFields": False,
    "MetadataFlag": 0,
    "CoverageField": "message",
    "Rule": {"FullText": {"CaseSensitive": False, "Tokenizer": ",; ", "ContainZH": True}},
}


class MissingIndex(Exception):
    """Mirror the SDK ``ResourceNotFound`` shape used for idempotent lookups."""

    def get_code(self):
        return "ResourceNotFound.IndexNotExist"


def _index(**overrides):
    item = copy.deepcopy(INDEX)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"topic_id": TOPIC}
    params.update(overrides)
    return module_args(**params)


class FakeClsClient(object):
    """In-memory CLS client mutating a topic-index store."""

    def __init__(self, index=None, missing=None):
        self.index = copy.deepcopy(index)
        # ``missing`` is an optional pre-existing marker: the fake raises
        # ResourceNotFound only while the topic has no index.
        self.missing = missing if missing is not None else index is None
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeIndex(self, request):
        self._record("DescribeIndex", request)
        if self.index is None and self.missing:
            raise MissingIndex("index not found")
        return FakeResource(self.index)

    def CreateIndex(self, request):
        self._record("CreateIndex", request)
        full = getattr(getattr(request, "Rule", None), "FullText", None)
        self.index = {
            "Status": getattr(request, "Status", None),
            "IncludeInternalFields": getattr(request, "IncludeInternalFields", None),
            "MetadataFlag": getattr(request, "MetadataFlag", None),
            "Rule": {
                "FullText": {
                    "CaseSensitive": getattr(full, "CaseSensitive", None),
                    "Tokenizer": getattr(full, "Tokenizer", None),
                    "ContainZH": getattr(full, "ContainZH", None),
                }
            },
        }
        if getattr(request, "CoverageField", None) is not None:
            self.index["CoverageField"] = request.CoverageField
        return SimpleNamespace(RequestId="req-fake")

    def ModifyIndex(self, request):
        self._record("ModifyIndex", request)
        if self.index is None:
            return SimpleNamespace(RequestId="req-fake")
        full = getattr(getattr(request, "Rule", None), "FullText", None)
        self.index["Status"] = getattr(request, "Status", None)
        self.index["IncludeInternalFields"] = getattr(request, "IncludeInternalFields", None)
        self.index["MetadataFlag"] = getattr(request, "MetadataFlag", None)
        self.index.setdefault("Rule", {})["FullText"] = {
            "CaseSensitive": getattr(full, "CaseSensitive", None),
            "Tokenizer": getattr(full, "Tokenizer", None),
            "ContainZH": getattr(full, "ContainZH", None),
        }
        if getattr(request, "CoverageField", None) is not None:
            self.index["CoverageField"] = request.CoverageField
        return SimpleNamespace(RequestId="req-fake")

    def DeleteIndex(self, request):
        self._record("DeleteIndex", request)
        self.index = None
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(ClsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _ops(fake):
    return [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_index_is_idempotent(monkeypatch):
    fake = FakeClsClient(index=None)
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["index"] is None
    assert _ops(fake) == ["DescribeIndex"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeClsClient(index=_index())
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["index"] is not None
    assert fake.index is not None
    assert "DeleteIndex" not in _ops(fake)


def test_absent_deletes_index(monkeypatch):
    fake = FakeClsClient(index=_index())
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["index"] is None
    assert fake.index is None
    assert "DeleteIndex" in _ops(fake)


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_index(monkeypatch):
    fake = FakeClsClient(index=None)
    _make_module(monkeypatch, fake)
    _base(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["index"]["Status"] is True
    assert result["index"]["Rule"]["FullText"]["Tokenizer"] == ",; "
    assert fake.index is not None
    ops = _ops(fake)
    assert ops[0] == "DescribeIndex"
    assert "CreateIndex" in ops


def test_create_index_with_customized_fields(monkeypatch):
    fake = FakeClsClient(index=None)
    _make_module(monkeypatch, fake)
    _base(state="present", enabled=False, case_sensitive=True, full_text_delimiters="@#", contain_zh=False, coverage_field="host")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["index"]["Status"] is False
    assert result["index"]["CoverageField"] == "host"
    assert result["index"]["Rule"]["FullText"]["CaseSensitive"] is True
    assert result["index"]["Rule"]["FullText"]["ContainZH"] is False
    assert "CreateIndex" in _ops(fake)


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeClsClient(index=None)
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.index is None
    assert "CreateIndex" not in _ops(fake)


# ---------------------------------------------------------------------------
# existing-index flows
# ---------------------------------------------------------------------------


def test_existing_index_no_drift_is_idempotent(monkeypatch):
    fake = FakeClsClient(index=_index())
    _make_module(monkeypatch, fake)
    _base(state="present", coverage_field="message")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["index"]["MetadataFlag"] == 0
    assert "ModifyIndex" not in _ops(fake)


def test_existing_index_enabled_drift_updates(monkeypatch):
    fake = FakeClsClient(index=_index())
    _make_module(monkeypatch, fake)
    _base(state="present", enabled=False, coverage_field="message")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["index"]["Status"] is False
    assert "ModifyIndex" in _ops(fake)
    assert "CreateIndex" not in _ops(fake)


def test_existing_index_tokenizer_drift_updates(monkeypatch):
    fake = FakeClsClient(index=_index())
    _make_module(monkeypatch, fake)
    _base(state="present", full_text_delimiters="@#", coverage_field="message")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["index"]["Rule"]["FullText"]["Tokenizer"] == "@#"
    assert "ModifyIndex" in _ops(fake)


def test_existing_index_check_mode_dry_run(monkeypatch):
    fake = FakeClsClient(index=_index())
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", enabled=False, coverage_field="message")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.index["Status"] is True
    assert "ModifyIndex" not in _ops(fake)


# ---------------------------------------------------------------------------
# failure path
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeIndex(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
