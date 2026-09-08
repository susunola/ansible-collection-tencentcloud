"""Unit tests for the tsf_application write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TSF client whose
write operations mutate the application store, so post-write describe
refetches converge immediately.

The TSF create request uses ``hasattr(request, key)`` gating, so this test
uses lenient fake SDK models whose instances return ``None`` for any unset
attribute, making ``hasattr`` true for every SDK field the module manages.

Scenario matrix:

* absent on a missing application (idempotent) / check-mode dry run / real
  delete
* creation when missing (missing type parameters, check mode, real create)
* no-op when nothing drifts
* drift updates (description/remark) and immutable-drift failure
* the multiple-match guard
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tsf_application as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeResource,
    module_args,
    run,
)

APPLICATION = {
    "ApplicationId": "application-8b0a1c2d",
    "ApplicationName": "orders",
    "ApplicationType": "C",
    "MicroserviceType": "N",
    "ApplicationDesc": "Order service",
    "FrameworkType": "SpringCloud",
    "ApplicationRuntimeType": "C",
    "ProgramLanguage": "Java",
    "ApplicationRemarkName": "orders",
}


def _application(**overrides):
    item = copy.deepcopy(APPLICATION)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "orders"}
    params.update(overrides)
    return module_args(**params)


class LenientRequest(object):
    """SDK model stand-in where any unset attribute reads as ``None``."""

    def _deserialize(self, data):
        if data:
            self.__dict__.update(data)
        return self

    def from_json_string(self, value):
        import json

        if value:
            self.__dict__.update(json.loads(value))
        return self

    def __getattr__(self, name):
        return None


class LenientModels(object):
    def __getattr__(self, name):
        return type(name, (LenientRequest,), {})


class FakeTsfClient(object):
    """In-memory TSF client mutating an application store."""

    def __init__(self, applications=None):
        self.applications = [copy.deepcopy(t) for t in (applications or [])]
        self.calls = []
        self._next = 0

    def _find(self, application_id):
        for item in self.applications:
            if item.get("ApplicationId") == application_id:
                return item
        return None

    def _copy(self, request):
        return {k: v for k, v in dict(getattr(request, "__dict__", {})).items() if not k.startswith("_")}

    def DescribeApplication(self, request):
        self.calls.append("DescribeApplication")
        item = self._find(getattr(request, "ApplicationId", None))
        result = FakeResource(dict(item)) if item is not None else None
        return SimpleNamespace(Result=result, RequestId="req-fake")

    def DescribeApplications(self, request):
        self.calls.append("DescribeApplications")
        result = SimpleNamespace(Content=[FakeResource(t) for t in self.applications], TotalCount=len(self.applications))
        return SimpleNamespace(Result=result, RequestId="req-fake")

    def CreateApplication(self, request):
        self.calls.append("CreateApplication")
        self._next += 1
        item = self._copy(request)
        item["ApplicationId"] = "application-new-%03d" % self._next
        self.applications.append(item)
        return SimpleNamespace(Result=item["ApplicationId"], RequestId="req-fake")

    def ModifyApplication(self, request):
        self.calls.append("ModifyApplication")
        item = self._find(getattr(request, "ApplicationId", None))
        if item is not None:
            for key in ("ApplicationName", "ApplicationDesc", "ApplicationRemarkName", "MicroserviceType", "FrameworkType"):
                value = getattr(request, key, None)
                if value is not None:
                    item[key] = value
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def DeleteApplication(self, request):
        self.calls.append("DeleteApplication")
        self.applications = [t for t in self.applications if t.get("ApplicationId") != getattr(request, "ApplicationId", None)]
        return SimpleNamespace(Result=True, RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (LenientModels(), SimpleNamespace(TsfClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_application_is_idempotent(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["application"] is None
    assert list(fake.calls) == ["DescribeApplications"]


def test_absent_deletes_application(monkeypatch):
    fake = FakeTsfClient(applications=[_application()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.applications == []
    ops = list(fake.calls)
    assert "DeleteApplication" in ops


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfClient(applications=[_application()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.applications) == 1
    assert "DeleteApplication" not in fake.calls


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_type_parameters(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _base(name="brand-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "application_type and microservice_type are required" in exc.value.args[0]["msg"]


def test_create_application(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _base(
        name="brand-new",
        application_type="C",
        microservice_type="N",
        description="created",
        framework_type="SpringCloud",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["application"]["ApplicationId"].startswith("application-new-")
    assert result["application"]["ApplicationName"] == "brand-new"
    assert result["application"]["MicroserviceType"] == "N"
    assert len(fake.applications) == 1
    ops = list(fake.calls)
    assert "CreateApplication" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        name="brand-new",
        application_type="C",
        microservice_type="N",
        framework_type="SpringCloud",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["application"]["ApplicationName"] == "brand-new"
    assert fake.applications == []
    assert "CreateApplication" not in fake.calls


# ---------------------------------------------------------------------------
# existing-application flows
# ---------------------------------------------------------------------------


def test_existing_application_no_drift_is_idempotent(monkeypatch):
    fake = FakeTsfClient(applications=[_application()])
    _make_module(monkeypatch, fake)
    _base(name="orders")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["application"]["ApplicationId"] == "application-8b0a1c2d"
    ops = list(fake.calls)
    assert "ModifyApplication" not in ops


def test_update_application_description(monkeypatch):
    fake = FakeTsfClient(applications=[_application()])
    _make_module(monkeypatch, fake)
    _base(description="renamed service", remark_name="orders-v2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["application"]["ApplicationDesc"] == "renamed service"
    assert result["application"]["ApplicationRemarkName"] == "orders-v2"
    ops = list(fake.calls)
    assert "ModifyApplication" in ops


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfClient(applications=[_application()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, description="renamed service")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["application"]["ApplicationDesc"] == "renamed service"
    assert "ModifyApplication" not in fake.calls


def test_immutable_drift_fails(monkeypatch):
    fake = FakeTsfClient(applications=[_application()])
    _make_module(monkeypatch, fake)
    _base(application_type="V", microservice_type="N")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert "ApplicationType" in payload["immutable_changes"]


def test_multiple_matches_fail(monkeypatch):
    fake = FakeTsfClient(applications=[_application(), _application(ApplicationId="application-dup")])
    _make_module(monkeypatch, fake)
    _base(name="orders")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSF applications matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeApplications(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(name="orders")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
