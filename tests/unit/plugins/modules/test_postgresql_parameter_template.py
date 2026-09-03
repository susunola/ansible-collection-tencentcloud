"""Unit tests for the postgresql_parameter_template write module (helpers + run_module).

Creates, updates and deletes reusable TencentDB for PostgreSQL parameter
templates. Lookup pages through DescribeParameterTemplates (Limit 100)
matching by ``template_id`` or ``name`` — duplicate names fail — then
fetches the full attributes (including ParamInfoSet) for the winner.
``DBMajorVersion`` and ``DBEngine`` are immutable after creation
(require_immutable_unchanged); the module only tracks the parameters the
playbook declares, so a noop requires those to match and no
``reset_parameters``. Creation is two API steps: CreateParameterTemplate
then a ModifyParameterTemplate that applies the declared parameter
entries and deletions.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import postgresql_parameter_template as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _template(**overrides):
    """API-shaped template dict; fresh copy per call."""
    item = {
        "TemplateId": "tpl-1",
        "TemplateName": "prod-pg15",
        "TemplateDescription": "",
        "DBMajorVersion": "15",
        "DBEngine": "postgresql",
        "ParamInfoSet": [{"Name": "max_connections", "CurrentValue": "1000"}],
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "template_id": None,
        "name": None,
        "description": "",
        "database_major_version": None,
        "database_engine": "postgresql",
        "parameters": {},
        "reset_parameters": [],
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    params = _params(**extra)
    args = {
        "state": params["state"],
        "description": params["description"],
        "database_engine": params["database_engine"],
        "parameters": params["parameters"],
        "reset_parameters": params["reset_parameters"],
    }
    for key in ("template_id", "name", "database_major_version"):
        if params[key] is not None:
            args[key] = params[key]
    for key, value in extra.items():
        if key.startswith("_"):
            args[key] = value
    return module_args(**args)


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


class FakePostgresClient(object):
    """In-memory PostgresClient stand-in storing template dicts.

    DescribeParameterTemplates paginates with the request's
    Offset/Limit; items carry TemplateId/TemplateName for the module's
    id/name matching. DescribeParameterTemplateAttributes returns the
    full stored dict (including ParamInfoSet) as a :class:`FakeResource`
    so the module's ``_serialize`` read works. Modify applies each
    ParamEntry (by name) and removes the DeleteParam names.
    """

    def __init__(self, templates=None):
        self.templates = [dict(t) for t in (templates or [])]
        self.calls = []
        self._next_id = 100

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _by_id(self, template_id):
        for stored in self.templates:
            if stored.get("TemplateId") == template_id:
                return stored
        return None

    def DescribeParameterTemplates(self, request):
        self._record("DescribeParameterTemplates", request)
        offset = getattr(request, "Offset", 0)
        limit = getattr(request, "Limit", 100)
        page = self.templates[offset:offset + limit]
        return SimpleNamespace(
            ParameterTemplateSet=[FakeResource(dict(t)) for t in page],
            TotalCount=len(self.templates),
            RequestId="req-fake",
        )

    def DescribeParameterTemplateAttributes(self, request):
        self._record("DescribeParameterTemplateAttributes", request)
        stored = self._by_id(request.TemplateId)
        return FakeResource(dict(stored) if stored else {"TemplateId": request.TemplateId})

    def CreateParameterTemplate(self, request):
        self._record("CreateParameterTemplate", request)
        template_id = "tpl-new%d" % self._next_id
        self._next_id += 1
        self.templates.append(
            {
                "TemplateId": template_id,
                "TemplateName": request.TemplateName,
                "TemplateDescription": request.TemplateDescription,
                "DBMajorVersion": request.DBMajorVersion,
                "DBEngine": request.DBEngine,
                "ParamInfoSet": [],
            }
        )
        return SimpleNamespace(TemplateId=template_id, RequestId="req-fake")

    def ModifyParameterTemplate(self, request):
        self._record("ModifyParameterTemplate", request)
        stored = self._by_id(request.TemplateId)
        if not stored:
            return SimpleNamespace(RequestId="req-fake")
        stored["TemplateName"] = request.TemplateName
        stored["TemplateDescription"] = request.TemplateDescription
        entries = {e.Name: e.ExpectedValue for e in (request.ModifyParamEntrySet or [])}
        kept = {}
        for entry in stored.get("ParamInfoSet") or []:
            kept[entry["Name"]] = entry["CurrentValue"]
        kept.update(entries)
        for name in request.DeleteParamSet or []:
            kept.pop(name, None)
        stored["ParamInfoSet"] = [{"Name": n, "CurrentValue": v} for n, v in sorted(kept.items())]
        return SimpleNamespace(RequestId="req-fake")

    def DeleteParameterTemplate(self, request):
        self._record("DeleteParameterTemplate", request)
        self.templates = [t for t in self.templates if t.get("TemplateId") != request.TemplateId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(PostgresClient=object)),
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
# entries / normalize tests
# ---------------------------------------------------------------------------


def test_entries_sorted_and_string_cast():
    entries = mod.entries(FakeModels(), {"work_mem": 4096, "max_connections": "1000"})
    assert [(e.Name, e.ExpectedValue) for e in entries] == [
        ("max_connections", "1000"),
        ("work_mem", "4096"),
    ]
    assert isinstance(entries[0].Name, str) and isinstance(entries[0].ExpectedValue, str)


def test_normalize_filters_parameter_names():
    value = mod.normalize(
        {
            "TemplateName": "prod-pg15",
            "TemplateDescription": None,
            "DBMajorVersion": "15",
            "DBEngine": "postgresql",
            "ParamInfoSet": [
                {"Name": "max_connections", "CurrentValue": "1000"},
                {"Name": "work_mem", "CurrentValue": "4096"},
            ],
        },
        parameter_names=("max_connections",),
    )
    assert value == {
        "TemplateName": "prod-pg15",
        "TemplateDescription": "",
        "DBMajorVersion": "15",
        "DBEngine": "postgresql",
        "Parameters": {"max_connections": "1000"},
    }


def test_normalize_missing_param_info_set():
    value = mod.normalize({"TemplateName": "x"}, parameter_names=("max_connections",))
    assert value["Parameters"] == {}


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_matches_by_template_id(monkeypatch):
    fake = FakePostgresClient([_template(), _template(TemplateId="tpl-2", TemplateName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find(module, fake, FakeModels(), "tpl-2", None)
    assert value["TemplateId"] == "tpl-2"
    assert value["TemplateName"] == "other"
    assert [c[0] for c in fake.calls] == [
        "DescribeParameterTemplates",
        "DescribeParameterTemplateAttributes",
    ]


def test_find_matches_by_name(monkeypatch):
    fake = FakePostgresClient([_template()])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find(module, fake, FakeModels(), None, "prod-pg15")
    assert value["TemplateId"] == "tpl-1"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakePostgresClient([_template()])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    assert mod.find(module, fake, FakeModels(), None, "ghost") is None
    assert not any(c[0] == "DescribeParameterTemplateAttributes" for c in fake.calls)


def test_find_multiple_name_matches_fails(monkeypatch):
    fake = FakePostgresClient([_template(), _template(TemplateId="tpl-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule()
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), None, "prod-pg15")
    payload = exc.value.args[0]
    assert "Multiple PostgreSQL parameter templates have the requested name" in payload["msg"]
    assert payload["name"] == "prod-pg15"


def test_find_paginates_across_pages(monkeypatch):
    templates = [_template(TemplateId="tpl-%03d" % i, TemplateName="t-%03d" % i) for i in range(120)]
    templates.append(_template())
    fake = FakePostgresClient(templates)
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find(module, fake, FakeModels(), None, "prod-pg15")
    assert value["TemplateId"] == "tpl-1"
    assert [c[0] for c in fake.calls].count("DescribeParameterTemplates") == 2  # page 0 + page 100


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_requires_template_id_or_name():
    module_args(state="present", database_major_version="15")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    msg = exc.value.args[0]["msg"]
    assert "template_id" in msg and "name" in msg


def test_name_required_when_present():
    module_args(state="present", template_id="tpl-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when state=present" in exc.value.args[0]["msg"]


def test_present_creates_and_applies_parameters(monkeypatch):
    fake = FakePostgresClient()
    _make_module(monkeypatch, fake)
    _run_args(name="prod-pg15", database_major_version="15", parameters={"max_connections": "1000"})
    result = run(mod.run_module)
    assert result["changed"] is True
    template = result["parameter_template"]
    assert template["TemplateId"] == "tpl-new100"
    assert template["TemplateName"] == "prod-pg15"
    assert template["DBMajorVersion"] == "15"
    calls = [c[0] for c in fake.calls]
    assert calls.count("DescribeParameterTemplates") == 3  # find + post-create + post-modify
    assert calls.count("DescribeParameterTemplateAttributes") == 2
    assert calls.count("CreateParameterTemplate") == 1
    assert calls.count("ModifyParameterTemplate") == 1
    create = [c for c in fake.calls if c[0] == "CreateParameterTemplate"][0][1]
    assert create.TemplateName == "prod-pg15"
    assert create.DBMajorVersion == "15"
    assert create.DBEngine == "postgresql"
    modify = [c for c in fake.calls if c[0] == "ModifyParameterTemplate"][0][1]
    assert [(e.Name, e.ExpectedValue) for e in modify.ModifyParamEntrySet] == [("max_connections", "1000")]
    assert modify.TemplateId == "tpl-new100"


def test_present_create_requires_database_major_version(monkeypatch):
    fake = FakePostgresClient()
    _make_module(monkeypatch, fake)
    _run_args(name="prod-pg15")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "database_major_version is required when creating a PostgreSQL parameter template" in exc.value.args[0]["msg"]
    assert not any(c[0] == "CreateParameterTemplate" for c in fake.calls)


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakePostgresClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, name="prod-pg15", database_major_version="15")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter_template"] is None  # nothing was created to report
    assert not any(c[0] in ("CreateParameterTemplate", "ModifyParameterTemplate") for c in fake.calls)
    assert fake.templates == []


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakePostgresClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(name="prod-pg15", database_major_version="15", parameters={"max_connections": "1000"})
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["parameter_template"]["TemplateId"] == "tpl-1"
    assert not any(c[0] in ("CreateParameterTemplate", "ModifyParameterTemplate") for c in fake.calls)


def test_present_parameter_drift_triggers_modify(monkeypatch):
    fake = FakePostgresClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(name="prod-pg15", database_major_version="15", parameters={"max_connections": "2000"})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter_template"]["ParamInfoSet"] == [{"Name": "max_connections", "CurrentValue": "2000"}]
    modify = [c for c in fake.calls if c[0] == "ModifyParameterTemplate"][0][1]
    assert [(e.Name, e.ExpectedValue) for e in modify.ModifyParamEntrySet] == [("max_connections", "2000")]
    assert not any(c[0] == "CreateParameterTemplate" for c in fake.calls)


def test_present_description_drift_triggers_modify(monkeypatch):
    fake = FakePostgresClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(name="prod-pg15", database_major_version="15", parameters={"max_connections": "1000"}, description="new desc")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter_template"]["TemplateDescription"] == "new desc"
    modify = [c for c in fake.calls if c[0] == "ModifyParameterTemplate"][0][1]
    assert modify.TemplateDescription == "new desc"


def test_present_reset_parameters_triggers_delete_set(monkeypatch):
    fake = FakePostgresClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(name="prod-pg15", database_major_version="15", parameters={"max_connections": "1000"}, reset_parameters=["work_mem"])
    result = run(mod.run_module)
    assert result["changed"] is True
    modify = [c for c in fake.calls if c[0] == "ModifyParameterTemplate"][0][1]
    assert modify.DeleteParamSet == ["work_mem"]
    # work_mem was never stored; max_connections stays
    assert result["parameter_template"]["ParamInfoSet"] == [{"Name": "max_connections", "CurrentValue": "1000"}]


def test_present_database_major_version_immutable_fails(monkeypatch):
    fake = FakePostgresClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(name="prod-pg15", database_major_version="16", parameters={"max_connections": "1000"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["replacement_required"] is True
    assert payload["immutable_changes"] == {"DBMajorVersion": {"before": "15", "after": "16"}}
    assert not any(c[0] == "ModifyParameterTemplate" for c in fake.calls)


def test_present_database_engine_immutable_fails(monkeypatch):
    fake = FakePostgresClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(name="prod-pg15", database_major_version="15", database_engine="mariadb", parameters={"max_connections": "1000"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["immutable_changes"] == {"DBEngine": {"before": "postgresql", "after": "mariadb"}}


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakePostgresClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, name="prod-pg15", database_major_version="15", parameters={"max_connections": "2000"})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter_template"]["ParamInfoSet"] == [{"Name": "max_connections", "CurrentValue": "1000"}]  # pre-change
    assert not any(c[0] == "ModifyParameterTemplate" for c in fake.calls)


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakePostgresClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["parameter_template"] is None
    assert not any(c[0] == "DeleteParameterTemplate" for c in fake.calls)


def test_absent_deletes_template(monkeypatch):
    fake = FakePostgresClient([_template(), _template(TemplateId="tpl-2", TemplateName="other")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", template_id="tpl-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter_template"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteParameterTemplate"][0][1]
    assert delete.TemplateId == "tpl-1"
    assert [t["TemplateId"] for t in fake.templates] == ["tpl-2"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakePostgresClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, state="absent", template_id="tpl-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter_template"]["TemplateId"] == "tpl-1"  # pre-delete reported
    assert not any(c[0] == "DeleteParameterTemplate" for c in fake.calls)
    assert len(fake.templates) == 1


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(PostgresClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args(name="prod-pg15", database_major_version="15")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"
