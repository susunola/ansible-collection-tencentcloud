"""Unit tests for the teo_web_security_template write module (run_module flows).

Drives ``run_module()`` against an in-memory fake EdgeOne client whose
create / modify / delete operations mutate a web-security-template store so
post-write describes converge immediately.

Scenario matrix:

* absent on a missing template, identified by name or by ``template_id``
  (idempotent no-op)
* absent with a matching template (check-mode dry run, real delete)
* creation when missing (happy path and check-mode dry run)
* ``name`` is mandatory for ``state=present`` even when ``template_id`` is
  given
* no-op when the template name already matches
* rename by ``template_id`` modifies in place; rename by name alone creates
  a separate template
* the ambiguous-match guard and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import teo_web_security_template as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ZONE_ID = "zone-abc123"

TEMPLATE = {
    "TemplateId": "temp-1001",
    "TemplateName": "production_security",
    "ZoneId": ZONE_ID,
}


def _template(**overrides):
    item = copy.deepcopy(TEMPLATE)
    item.update(overrides)
    return item


def _args(**overrides):
    params = {"zone_id": ZONE_ID, "name": "production_security"}
    params.update(overrides)
    return module_args(**params)


class FakeTeoClient(object):
    """In-memory EdgeOne client mutating a web-security-template store."""

    def __init__(self, templates=None):
        self.templates = [copy.deepcopy(t) for t in (templates or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _in_zone(self, request, item):
        zone_ids = getattr(request, "ZoneIds", None) or []
        return (not zone_ids) or item.get("ZoneId") in zone_ids

    def DescribeWebSecurityTemplates(self, request):
        self._record("DescribeWebSecurityTemplates", request)
        matches = [t for t in self.templates if self._in_zone(request, t)]
        return SimpleNamespace(
            SecurityPolicyTemplates=[FakeResource(t) for t in matches], TotalCount=len(matches)
        )

    def _new_template_id(self):
        used = {
            int(t["TemplateId"].split("-")[1])
            for t in self.templates
            if t.get("TemplateId", "").startswith("temp-")
        }
        return "temp-%d" % ((max(used) + 1) if used else 1001)

    def CreateWebSecurityTemplate(self, request):
        self._record("CreateWebSecurityTemplate", request)
        self._next += 1
        item = {
            "TemplateId": self._new_template_id(),
            "TemplateName": getattr(request, "TemplateName", None),
            "ZoneId": getattr(request, "ZoneId", None),
        }
        self.templates.append(item)
        return SimpleNamespace(TemplateId=item["TemplateId"], RequestId="req-fake")

    def ModifyWebSecurityTemplate(self, request):
        self._record("ModifyWebSecurityTemplate", request)
        template_id = getattr(request, "TemplateId", None)
        for item in self.templates:
            if item.get("TemplateId") == template_id:
                item["TemplateName"] = getattr(request, "TemplateName", item.get("TemplateName"))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteWebSecurityTemplate(self, request):
        self._record("DeleteWebSecurityTemplate", request)
        template_id = getattr(request, "TemplateId", None)
        self.templates = [t for t in self.templates if t.get("TemplateId") != template_id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TeoClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_by_name_is_idempotent(monkeypatch):
    fake = FakeTeoClient(templates=[])
    _make_module(monkeypatch, fake)
    _args(state="absent", name="ghost-template")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["security_template"] is None
    assert [c for c, unused in fake.calls] == ["DescribeWebSecurityTemplates"]


def test_absent_missing_by_template_id_is_idempotent(monkeypatch):
    fake = FakeTeoClient(templates=[])
    _make_module(monkeypatch, fake)
    _args(state="absent", template_id="temp-9999")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["security_template"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTeoClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["security_template"]["TemplateId"] == "temp-1001"
    assert len(fake.templates) == 1
    assert "DeleteWebSecurityTemplate" not in [c for c, unused in fake.calls]


def test_absent_deletes_template(monkeypatch):
    fake = FakeTeoClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _args(state="absent", template_id="temp-1001")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["security_template"] is None
    assert fake.templates == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteWebSecurityTemplate" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_present_requires_name(monkeypatch):
    fake = FakeTeoClient(templates=[])
    _make_module(monkeypatch, fake)
    _args(state="present", template_id="temp-1001", name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when state=present" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_create_template(monkeypatch):
    fake = FakeTeoClient(templates=[])
    _make_module(monkeypatch, fake)
    _args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["security_template"]["TemplateName"] == "production_security"
    assert result["security_template"]["TemplateId"] == "temp-1001"
    assert result["security_template"]["ZoneId"] == ZONE_ID
    assert len(fake.templates) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeWebSecurityTemplates"
    assert "CreateWebSecurityTemplate" in ops
    assert ops[-1] == "DescribeWebSecurityTemplates"


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTeoClient(templates=[])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "diff" in result
    assert result["security_template"] is None
    assert fake.templates == []
    assert "CreateWebSecurityTemplate" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-template flows
# ---------------------------------------------------------------------------


def test_existing_template_no_drift_is_idempotent(monkeypatch):
    fake = FakeTeoClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["security_template"]["TemplateId"] == "temp-1001"
    assert "ModifyWebSecurityTemplate" not in [c for c, unused in fake.calls]


def test_rename_by_template_id(monkeypatch):
    fake = FakeTeoClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _args(state="present", template_id="temp-1001", name="renamed-security")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["security_template"]["TemplateId"] == "temp-1001"
    assert result["security_template"]["TemplateName"] == "renamed-security"
    ops = [c for c, unused in fake.calls]
    assert "ModifyWebSecurityTemplate" in ops
    modify_call = dict((name, request) for name, request in fake.calls)["ModifyWebSecurityTemplate"]
    assert modify_call.TemplateName == "renamed-security"


def test_rename_by_name_alone_creates_new_template(monkeypatch):
    # Without template_id the module can only look the template up by its
    # exact name, so handing it a brand-new name reads as a brand-new template.
    fake = FakeTeoClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _args(state="present", name="renamed-security")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["security_template"]["TemplateName"] == "renamed-security"
    names = sorted(t["TemplateName"] for t in fake.templates)
    assert names == ["production_security", "renamed-security"]


def test_ambiguous_name_match_fails(monkeypatch):
    fake = FakeTeoClient(templates=[_template(), _template(TemplateId="temp-2002")])
    _make_module(monkeypatch, fake)
    _args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "specify template_id" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeWebSecurityTemplates(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
