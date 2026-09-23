"""Unit tests for the redis_parameter_template write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake Redis client
whose write operations mutate the template store, so the post-write
``find`` refetch converges immediately.

Scenario matrix:

* absent on a missing template (idempotent no-op)
* absent with a matching template (check-mode dry run and the real delete)
* creation when missing (missing product_type, check-mode dry run and the
  happy path)
* no-op when nothing drifts
* parameter / rename drift updates and their check mode
* the immutable product-type guard
* the ``name is required when state=present`` guard
* the ambiguous-name guard and the required_one_of guard
* the blanket ``Tencent Cloud API request failed`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import redis_parameter_template as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

TEMPLATE_ID = "tmpl-1a2b3c4d"

TEMPLATE = {
    "TemplateId": TEMPLATE_ID,
    "Name": "production-redis",
    "Description": "",
    "ProductType": 2,
    "Items": [{"Name": "timeout", "CurrentValue": "300"}],
}


def _template(**overrides):
    item = copy.deepcopy(TEMPLATE)
    item.update(overrides)
    return item


def _base(**overrides):
    # NOTE: keys carrying ``choices`` (state) must not be pre-filled with
    # None. template_id/name are a required_one_of pair so the
    # _name_args/_id_args helpers supply exactly one of them.
    params = {}
    params.update(overrides)
    return module_args(**params)


def _name_args(**overrides):
    params = {"name": "production-redis"}
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {"template_id": TEMPLATE_ID}
    params.update(overrides)
    return module_args(**params)


class FakeRedisClient(object):
    """In-memory Redis client mutating a small template store."""

    def __init__(self, templates=None):
        self.templates = [copy.deepcopy(t) for t in (templates or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _template(self, template_id):
        for item in self.templates:
            if item.get("TemplateId") == template_id:
                return item
        return None

    def DescribeParamTemplates(self, request):
        self._record("DescribeParamTemplates", request)
        ids = list(getattr(request, "TemplateIds", None) or [])
        names = list(getattr(request, "TemplateNames", None) or [])
        if ids:
            page = [t for t in self.templates if t.get("TemplateId") in ids]
        elif names:
            page = [t for t in self.templates if t.get("Name") in names]
        else:
            page = list(self.templates)
        return SimpleNamespace(
            Items=[FakeResource({"TemplateId": t["TemplateId"], "Name": t["Name"]}) for t in page],
        )

    def DescribeParamTemplateInfo(self, request):
        self._record("DescribeParamTemplateInfo", request)
        item = self._template(getattr(request, "TemplateId", None))
        if item is None:
            return FakeResource({})
        return FakeResource(copy.deepcopy(item))

    def CreateParamTemplate(self, request):
        self._record("CreateParamTemplate", request)
        template_id = "tmpl-new-%d" % (len(self.templates) + 1)
        item = {
            "TemplateId": template_id,
            "Name": getattr(request, "Name", None),
            "Description": getattr(request, "Description", ""),
            "ProductType": getattr(request, "ProductType", None),
            "Items": [
                {"Name": getattr(p, "Key", None), "CurrentValue": getattr(p, "Value", None)}
                for p in (getattr(request, "ParamList", None) or [])
            ],
        }
        self.templates.append(item)
        return SimpleNamespace(TemplateId=template_id, RequestId="req-fake")

    def ModifyParamTemplate(self, request):
        self._record("ModifyParamTemplate", request)
        item = self._template(getattr(request, "TemplateId", None))
        if item is not None:
            item["Name"] = getattr(request, "Name", item.get("Name"))
            item["Description"] = getattr(request, "Description", item.get("Description"))
            item["Items"] = [
                {"Name": getattr(p, "Key", None), "CurrentValue": getattr(p, "Value", None)}
                for p in (getattr(request, "ParamList", None) or [])
            ]
        return SimpleNamespace(RequestId="req-fake")

    def DeleteParamTemplate(self, request):
        self._record("DeleteParamTemplate", request)
        self.templates = [t for t in self.templates if t.get("TemplateId") != getattr(request, "TemplateId", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(RedisClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_template_is_idempotent(monkeypatch):
    fake = FakeRedisClient(templates=[])
    _make_module(monkeypatch, fake)
    _name_args(state="absent", name="ghost-template")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["parameter_template"] is None
    assert [c for c, unused in fake.calls] == ["DescribeParamTemplates"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeRedisClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _id_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter_template"]["TemplateId"] == TEMPLATE_ID
    assert len(fake.templates) == 1
    assert "DeleteParamTemplate" not in [c for c, unused in fake.calls]


def test_absent_deletes_template(monkeypatch):
    fake = FakeRedisClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter_template"] is None
    assert fake.templates == []
    assert "DeleteParamTemplate" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_present_requires_name(monkeypatch):
    fake = FakeRedisClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _id_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when state=present" in exc.value.args[0]["msg"]


def test_create_requires_product_type(monkeypatch):
    fake = FakeRedisClient(templates=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", name="ghost-template", parameters={"timeout": "300"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "product_type is required when creating" in payload["msg"]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeRedisClient(templates=[])
    _make_module(monkeypatch, fake)
    _name_args(
        _ansible_check_mode=True,
        state="present",
        name="ghost-template",
        product_type=2,
        description="prod params",
        parameters={"timeout": "300"},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter_template"] is None
    assert fake.templates == []
    assert "CreateParamTemplate" not in [c for c, unused in fake.calls]


def test_create_template(monkeypatch):
    fake = FakeRedisClient(templates=[])
    _make_module(monkeypatch, fake)
    _name_args(
        state="present",
        name="production-redis",
        product_type=2,
        description="prod params",
        parameters={"timeout": "300"},
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    template = result["parameter_template"]
    assert template["TemplateId"].startswith("tmpl-")
    assert template["Name"] == "production-redis"
    assert len(fake.templates) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeParamTemplates"
    assert "CreateParamTemplate" in ops


# ---------------------------------------------------------------------------
# existing-template flows
# ---------------------------------------------------------------------------


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeRedisClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _name_args(state="present", parameters={"timeout": "300"})
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["parameter_template"]["TemplateId"] == TEMPLATE_ID
    assert "ModifyParamTemplate" not in [c for c, unused in fake.calls]


def test_update_parameters(monkeypatch):
    fake = FakeRedisClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _name_args(state="present", parameters={"timeout": "300", "maxmemory-policy": "allkeys-lru"})
    result = run(mod.run_module)
    assert result["changed"] is True
    params = {x["Name"]: x["CurrentValue"] for x in result["parameter_template"]["Items"]}
    assert params == {"timeout": "300", "maxmemory-policy": "allkeys-lru"}
    assert "ModifyParamTemplate" in [c for c, unused in fake.calls]


def test_rename_via_template_id(monkeypatch):
    fake = FakeRedisClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="renamed-redis", parameters={"timeout": "300"})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["parameter_template"]["Name"] == "renamed-redis"
    assert fake.templates[0]["Name"] == "renamed-redis"
    assert "ModifyParamTemplate" in [c for c, unused in fake.calls]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeRedisClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="present", parameters={"timeout": "600"})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.templates[0]["Items"] == [{"Name": "timeout", "CurrentValue": "300"}]
    assert "ModifyParamTemplate" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards / validation / failure paths
# ---------------------------------------------------------------------------


def test_immutable_product_type_fails(monkeypatch):
    fake = FakeRedisClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="production-redis", product_type=3, parameters={"timeout": "300"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed on an existing Redis parameter template" in payload["msg"]
    assert payload["replacement_required"] is True
    assert payload["immutable_changes"]["ProductType"] == {"before": 2, "after": 3}
    assert "ModifyParamTemplate" not in [c for c, unused in fake.calls]


def test_multiple_templates_with_same_name_fail(monkeypatch):
    fake = FakeRedisClient(templates=[_template(), _template(TemplateId="tmpl-dup")])
    _make_module(monkeypatch, fake)
    _name_args(state="present", parameters={"timeout": "300"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Multiple Redis parameter templates have the requested name" in payload["msg"]
    assert payload["name"] == "production-redis"


def test_missing_identity_fails(monkeypatch):
    fake = FakeRedisClient(templates=[])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "template_id" in payload["msg"]
    assert "name" in payload["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeParamTemplates(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _id_args(state="present", name="production-redis")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
