"""Unit tests for the vpc_address_template write module (run_module flows).

Drives ``run_module()`` against an in-memory fake VPC client whose
create / modify / delete operations mutate an address-template store so
post-write describes converge immediately.

Scenario matrix:

* the state=present parameter guard (name + at least one address entry)
* absent on a missing template (idempotent no-op)
* absent with a matching template (check-mode dry run, real delete)
* creation from plain addresses and from extended entries (happy path, check
  mode, create-refind via the nested ``AddressTemplate`` response)
* no-op when the template already matches (order-invariant set comparison)
* address-set / extended-set drift through ModifyAddressTemplateAttribute
* rename by ``template_id``, the ambiguous-match guard and the blanket SDK
  failure paths
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import vpc_address_template as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

EXTRA = {"Type": "ip", "Address": "10.0.0.5/32", "Description": "db server"}

TEMPLATE = {
    "AddressTemplateId": "ipm-aaaa",
    "AddressTemplateName": "office-networks",
    "AddressSet": ["10.10.0.0/16", "192.0.2.10"],
    "AddressExtraSet": [],
}


def _template(**overrides):
    item = copy.deepcopy(TEMPLATE)
    item.update(overrides)
    return item


def _present_args(**overrides):
    params = {
        "state": "present",
        "name": "office-networks",
        "addresses": ["10.10.0.0/16", "192.0.2.10"],
        "address_extra": [],
    }
    params.update(overrides)
    return module_args(**params)


def _materialize(extra_models):
    return [dict(vars(item)) for item in (extra_models or [])]


class FakeVpcClient(object):
    """In-memory VPC client mutating a small address-template store."""

    def __init__(self, templates=None):
        self.templates = [copy.deepcopy(t) for t in (templates or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, template_id):
        for item in self.templates:
            if item.get("AddressTemplateId") == template_id:
                return item
        return None

    def DescribeAddressTemplates(self, request):
        self._record("DescribeAddressTemplates", request)
        return SimpleNamespace(
            AddressTemplateSet=[FakeResource(copy.deepcopy(t)) for t in self.templates],
            TotalCount=len(self.templates),
        )

    def CreateAddressTemplate(self, request):
        self._record("CreateAddressTemplate", request)
        self._next += 1
        item = {
            "AddressTemplateId": "ipm-n%04d" % self._next,
            "AddressTemplateName": getattr(request, "AddressTemplateName", None),
            "AddressSet": list(getattr(request, "Addresses", None) or []),
            "AddressExtraSet": _materialize(getattr(request, "AddressesExtra", None)),
        }
        self.templates.append(item)
        return SimpleNamespace(AddressTemplate=SimpleNamespace(AddressTemplateId=item["AddressTemplateId"]), RequestId="req-fake")

    def ModifyAddressTemplateAttribute(self, request):
        self._record("ModifyAddressTemplateAttribute", request)
        item = self._by_id(getattr(request, "AddressTemplateId", None))
        if item is not None:
            item["AddressTemplateName"] = getattr(request, "AddressTemplateName", item.get("AddressTemplateName"))
            item["AddressSet"] = list(getattr(request, "Addresses", None) or [])
            item["AddressExtraSet"] = _materialize(getattr(request, "AddressesExtra", None))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAddressTemplate(self, request):
        self._record("DeleteAddressTemplate", request)
        template_id = getattr(request, "AddressTemplateId", None)
        self.templates = [t for t in self.templates if t.get("AddressTemplateId") != template_id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(VpcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# guards / absent flows
# ---------------------------------------------------------------------------


def test_present_requires_address_entry(monkeypatch):
    fake = FakeVpcClient(templates=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="office-networks", addresses=[], address_extra=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name and at least one address entry are required" in exc.value.args[0]["msg"]


def test_absent_missing_template_is_idempotent(monkeypatch):
    fake = FakeVpcClient(templates=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ghost-template")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["address_template"] is None
    assert [c for c, unused in fake.calls] == ["DescribeAddressTemplates"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", name="office-networks")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["address_template"]["AddressTemplateId"] == "ipm-aaaa"
    assert len(fake.templates) == 1
    assert "DeleteAddressTemplate" not in [c for c, unused in fake.calls]


def test_absent_deletes_template(monkeypatch):
    fake = FakeVpcClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", template_id="ipm-aaaa")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["address_template"] is None
    assert fake.templates == []
    assert "DeleteAddressTemplate" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_from_addresses(monkeypatch):
    fake = FakeVpcClient(templates=[])
    _make_module(monkeypatch, fake)
    _present_args(addresses=["192.0.2.10", "10.10.0.0/16"])  # order-normalized
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["address_template"]["AddressTemplateId"] == "ipm-n0001"
    assert result["address_template"]["AddressSet"] == ["10.10.0.0/16", "192.0.2.10"]
    assert len(fake.templates) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeAddressTemplates"
    assert "CreateAddressTemplate" in ops
    assert ops[-1] == "DescribeAddressTemplates"


def test_create_from_extended_entries(monkeypatch):
    fake = FakeVpcClient(templates=[])
    _make_module(monkeypatch, fake)
    _present_args(addresses=[], address_extra=[EXTRA])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["address_template"]["AddressExtraSet"] == [EXTRA]
    assert result["address_template"]["AddressSet"] == []


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(templates=[])
    _make_module(monkeypatch, fake)
    _present_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["address_template"] is None
    assert "diff" in result
    assert fake.templates == []
    assert "CreateAddressTemplate" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-template flows
# ---------------------------------------------------------------------------


def test_existing_template_no_drift_is_idempotent(monkeypatch):
    remote = _template(AddressExtraSet=[EXTRA])
    fake = FakeVpcClient(templates=[remote])
    _make_module(monkeypatch, fake)
    _present_args(addresses=["192.0.2.10", "10.10.0.0/16"], address_extra=[EXTRA])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["address_template"]["AddressTemplateId"] == "ipm-aaaa"
    assert "ModifyAddressTemplateAttribute" not in [c for c, unused in fake.calls]


def test_address_set_drift_updates(monkeypatch):
    fake = FakeVpcClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _present_args(addresses=["10.10.0.0/16"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["address_template"]["AddressSet"] == ["10.10.0.0/16"]
    assert fake.templates[0]["AddressSet"] == ["10.10.0.0/16"]
    assert "ModifyAddressTemplateAttribute" in [c for c, unused in fake.calls]


def test_extra_set_drift_updates(monkeypatch):
    fake = FakeVpcClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _present_args(addresses=[], address_extra=[EXTRA])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["address_template"]["AddressSet"] == []
    assert result["address_template"]["AddressExtraSet"] == [EXTRA]
    assert "ModifyAddressTemplateAttribute" in [c for c, unused in fake.calls]


def test_rename_by_template_id(monkeypatch):
    fake = FakeVpcClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _present_args(template_id="ipm-aaaa", name="renamed-networks")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["address_template"]["AddressTemplateName"] == "renamed-networks"
    assert "ModifyAddressTemplateAttribute" in [c for c, unused in fake.calls]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeVpcClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _present_args(_ansible_check_mode=True, addresses=["10.10.0.0/16"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["address_template"]["AddressSet"] == ["10.10.0.0/16", "192.0.2.10"]
    assert "diff" in result
    assert fake.templates[0]["AddressSet"] == ["10.10.0.0/16", "192.0.2.10"]
    assert "ModifyAddressTemplateAttribute" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards and failure paths
# ---------------------------------------------------------------------------


def test_multiple_name_matches_fail(monkeypatch):
    fake = FakeVpcClient(templates=[_template(), _template(AddressTemplateId="ipm-bbbb")])
    _make_module(monkeypatch, fake)
    _present_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "specify template_id" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAddressTemplates(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _present_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


def test_delete_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAddressTemplates(self, request):
            return SimpleNamespace(AddressTemplateSet=[FakeResource(copy.deepcopy(_template()))], TotalCount=1)

        def DeleteAddressTemplate(self, request):
            raise Boom("delete refused")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="office-networks")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "delete refused" in payload["error"]
