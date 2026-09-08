"""Unit tests for the cfw_address_template write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake CFW client
whose write operations mutate the address-template store, so the module's
post-write ``find_template`` refetch and waiter converge immediately.

Scenario matrix:

* absent on a missing template (idempotent no-op)
* absent with a matching template (check-mode dry run and the real delete)
* creation when missing (the ``required_if`` name/addresses guard, check
  mode, happy paths for ip and domain templates)
* no-op when nothing drifts
* address drift updates and check-mode dry runs
* the immutable ip_version guard and the multiple-match guard
* the ``Tencent Cloud API request failed`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cfw_address_template as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

TEMPLATE = {
    "Uuid": "cfw-template-abc",
    "Name": "trusted-networks",
    "Detail": "Internal networks",
    "IpString": "10.0.0.0/8,192.168.0.0/16",
    "Type": 1,
    "IpVersion": 0,
}


def _template(**overrides):
    item = copy.deepcopy(TEMPLATE)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {}
    params.update(overrides)
    return module_args(**params)


class FakeCfwClient(object):
    """In-memory CFW client mutating a small address-template store."""

    def __init__(self, templates=None):
        self.templates = [copy.deepcopy(t) for t in (templates or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeAddressTemplateList(self, request):
        self._record("DescribeAddressTemplateList", request)
        uuid = getattr(request, "Uuid", None)
        search = getattr(request, "SearchValue", None)
        matches = []
        for item in self.templates:
            if uuid and item.get("Uuid") == uuid:
                matches.append(dict(item))
            elif not uuid and search and item.get("Name") == search:
                matches.append(dict(item))
        return SimpleNamespace(Data=[FakeResource(t) for t in matches])

    def CreateAddressTemplate(self, request):
        self._record("CreateAddressTemplate", request)
        self._next += 1
        item = {
            "Uuid": "cfw-template-new-%03d" % self._next,
            "Name": getattr(request, "Name", None),
            "Detail": getattr(request, "Detail", None),
            "IpString": getattr(request, "IpString", None),
            "Type": getattr(request, "Type", None),
            "IpVersion": getattr(request, "IpVersion", None),
        }
        self.templates.append(item)
        return SimpleNamespace(Uuid=item["Uuid"], RequestId="req-fake")

    def ModifyAddressTemplate(self, request):
        self._record("ModifyAddressTemplate", request)
        for item in self.templates:
            if item.get("Uuid") == getattr(request, "Uuid", None):
                item["Name"] = getattr(request, "Name", None)
                item["Detail"] = getattr(request, "Detail", None)
                item["IpString"] = getattr(request, "IpString", None)
                item["Type"] = getattr(request, "Type", None)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAddressTemplate(self, request):
        self._record("DeleteAddressTemplate", request)
        self.templates = [t for t in self.templates if t.get("Uuid") != getattr(request, "Uuid", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_cfw", lambda: (models or FakeModels(), SimpleNamespace(CfwClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _ops(fake):
    return [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_template_is_idempotent(monkeypatch):
    fake = FakeCfwClient(templates=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["template"] is None
    assert _ops(fake) == ["DescribeAddressTemplateList"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCfwClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", uuid="cfw-template-abc")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["template"]["Name"] == "trusted-networks"
    assert len(fake.templates) == 1
    assert "DeleteAddressTemplate" not in _ops(fake)


def test_absent_deletes_template(monkeypatch):
    fake = FakeCfwClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _base(state="absent", uuid="cfw-template-abc")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["template"] is None
    assert fake.templates == []
    ops = _ops(fake)
    assert "DeleteAddressTemplate" in ops
    delete_request = [r for c, r in fake.calls if c == "DeleteAddressTemplate"][0]
    assert delete_request.Uuid == "cfw-template-abc"


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_present_requires_name_and_addresses(monkeypatch):
    fake = FakeCfwClient(templates=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="trusted-networks")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "addresses" in exc.value.args[0]["msg"]


def test_create_ip_template(monkeypatch):
    fake = FakeCfwClient(templates=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="trusted-networks",
        template_type="ip",
        addresses=["192.168.0.0/16", "10.0.0.0/8"],
        description="Internal networks",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["template"]["Name"] == "trusted-networks"
    assert result["template"]["Type"] == 1
    assert result["template"]["IpVersion"] == 0
    assert result["template"]["IpString"] == "10.0.0.0/8,192.168.0.0/16"
    assert len(fake.templates) == 1
    ops = _ops(fake)
    assert ops[0] == "DescribeAddressTemplateList"
    assert "CreateAddressTemplate" in ops


def test_create_domain_template(monkeypatch):
    fake = FakeCfwClient(templates=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        name="trusted-domains",
        template_type="domain",
        addresses=["example.com", "internal.example.net"],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["template"]["Type"] == 5
    assert "CreateAddressTemplate" in _ops(fake)


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCfwClient(templates=[])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        name="trusted-networks",
        addresses=["10.0.0.0/8"],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.templates == []
    assert "CreateAddressTemplate" not in _ops(fake)


# ---------------------------------------------------------------------------
# existing-template flows
# ---------------------------------------------------------------------------


def test_existing_template_no_drift_is_idempotent(monkeypatch):
    fake = FakeCfwClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        uuid="cfw-template-abc",
        name="trusted-networks",
        template_type="ip",
        addresses=["10.0.0.0/8", "192.168.0.0/16"],
        description="Internal networks",
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["template"]["Uuid"] == "cfw-template-abc"
    assert "ModifyAddressTemplate" not in _ops(fake)


def test_existing_template_address_drift_updates(monkeypatch):
    fake = FakeCfwClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        uuid="cfw-template-abc",
        name="trusted-networks",
        template_type="ip",
        addresses=["10.0.0.0/8", "192.168.0.0/16", "172.16.0.0/12"],
        description="Internal networks",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["template"]["IpString"] == "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
    ops = _ops(fake)
    assert "ModifyAddressTemplate" in ops
    modify_request = [r for c, r in fake.calls if c == "ModifyAddressTemplate"][0]
    assert modify_request.Uuid == "cfw-template-abc"


def test_existing_template_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeCfwClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        uuid="cfw-template-abc",
        name="trusted-networks",
        template_type="ip",
        addresses=["10.0.0.0/8", "172.16.0.0/12"],
        description="Internal networks",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.templates[0]["IpString"] == "10.0.0.0/8,192.168.0.0/16"
    assert "ModifyAddressTemplate" not in _ops(fake)


def test_ip_version_immutable_fails(monkeypatch):
    fake = FakeCfwClient(templates=[_template()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        uuid="cfw-template-abc",
        name="trusted-networks",
        template_type="ip",
        addresses=["10.0.0.0/8", "192.168.0.0/16"],
        description="Internal networks",
        ip_version=1,
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "ip_version cannot be changed" in payload["msg"]
    assert payload["requested_ip_version"] == 1


def test_multiple_name_matches_fail(monkeypatch):
    fake = FakeCfwClient(templates=[_template(), _template(Uuid="cfw-template-dup")])
    _make_module(monkeypatch, fake)
    _base(state="present", name="trusted-networks", addresses=["10.0.0.0/8"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple Cloud Firewall address templates" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure path
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAddressTemplateList(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="trusted-networks", addresses=["10.0.0.0/8"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
