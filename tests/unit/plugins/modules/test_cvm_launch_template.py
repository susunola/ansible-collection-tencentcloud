"""Unit tests for the cvm_launch_template write module (helpers + run_module).

Creates, deletes and selects the default version of CVM launch
templates. A template is looked up through DescribeLaunchTemplates:
LaunchTemplateIds when ``template_id`` is given, else a
launch-template-name Filter. The name is immutable on an existing
template — renaming requires ``force_replace=true`` which deletes and
recreates it. Initial data is creation-only. ``default_version`` drift
becomes ModifyLaunchTemplateDefaultVersion (also right after a fresh
create when the requested default is not version 1).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cvm_launch_template as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeRequest,
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


INITIAL_DATA = {
    "Placement": {"Zone": "ap-guangzhou-3"},
    "ImageId": "img-xxxxxx",
    "InstanceType": "S5.MEDIUM4",
    "SecurityGroupIds": ["sg-xxxxxx"],
}


def _template(**overrides):
    """API-shaped launch-template dict; fresh copy per call."""
    item = {
        "LaunchTemplateId": "lt-1001",
        "LaunchTemplateName": "web-production",
        "DefaultVersionNumber": 1,
        "LaunchTemplateVersionDescription": "initial version",
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "template_id": None,
        "name": "web-production",
        "initial_data": None,
        "version_description": "initial version",
        "default_version": None,
        "force_replace": False,
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


class _DeserializableRequest(FakeRequest):
    """Request whose _deserialize captures the raw payload for the fake."""

    def _deserialize(self, data):
        self._payload = dict(data or {})


class FakeCvmModels(FakeModels):
    """FakeModels whose CreateLaunchTemplateRequest can _deserialize JSON."""

    def __getattr__(self, name):
        if name == "CreateLaunchTemplateRequest":
            return _DeserializableRequest
        return type(name, (FakeRequest,), {})


class FakeCvmClient(object):
    """In-memory CvmClient stand-in storing launch-template dicts.

    DescribeLaunchTemplates applies the module's server-side filters
    (LaunchTemplateIds first, else the launch-template-name Filter);
    CreateLaunchTemplate synthesizes sequential LaunchTemplateIds with
    DefaultVersionNumber 1; ModifyLaunchTemplateDefaultVersion rewrites
    the version; DeleteLaunchTemplate removes by id.
    """

    def __init__(self, templates=None):
        self.templates = [dict(t) for t in (templates or [])]
        self.calls = []
        self._seq = 2001

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeLaunchTemplates(self, request):
        self._record("DescribeLaunchTemplates", request)
        ids = getattr(request, "LaunchTemplateIds", None) or []
        filters = getattr(request, "Filters", None) or []
        values = self.templates
        if ids:
            values = [t for t in values if t["LaunchTemplateId"] in ids]
        elif filters:
            for item in filters:
                if getattr(item, "Name", None) == "launch-template-name":
                    names = getattr(item, "Values", None) or []
                    values = [t for t in values if t["LaunchTemplateName"] in names]
        return SimpleNamespace(
            LaunchTemplateSet=[FakeResource(dict(t)) for t in values],
            RequestId="req-fake",
        )

    def CreateLaunchTemplate(self, request):
        self._record("CreateLaunchTemplate", request)
        stored = {
            "LaunchTemplateId": "lt-%04d" % self._seq,
            "LaunchTemplateName": request.LaunchTemplateName,
            "LaunchTemplateVersionDescription": getattr(request, "LaunchTemplateVersionDescription", ""),
            "DefaultVersionNumber": 1,
        }
        for key, value in (getattr(request, "_payload", None) or {}).items():
            if key not in stored:
                stored[key] = value
        self._seq += 1
        self.templates.append(stored)
        return SimpleNamespace(LaunchTemplateId=stored["LaunchTemplateId"], RequestId="req-fake")

    def ModifyLaunchTemplateDefaultVersion(self, request):
        self._record("ModifyLaunchTemplateDefaultVersion", request)
        for stored in self.templates:
            if stored["LaunchTemplateId"] == request.LaunchTemplateId:
                stored["DefaultVersionNumber"] = request.DefaultVersion
        return SimpleNamespace(RequestId="req-fake")

    def DeleteLaunchTemplate(self, request):
        self._record("DeleteLaunchTemplate", request)
        self.templates = [t for t in self.templates if t["LaunchTemplateId"] != request.LaunchTemplateId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeCvmModels(), SimpleNamespace(CvmClient=object)),
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
# request-builder / helper tests
# ---------------------------------------------------------------------------


def test_describe_request_filters_by_template_id():
    request = mod.describe_request(FakeCvmModels(), _params(template_id="lt-1001", name=None))
    assert request.LaunchTemplateIds == ["lt-1001"]
    assert not hasattr(request, "Filters")
    assert request.Offset == 0
    assert request.Limit == 100


def test_describe_request_filters_by_name():
    request = mod.describe_request(FakeCvmModels(), _params(template_id=None, name="web-production"))
    assert not hasattr(request, "LaunchTemplateIds")
    assert len(request.Filters) == 1
    assert request.Filters[0].Name == "launch-template-name"
    assert request.Filters[0].Values == ["web-production"]


def test_describe_request_lists_all_when_no_identity():
    request = mod.describe_request(FakeCvmModels(), _params(template_id=None, name=None))
    assert not hasattr(request, "LaunchTemplateIds")
    assert not hasattr(request, "Filters")


def test_create_request_deserializes_payload():
    request = mod.create_request(FakeCvmModels(), _params(initial_data=INITIAL_DATA))
    assert request._payload == INITIAL_DATA
    assert request.LaunchTemplateName == "web-production"
    assert request.LaunchTemplateVersionDescription == "initial version"


def test_default_request_carries_id_and_version():
    request = mod.default_request(FakeCvmModels(), "lt-1001", 2)
    assert request.LaunchTemplateId == "lt-1001"
    assert request.DefaultVersion == 2


def test_delete_request_carries_id():
    request = mod.delete_request(FakeCvmModels(), "lt-1001")
    assert request.LaunchTemplateId == "lt-1001"


def test_find_by_template_id(monkeypatch):
    fake = FakeCvmClient([_template(), _template(LaunchTemplateId="lt-1002", LaunchTemplateName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(template_id="lt-1002", name=None))
    value = mod.find(module, fake, FakeCvmModels(), module.params)
    assert value["LaunchTemplateId"] == "lt-1002"
    assert value["LaunchTemplateName"] == "other"


def test_find_by_name(monkeypatch):
    fake = FakeCvmClient([_template(), _template(LaunchTemplateId="lt-1002", LaunchTemplateName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(template_id=None, name="web-production"))
    value = mod.find(module, fake, FakeCvmModels(), module.params)
    assert value["LaunchTemplateId"] == "lt-1001"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeCvmClient([_template(LaunchTemplateName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(template_id=None, name="missing"))
    assert mod.find(module, fake, FakeCvmModels(), module.params) is None


def test_find_multiple_name_matches_fail(monkeypatch):
    fake = FakeCvmClient([_template(), _template(LaunchTemplateId="lt-1002")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(template_id=None, name="web-production"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeCvmModels(), module.params)
    assert "Multiple CVM launch templates matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_present_requires_name(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(state="present", template_id="lt-1001", name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "name is required when state=present" in payload["msg"]


def test_default_version_must_be_positive(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(template_id="lt-1001", default_version=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "default_version must be positive" in payload["msg"]


def test_absent_noop_when_missing(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", template_id="lt-ghost", name=None)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["launch_template"] is None
    assert [c[0] for c in fake.calls] == ["DescribeLaunchTemplates"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakeCvmClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", template_id="lt-1001", name=None, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["launch_template"]["LaunchTemplateId"] == "lt-1001"
    assert [c[0] for c in fake.calls] == ["DescribeLaunchTemplates"]


def test_absent_deletes_template(monkeypatch):
    fake = FakeCvmClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", template_id="lt-1001", name=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["launch_template"] is None
    assert [c[0] for c in fake.calls] == ["DescribeLaunchTemplates", "DeleteLaunchTemplate"]
    assert fake.calls[1][1].LaunchTemplateId == "lt-1001"
    assert fake.templates == []


def test_present_noop_matching_template(monkeypatch):
    fake = FakeCvmClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(template_id="lt-1001", name="web-production", initial_data=None)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["launch_template"]["LaunchTemplateId"] == "lt-1001"
    assert [c[0] for c in fake.calls] == ["DescribeLaunchTemplates"]


def test_present_noop_with_matching_default_version(monkeypatch):
    fake = FakeCvmClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(template_id="lt-1001", name="web-production", initial_data=None, default_version=1)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["launch_template"]["DefaultVersionNumber"] == 1


def test_present_immutable_name_fails_without_force(monkeypatch):
    fake = FakeCvmClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(template_id="lt-1001", name="renamed", initial_data=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "name is immutable" in payload["msg"]
    assert payload["current_name"] == "web-production"
    assert payload["desired_name"] == "renamed"
    assert [c[0] for c in fake.calls] == ["DescribeLaunchTemplates"]


def test_present_create_requires_initial_data(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(template_id="lt-ghost", name="web-production", initial_data=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "initial_data is required when creating or replacing" in payload["msg"]
    assert [c[0] for c in fake.calls] == ["DescribeLaunchTemplates"]


def test_present_check_mode_create_reports_target(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(template_id=None, name="web-production", initial_data=INITIAL_DATA, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["launch_template"] is None
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["LaunchTemplateName"] == "web-production"
    assert result["diff"]["after"]["DefaultVersionNumber"] == 1
    assert [c[0] for c in fake.calls] == ["DescribeLaunchTemplates"]


def test_present_create_creates_and_confirms(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(template_id=None, name="web-production", initial_data=INITIAL_DATA)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["launch_template"]["LaunchTemplateId"] == "lt-2001"
    assert result["launch_template"]["LaunchTemplateName"] == "web-production"
    assert [c[0] for c in fake.calls] == ["DescribeLaunchTemplates", "CreateLaunchTemplate", "DescribeLaunchTemplates"]
    created = fake.calls[1][1]
    assert created.LaunchTemplateName == "web-production"
    assert created.LaunchTemplateVersionDescription == "initial version"
    assert created._payload["ImageId"] == "img-xxxxxx"
    assert fake.templates[0]["DefaultVersionNumber"] == 1


def test_present_default_version_drift_triggers_update(monkeypatch):
    fake = FakeCvmClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(template_id="lt-1001", name="web-production", initial_data=None, default_version=2)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["launch_template"]["DefaultVersionNumber"] == 2
    assert [c[0] for c in fake.calls] == [
        "DescribeLaunchTemplates",
        "ModifyLaunchTemplateDefaultVersion",
        "DescribeLaunchTemplates",
    ]
    assert fake.calls[1][1].LaunchTemplateId == "lt-1001"
    assert fake.calls[1][1].DefaultVersion == 2


def test_present_check_mode_default_drift_is_dry_run(monkeypatch):
    fake = FakeCvmClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(template_id="lt-1001", name="web-production", initial_data=None, default_version=2, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["launch_template"]["DefaultVersionNumber"] == 1
    assert result["diff"]["after"]["DefaultVersionNumber"] == 2
    assert [c[0] for c in fake.calls] == ["DescribeLaunchTemplates"]


def test_present_create_then_set_default_version(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(template_id=None, name="web-production", initial_data=INITIAL_DATA, default_version=3)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["launch_template"]["DefaultVersionNumber"] == 3
    assert [c[0] for c in fake.calls] == [
        "DescribeLaunchTemplates",
        "CreateLaunchTemplate",
        "DescribeLaunchTemplates",
        "ModifyLaunchTemplateDefaultVersion",
        "DescribeLaunchTemplates",
    ]
    assert fake.calls[3][1].LaunchTemplateId == "lt-2001"
    assert fake.calls[3][1].DefaultVersion == 3


def test_present_replace_with_force_recreates(monkeypatch):
    fake = FakeCvmClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(template_id="lt-1001", name="renamed", initial_data=INITIAL_DATA, force_replace=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["launch_template"]["LaunchTemplateId"] == "lt-2001"
    assert result["launch_template"]["LaunchTemplateName"] == "renamed"
    assert [c[0] for c in fake.calls] == [
        "DescribeLaunchTemplates",
        "DeleteLaunchTemplate",
        "CreateLaunchTemplate",
        "DescribeLaunchTemplates",
    ]
    assert fake.calls[1][1].LaunchTemplateId == "lt-1001"
    assert fake.templates[0]["LaunchTemplateId"] == "lt-2001"


def test_present_check_mode_replace_reports_new_target(monkeypatch):
    fake = FakeCvmClient([_template()])
    _make_module(monkeypatch, fake)
    _run_args(template_id="lt-1001", name="renamed", initial_data=INITIAL_DATA, force_replace=True, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["launch_template"]["LaunchTemplateName"] == "web-production"
    assert result["diff"]["after"]["LaunchTemplateName"] == "renamed"
    assert [c[0] for c in fake.calls] == ["DescribeLaunchTemplates"]


def test_sdk_failure_reports_error_payload(monkeypatch):
    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", template_id="lt-1001", name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "auth rejected"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"
