"""Unit tests for the dlc_script write module (run_module flows)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import base64
import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_script as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SQL_TEXT = "SELECT sale_date, SUM(amount) FROM sales GROUP BY sale_date"

SCRIPT = {
    "ScriptId": "script-000001",
    "ScriptName": "daily-sales",
    "SQLStatement": base64.b64encode(SQL_TEXT.encode("utf-8")).decode("ascii"),
    "ScriptDesc": "Daily sales aggregation",
    "DatabaseName": "analytics",
}


def _b64(value):
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def _script(**overrides):
    item = copy.deepcopy(SCRIPT)
    item.update(overrides)
    return item


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


class FakeDlcClient(object):
    """In-memory DLC client mutating a saved-script store."""

    def __init__(self, scripts=None):
        self.scripts = [copy.deepcopy(t) for t in (scripts or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeScripts(self, request):
        self._record("DescribeScripts", request)
        return SimpleNamespace(Scripts=[FakeResource(t) for t in self.scripts], TotalCount=len(self.scripts))

    def CreateScript(self, request):
        self._record("CreateScript", request)
        self._next += 1
        item = {
            "ScriptId": "script-new-%03d" % self._next,
            "ScriptName": getattr(request, "ScriptName", None),
            "SQLStatement": getattr(request, "SQLStatement", None),
            "ScriptDesc": getattr(request, "ScriptDesc", None),
            "DatabaseName": getattr(request, "DatabaseName", None),
        }
        self.scripts.append(item)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteScript(self, request):
        self._record("DeleteScript", request)
        ids = list(getattr(request, "ScriptIds", None) or [])
        self.scripts = [t for t in self.scripts if t.get("ScriptId") not in ids]
        return SimpleNamespace(RequestId="req-fake")


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_script_is_idempotent(monkeypatch):
    fake = FakeDlcClient(scripts=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ghost-script")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["script"] is None
    assert result["script_id"] is None
    assert [c for c, unused in fake.calls] == ["DescribeScripts"]


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeDlcClient(scripts=[_script()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="daily-sales")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(scripts=[_script()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", name="daily-sales", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.scripts) == 1
    assert "DeleteScript" not in [c for c, unused in fake.calls]


def test_absent_deletes_script(monkeypatch):
    fake = FakeDlcClient(scripts=[_script()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="daily-sales", allow_delete=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["script"] is None
    assert fake.scripts == []
    assert "DeleteScript" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_sql_statement(monkeypatch):
    fake = FakeDlcClient(scripts=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="brand-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "sql_statement is required when creating" in exc.value.args[0]["msg"]


def test_create_script(monkeypatch):
    fake = FakeDlcClient(scripts=[])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="daily-sales",
        sql_statement=SQL_TEXT,
        description="Daily sales aggregation",
        database_name="analytics",
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["script_id"].startswith("script-new-")
    assert result["script"]["ScriptName"] == "daily-sales"
    assert result["script"]["SQLStatement"] == SQL_TEXT
    assert len(fake.scripts) == 1
    assert "CreateScript" in [c for c, unused in fake.calls]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(scripts=[])
    _make_module(monkeypatch, fake)
    module_args(
        _ansible_check_mode=True,
        state="present",
        name="daily-sales",
        sql_statement=SQL_TEXT,
        description="Daily sales aggregation",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["script_id"] is None
    assert result["script"]["SQLStatement"] == SQL_TEXT
    assert fake.scripts == []
    assert "CreateScript" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-script flows
# ---------------------------------------------------------------------------


def test_existing_script_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcClient(scripts=[_script()])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="daily-sales",
        sql_statement=SQL_TEXT,
        description="Daily sales aggregation",
        database_name="analytics",
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["script"]["ScriptId"] == "script-000001"
    assert result["script_id"] == "script-000001"


def test_drift_requires_allow_replace(monkeypatch):
    fake = FakeDlcClient(scripts=[_script()])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="daily-sales", description="Edited description")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "allow_replace=true" in payload["msg"]
    assert "ScriptDesc" in payload["changes"]


def test_replace_requires_sql_statement(monkeypatch):
    fake = FakeDlcClient(scripts=[_script()])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="daily-sales", description="Edited description", allow_replace=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "sql_statement is required when replacing" in exc.value.args[0]["msg"]


def test_allow_replace_recreates_script(monkeypatch):
    fake = FakeDlcClient(scripts=[_script()])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="daily-sales",
        sql_statement=SQL_TEXT,
        description="Edited description",
        database_name="analytics",
        allow_replace=True,
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["script_id"] != "script-000001"
    assert result["script"]["ScriptDesc"] == "Edited description"
    assert len(fake.scripts) == 1
    ops = [c for c, unused in fake.calls]
    assert "DeleteScript" in ops
    assert "CreateScript" in ops


def test_sql_content_drift_requires_allow_replace(monkeypatch):
    fake = FakeDlcClient(scripts=[_script()])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="daily-sales", sql_statement="SELECT 1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_replace=true" in exc.value.args[0]["msg"]


def test_multiple_matches_fail(monkeypatch):
    fake = FakeDlcClient(scripts=[_script(), _script(ScriptId="script-000002")])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="daily-sales")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DLC saved scripts matched" in exc.value.args[0]["msg"]


def test_non_utf8_sql_passthrough(monkeypatch):
    fake = FakeDlcClient(scripts=[_script(SQLStatement="not-base64")])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="daily-sales")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["script"]["SQLStatement"] == "not-base64"


# ---------------------------------------------------------------------------
# validation / failure paths
# ---------------------------------------------------------------------------


def test_name_too_long_fails(monkeypatch):
    fake = FakeDlcClient(scripts=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="x" * 256)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name must not exceed 255 characters" in exc.value.args[0]["msg"]


def test_description_too_long_fails(monkeypatch):
    fake = FakeDlcClient(scripts=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ghost", description="y" * 51)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "description must not exceed 50 characters" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeScripts(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", name="daily-sales")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
