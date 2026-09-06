"""Unit tests for the cdb_database write module (helpers + run_module).

Creates and deletes a database inside a TencentDB for MySQL instance. Lookup
walks DescribeDatabases pages (Offset/Limit 5000) matching DatabaseName and
returns the first hit. There is NO update path: an existing database whose
CharacterSet differs from the request fails as immutable (delete and
recreate instead); a matching one is a noop. absent deletes by name.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdb_database as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

_ORIG_LOAD = mod._load  # captured before any monkeypatching


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "instance_id": "cdb-abc123",
        "name": "orders",
        "character_set": "utf8mb4",
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    return module_args(**{k: v for k, v in _params(**extra).items() if v is not None})


def _load_real_or_fake():
    """Exercise the real lazy SDK import body when the SDK is installed.

    The coverage gate runs with the SDK present (see ci.yml "SDK contract
    tests"), so the real import executes and the ``_load`` body is covered;
    in SDK-less environments (``ansible-test units``) the import falls back
    to fake models so the same test file stays portable.
    """
    try:
        return _ORIG_LOAD()
    except ImportError:
        return FakeModels(), SimpleNamespace(CdbClient=object)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or {}

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


def _database(name, character_set="utf8mb4"):
    return {"DatabaseName": name, "CharacterSet": character_set}


class FakeCdbClient(object):
    """In-memory CdbClient stand-in storing per-instance database records.

    DescribeDatabases returns the stored records sliced by Offset (an
    optional page_size forces multiple pages for the paging tests);
    CreateDatabase appends a record from the request payload and
    DeleteDatabase removes it by DBName.
    """

    def __init__(self, databases=None, page_size=None):
        self.databases = [dict(d) for d in (databases or [])]
        self.page_size = page_size
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeDatabases(self, request):
        self._record("DescribeDatabases", request)
        page = self.databases
        if self.page_size:
            page = page[request.Offset:request.Offset + self.page_size]
        return SimpleNamespace(
            DatabaseList=[FakeResource(dict(d)) for d in page],
            TotalCount=len(self.databases),
        )

    def CreateDatabase(self, request):
        self._record("CreateDatabase", request)
        self.databases.append(_database(request.DBName, request.CharacterSetName))
        return SimpleNamespace()

    def DeleteDatabase(self, request):
        self._record("DeleteDatabase", request)
        self.databases = [d for d in self.databases if d["DatabaseName"] != request.DBName]
        return SimpleNamespace()


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", _load_real_or_fake)
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# request-builder tests
# ---------------------------------------------------------------------------


def test_describe_request_fields():
    request = mod.describe_request(FakeModels(), "cdb-abc123")
    assert type(request).__name__ == "DescribeDatabasesRequest"
    assert request.InstanceId == "cdb-abc123"
    assert request.Offset == 0
    assert request.Limit == 5000


def test_describe_request_respects_offset():
    request = mod.describe_request(FakeModels(), "cdb-abc123", offset=42)
    assert request.Offset == 42


def test_create_request_fields():
    request = mod.create_request(FakeModels(), _params(character_set="gbk"))
    assert type(request).__name__ == "CreateDatabaseRequest"
    assert request.InstanceId == "cdb-abc123"
    assert request.DBName == "orders"
    assert request.CharacterSetName == "gbk"


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params())
    assert type(request).__name__ == "DeleteDatabaseRequest"
    assert request.InstanceId == "cdb-abc123"
    assert request.DBName == "orders"


# ---------------------------------------------------------------------------
# find helper tests
# ---------------------------------------------------------------------------


def test_find_matches_on_first_page():
    fake = FakeCdbClient([_database("orders"), _database("reports")])
    found = mod.find(FakeModule(), fake, FakeModels(), _params())
    assert found == {"DatabaseName": "orders", "CharacterSet": "utf8mb4"}
    assert [name for name, request in fake.calls] == ["DescribeDatabases"]


def test_find_pages_until_match():
    fake = FakeCdbClient([_database("audit"), _database("orders", "gbk")], page_size=1)
    found = mod.find(FakeModule(), fake, FakeModels(), _params(character_set="gbk"))
    assert found["DatabaseName"] == "orders"
    assert found["CharacterSet"] == "gbk"
    offsets = [req.Offset for name, req in fake.calls if name == "DescribeDatabases"]
    assert offsets == [0, 1]  # page 1 had no match, advanced by returned count


def test_find_no_match_pages_to_exhaustion():
    fake = FakeCdbClient([_database("audit"), _database("reports")], page_size=1)
    assert mod.find(FakeModule(), fake, FakeModels(), _params(name="orders")) is None
    assert len(fake.calls) == 2  # both pages walked, then offset >= TotalCount


def test_find_empty_store_returns_none():
    fake = FakeCdbClient()
    assert mod.find(FakeModule(), fake, FakeModels(), _params()) is None
    assert len(fake.calls) == 1


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeCdbClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["database"] is None
    assert not any(name == "DeleteDatabase" for name, request in fake.calls)


def test_absent_deletes_database(monkeypatch):
    fake = FakeCdbClient([_database("orders")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["database"] is None
    delete = [req for name, req in fake.calls if name == "DeleteDatabase"][0]
    assert delete.InstanceId == "cdb-abc123"
    assert delete.DBName == "orders"
    assert fake.databases == []  # record removed


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCdbClient([_database("orders")])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["database"] == {"DatabaseName": "orders", "CharacterSet": "utf8mb4"}  # current kept
    assert result["diff"]["before"] == {"DatabaseName": "orders", "CharacterSet": "utf8mb4"}
    assert result["diff"]["after"] is None
    assert not any(name == "DeleteDatabase" for name, request in fake.calls)
    assert len(fake.databases) == 1  # remote untouched


def test_present_creates_database_and_refinds(monkeypatch):
    fake = FakeCdbClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["database"] == {"DatabaseName": "orders", "CharacterSet": "utf8mb4"}
    assert [name for name, request in fake.calls] == ["DescribeDatabases", "CreateDatabase", "DescribeDatabases"]
    create = [req for name, req in fake.calls if name == "CreateDatabase"][0]
    assert create.InstanceId == "cdb-abc123"
    assert create.DBName == "orders"
    assert create.CharacterSetName == "utf8mb4"


def test_present_create_uses_requested_character_set(monkeypatch):
    fake = FakeCdbClient()
    _make_module(monkeypatch, fake)
    _run_args(character_set="gbk")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["database"]["CharacterSet"] == "gbk"
    create = [req for name, req in fake.calls if name == "CreateDatabase"][0]
    assert create.CharacterSetName == "gbk"


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeCdbClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["database"] is None
    assert result["diff"]["before"] is None
    assert result["diff"]["after"] == {"DatabaseName": "orders", "CharacterSet": "utf8mb4"}
    assert not any(name == "CreateDatabase" for name, request in fake.calls)


def test_present_unchanged_is_noop(monkeypatch):
    fake = FakeCdbClient([_database("orders", "utf8mb4")])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["database"] == {"DatabaseName": "orders", "CharacterSet": "utf8mb4"}
    assert not any(name == "CreateDatabase" for name, request in fake.calls)


def test_present_character_set_drift_fails_immutable(monkeypatch):
    fake = FakeCdbClient([_database("orders", "utf8")])
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Immutable fields cannot be changed on an existing CDB database"
    assert payload["immutable_changes"] == {"CharacterSet": {"before": "utf8", "after": "utf8mb4"}}
    assert payload["replacement_required"] is True
    assert not any(name == "CreateDatabase" for name, request in fake.calls)


def test_present_character_set_drift_fails_even_in_check_mode(monkeypatch):
    fake = FakeCdbClient([_database("orders", "utf8")])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "Immutable fields cannot be changed on an existing CDB database"


def test_invalid_character_set_choice_fails_validation(monkeypatch):
    _make_module(monkeypatch, FakeCdbClient())
    _run_args(character_set="utf16")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "character_set" in exc.value.args[0]["msg"]


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(CdbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: _BoomClient())
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeCdbClient([_database("orders", "utf8mb4")])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.main)
    assert result["changed"] is False
    assert result["database"]["DatabaseName"] == "orders"
