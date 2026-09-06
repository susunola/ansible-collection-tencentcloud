"""Unit tests for the cdb_parameter_template write module (helpers + run_module).

Creates, updates and deletes reusable CDB parameter templates. find() lists
templates by TemplateIds or TemplateNames, then enriches the match with a
DescribeParamTemplateInfo call (multi-name matches fail). EngineVersion and
EngineType are immutable on an existing template; when updating without
engine_version the desired value falls back to the current one. Creation
requires engine_version (only reached when no current exists). Updates go
through ModifyParamTemplate (TemplateId + Name/Description/ParamList),
creation through CreateParamTemplate (which also sets EngineVersion /
EngineType / TemplateType); both carry param_list() (sorted, str-coerced
ParamInfo items).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdb_parameter_template as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


class _SdkError(Exception):
    """Stand-in for TencentCloudSDKException carrying a code/request id."""

    def __init__(self, code, message="", request_id=None):
        super(_SdkError, self).__init__(message)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def _template(**overrides):
    """API-shaped stored template; fresh copy per call."""
    item = {
        "template_id": 1001,
        "name": "production-mysql80",
        "description": "prod defaults",
        "engine_version": "8.0",
        "engine_type": "mysql",
        "template_type": 0,
        "parameters": {"max_connections": "2000"},
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "template_id": None,
        "name": "production-mysql80",
        "description": "prod defaults",
        "engine_version": "8.0",
        "engine_type": "mysql",
        "template_type": 0,
        "parameters": {"max_connections": "2000"},
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    params = _params(**extra)
    args = {k: v for k, v in params.items() if v is not None}
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


class FakeCdbClient(object):
    """In-memory CdbClient stand-in storing template dicts.

    DescribeParamTemplates honours TemplateIds / TemplateNames and returns
    slim TemplateId+Name items; DescribeParamTemplateInfo enriches one
    template into the full serialized shape (Items as plain dicts so the
    module's normalize() can read them); Create synthesises sequential ids;
    Modify rewrites Name/Description/ParamList by id; Delete removes by id.
    """

    def __init__(self, templates=None):
        self.templates = [dict(t) for t in (templates or [])]
        self.calls = []
        self._seq = 1000

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _next_id(self):
        self._seq += 1
        return self._seq

    def _list_items(self, request):
        if getattr(request, "TemplateIds", None):
            return [t for t in self.templates if t["template_id"] in request.TemplateIds]
        if getattr(request, "TemplateNames", None):
            return [t for t in self.templates if t["name"] in request.TemplateNames]
        return list(self.templates)

    def DescribeParamTemplates(self, request):
        self._record("DescribeParamTemplates", request)
        items = self._list_items(request)
        return SimpleNamespace(
            Items=[FakeResource({"TemplateId": t["template_id"], "Name": t["name"]}) for t in items],
            RequestId="req-fake",
        )

    def DescribeParamTemplateInfo(self, request):
        self._record("DescribeParamTemplateInfo", request)
        match = next((t for t in self.templates if t["template_id"] == request.TemplateId), None)
        if match is None:
            return FakeResource({})
        data = {
            "TemplateId": match["template_id"],
            "Name": match["name"],
            "Description": match["description"],
            "EngineVersion": match["engine_version"],
            "EngineType": match["engine_type"],
            "Items": [{"Name": k, "Value": v} for k, v in sorted(match["parameters"].items())],
        }
        return FakeResource(data)

    def CreateParamTemplate(self, request):
        self._record("CreateParamTemplate", request)
        template_id = self._next_id()
        self.templates.append({
            "template_id": template_id,
            "name": request.Name,
            "description": request.Description,
            "engine_version": request.EngineVersion,
            "engine_type": request.EngineType,
            "template_type": request.TemplateType,
            "parameters": {item.Name: item.Value for item in request.ParamList},
        })
        return SimpleNamespace(TemplateId=template_id, RequestId="req-fake")

    def ModifyParamTemplate(self, request):
        self._record("ModifyParamTemplate", request)
        for template in self.templates:
            if template["template_id"] == request.TemplateId:
                template["name"] = request.Name
                template["description"] = request.Description
                template["parameters"] = {item.Name: item.Value for item in request.ParamList}
        return SimpleNamespace(RequestId="req-fake")

    def DeleteParamTemplate(self, request):
        self._record("DeleteParamTemplate", request)
        self.templates = [t for t in self.templates if t["template_id"] != request.TemplateId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(CdbClient=object)),
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
            raise _SdkError("AuthFailure", "auth rejected", request_id="req-err")

        return boom


# ---------------------------------------------------------------------------
# helper tests
# ---------------------------------------------------------------------------


def test_param_list_sorts_and_coerces():
    items = mod.param_list(FakeModels(), {"max_connections": 2000, "auto_increment": 1})
    assert [i.Name for i in items] == ["auto_increment", "max_connections"]
    assert [i.Value for i in items] == ["1", "2000"]


def test_param_list_empty():
    assert mod.param_list(FakeModels(), {}) == []


def test_normalize_maps_fields():
    value = mod.normalize({
        "Name": "tpl",
        "Description": None,
        "EngineVersion": "8.0",
        "EngineType": "mysql",
        "Items": [{"Name": "max_connections", "Value": "2000"}],
    })
    assert value == {
        "Name": "tpl",
        "Description": "",
        "EngineVersion": "8.0",
        "EngineType": "mysql",
        "Parameters": {"max_connections": "2000"},
    }


def test_normalize_handles_missing_items():
    value = mod.normalize({"Name": "tpl", "Items": None})
    assert value["Parameters"] == {}
    assert value["Description"] == ""


def test_find_matches_by_template_id():
    fake = FakeCdbClient([_template()])
    module = FakeModule(_params(template_id=1001))
    value = mod.find(module, fake, FakeModels(), 1001, None)
    assert value["TemplateId"] == 1001
    assert value["Name"] == "production-mysql80"
    assert module.sdk_calls[0][1].TemplateIds == [1001]
    assert module.sdk_calls[0][0].__name__ == "DescribeParamTemplates"
    assert module.sdk_calls[1][0].__name__ == "DescribeParamTemplateInfo"
    assert module.sdk_calls[1][1].TemplateId == 1001


def test_find_matches_by_name():
    fake = FakeCdbClient([_template()])
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), None, "production-mysql80")
    assert value["TemplateId"] == 1001
    assert module.sdk_calls[0][1].TemplateNames == ["production-mysql80"]


def test_find_no_match_returns_none():
    fake = FakeCdbClient()
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), None, "ghost") is None
    assert len(module.sdk_calls) == 1


def test_find_multi_name_match_fails():
    fake = FakeCdbClient([_template(), _template(template_id=1002)])
    module = FakeModule(_params())
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), None, "production-mysql80")
    payload = exc.value.args[0]
    assert "Multiple CDB parameter templates have the requested name" in payload["msg"]
    assert payload["name"] == "production-mysql80"


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_requires_either_template_id_or_name(monkeypatch):
    fake = FakeCdbClient()
    _make_module(monkeypatch, fake)
    _run_args(template_id=None, name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "one of the following is required" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_present_requires_name(monkeypatch):
    fake = FakeCdbClient()
    _make_module(monkeypatch, fake)
    _run_args(template_id=1001, name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when state=present" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_create_requires_engine_version(monkeypatch):
    fake = FakeCdbClient()
    _make_module(monkeypatch, fake)
    _run_args(engine_version=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "engine_version is required when creating a CDB parameter template" in exc.value.args[0]["msg"]
    assert [c[0] for c in fake.calls] == ["DescribeParamTemplates"]


def test_absent_noop_when_missing(monkeypatch):
    fake = FakeCdbClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["parameter_template"] is None
    assert [c[0] for c in fake.calls] == ["DescribeParamTemplates"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakeCdbClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter_template"]["TemplateId"] == 1001
    assert result["diff"]["before"]["Name"] == "production-mysql80"
    assert result["diff"]["after"] is None
    assert [c[0] for c in fake.calls] == [
        "DescribeParamTemplates",
        "DescribeParamTemplateInfo",
    ]
    assert len(fake.templates) == 1


def test_absent_deletes_template(monkeypatch):
    fake = FakeCdbClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter_template"] is None
    assert [c[0] for c in fake.calls] == [
        "DescribeParamTemplates",
        "DescribeParamTemplateInfo",
        "DeleteParamTemplate",
    ]
    deleted = fake.calls[2][1]
    assert deleted.TemplateId == 1001
    assert fake.templates == []


def test_present_noop_when_template_matches(monkeypatch):
    fake = FakeCdbClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["parameter_template"]["TemplateId"] == 1001
    assert [c[0] for c in fake.calls] == [
        "DescribeParamTemplates",
        "DescribeParamTemplateInfo",
    ]


def test_present_renames_template_by_id(monkeypatch):
    fake = FakeCdbClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(template_id=1001, name="renamed")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter_template"]["Name"] == "renamed"
    assert [c[0] for c in fake.calls] == [
        "DescribeParamTemplates",
        "DescribeParamTemplateInfo",
        "ModifyParamTemplate",
        "DescribeParamTemplates",
        "DescribeParamTemplateInfo",
    ]
    updated = fake.calls[2][1]
    assert updated.TemplateId == 1001
    assert updated.Name == "renamed"
    assert updated.Description == "prod defaults"
    assert not hasattr(updated, "EngineVersion")
    assert [i.Value for i in updated.ParamList] == ["2000"]
    assert fake.templates[0]["name"] == "renamed"


def test_present_updates_parameters(monkeypatch):
    fake = FakeCdbClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(parameters={"max_connections": "5000"})
    result = run(mod.run_module)
    assert result["changed"] is True
    updated = fake.calls[2][1]
    assert updated.ParamList[0].Name == "max_connections"
    assert updated.ParamList[0].Value == "5000"
    assert fake.templates[0]["parameters"] == {"max_connections": "5000"}


def test_present_update_without_engine_version_keeps_current(monkeypatch):
    fake = FakeCdbClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(template_id=1001, engine_version=None, description="new desc")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter_template"]["Description"] == "new desc"
    assert fake.templates[0]["description"] == "new desc"


def test_present_engine_version_drift_fails(monkeypatch):
    fake = FakeCdbClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(engine_version="5.7")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed on an existing CDB parameter template" in payload["msg"]
    assert payload["immutable_changes"]["EngineVersion"] == {"before": "8.0", "after": "5.7"}
    assert payload["replacement_required"] is True
    assert [c[0] for c in fake.calls] == [
        "DescribeParamTemplates",
        "DescribeParamTemplateInfo",
    ]


def test_present_engine_type_drift_fails(monkeypatch):
    fake = FakeCdbClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(engine_type="postgresql")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed on an existing CDB parameter template" in payload["msg"]
    assert payload["immutable_changes"]["EngineType"]["after"] == "postgresql"


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeCdbClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(template_id=1001, name="renamed", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter_template"]["Name"] == "production-mysql80"
    assert result["diff"]["before"]["Name"] == "production-mysql80"
    assert result["diff"]["after"]["Name"] == "renamed"
    assert [c[0] for c in fake.calls] == [
        "DescribeParamTemplates",
        "DescribeParamTemplateInfo",
    ]
    assert fake.templates[0]["name"] == "production-mysql80"


def test_present_creates_template(monkeypatch):
    fake = FakeCdbClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter_template"]["TemplateId"] == 1001
    assert result["parameter_template"]["Name"] == "production-mysql80"
    assert [c[0] for c in fake.calls] == [
        "DescribeParamTemplates",
        "CreateParamTemplate",
        "DescribeParamTemplates",
        "DescribeParamTemplateInfo",
    ]
    created = fake.calls[1][1]
    assert created.Name == "production-mysql80"
    assert created.Description == "prod defaults"
    assert created.EngineVersion == "8.0"
    assert created.EngineType == "mysql"
    assert created.TemplateType == 0
    assert created.ParamList[0].Name == "max_connections"
    assert created.ParamList[0].Value == "2000"
    assert len(fake.templates) == 1
    assert fake.templates[0]["template_id"] == 1001


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeCdbClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter_template"] is None
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["Name"] == "production-mysql80"
    assert [c[0] for c in fake.calls] == ["DescribeParamTemplates"]
    assert fake.templates == []


def test_present_multi_name_match_fails(monkeypatch):
    fake = FakeCdbClient([_template(), _template(template_id=1002)])
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple CDB parameter templates have the requested name" in exc.value.args[0]["msg"]


def test_sdk_failure_reports_error_payload(monkeypatch):
    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "auth rejected"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeCdbClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.main)
    assert result["changed"] is False
    assert result["parameter_template"]["TemplateId"] == 1001
