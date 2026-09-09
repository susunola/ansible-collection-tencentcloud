"""Unit tests for the dnspod_domain write module (run_module flows).

Drives ``run_module()`` against an in-memory fake DNSPod client whose domain
store is mutated by create / modify / delete so post-write describes converge
immediately.

Scenario matrix:

* absent on a missing domain, identified by name or by ``domain_id``
  (idempotent no-op)
* absent with a matching domain (check-mode dry run, real delete)
* creation when missing (happy path with remark/tags/status, check mode,
  name-required guard)
* no-op when remark and status already match
* remark drift and status drift each trigger the matching modify call
* a duplicated name fails the lookup
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dnspod_domain as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

DOMAIN = {
    "DomainId": 1001,
    "Name": "example.com",
    "Remark": "",
    "Status": "ENABLE",
}


def _domain(**overrides):
    item = copy.deepcopy(DOMAIN)
    item.update(overrides)
    return item


def _name_args(**overrides):
    params = {"name": "example.com", "remark": "", "enabled": True, "tags": {}}
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {"domain_id": 1001, "remark": "", "enabled": True}
    params.update(overrides)
    return module_args(**params)


class FakeDnspodClient(object):
    """In-memory DNSPod client mutating a small domain store."""

    def __init__(self, domains=None):
        self.domains = [copy.deepcopy(t) for t in (domains or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_id(self, domain_id):
        for item in self.domains:
            if item.get("DomainId") == domain_id:
                return item
        return None

    def DescribeDomainList(self, request):
        self._record("DescribeDomainList", request)
        keyword = getattr(request, "Keyword", None)
        items = self.domains if not keyword else [t for t in self.domains if t.get("Name") == keyword]
        return SimpleNamespace(
            DomainList=[FakeResource(t) for t in items],
            DomainCountInfo=SimpleNamespace(DomainTotal=len(items)),
        )

    def CreateDomain(self, request):
        self._record("CreateDomain", request)
        self._next += 1
        item = {
            "DomainId": 1000 + self._next,
            "Name": getattr(request, "Domain", None),
            "Remark": "",
            "Status": "ENABLE",
        }
        self.domains.append(item)
        return SimpleNamespace(DomainInfo=FakeResource(item))

    def ModifyDomainRemark(self, request):
        self._record("ModifyDomainRemark", request)
        item = self._by_id(getattr(request, "DomainId", None))
        if item is not None:
            item["Remark"] = getattr(request, "Remark", item.get("Remark"))
        return SimpleNamespace(RequestId="req-fake")

    def ModifyDomainStatus(self, request):
        self._record("ModifyDomainStatus", request)
        item = self._by_id(getattr(request, "DomainId", None))
        if item is not None:
            item["Status"] = getattr(request, "Status", item.get("Status"))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteDomain(self, request):
        self._record("DeleteDomain", request)
        domain_id = getattr(request, "DomainId", None)
        self.domains = [t for t in self.domains if t.get("DomainId") != domain_id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(DnspodClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_by_name_is_idempotent(monkeypatch):
    fake = FakeDnspodClient(domains=[])
    _make_module(monkeypatch, fake)
    _name_args(state="absent", name="ghost.example.com")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["domain"] is None
    assert [c for c, unused in fake.calls] == ["DescribeDomainList"]


def test_absent_missing_by_id_is_idempotent(monkeypatch):
    fake = FakeDnspodClient(domains=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", domain_id=9999)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["domain"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDnspodClient(domains=[_domain()])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["domain"]["DomainId"] == 1001
    assert len(fake.domains) == 1
    assert "DeleteDomain" not in [c for c, unused in fake.calls]


def test_absent_deletes_domain(monkeypatch):
    fake = FakeDnspodClient(domains=[_domain()])
    _make_module(monkeypatch, fake)
    _name_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["domain"] is None
    assert fake.domains == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteDomain" in ops


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_domain_with_remark(monkeypatch):
    fake = FakeDnspodClient(domains=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", remark="Public production zone")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["domain"]["Name"] == "example.com"
    assert result["domain"]["Remark"] == "Public production zone"
    assert result["domain"]["Status"] == "ENABLE"
    assert len(fake.domains) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeDomainList"
    assert "CreateDomain" in ops
    assert "ModifyDomainRemark" in ops


def test_create_disabled_domain_toggles_status(monkeypatch):
    fake = FakeDnspodClient(domains=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["domain"]["Status"] == "DISABLE"
    ops = [c for c, unused in fake.calls]
    assert "CreateDomain" in ops
    assert "ModifyDomainStatus" in ops


def test_create_domain_passes_tags(monkeypatch):
    fake = FakeDnspodClient(domains=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present", tags={"env": "prod"})
    result = run(mod.run_module)
    assert result["changed"] is True
    create_call = dict((name, request) for name, request in fake.calls)["CreateDomain"]
    tags = list(create_call.Tags)
    assert len(tags) == 1
    assert tags[0].TagKey == "env"
    assert tags[0].TagValue == "prod"


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDnspodClient(domains=[])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="present", remark="Public production zone")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.domains == []
    assert "CreateDomain" not in [c for c, unused in fake.calls]


def test_present_requires_name(monkeypatch):
    fake = FakeDnspodClient(domains=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", domain_id=1001)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when state=present" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# existing-domain flows
# ---------------------------------------------------------------------------


def test_existing_domain_no_drift_is_idempotent(monkeypatch):
    fake = FakeDnspodClient(domains=[_domain()])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["domain"]["DomainId"] == 1001
    assert [c for c, unused in fake.calls] == ["DescribeDomainList"]


def test_remark_drift_updates_domain(monkeypatch):
    fake = FakeDnspodClient(domains=[_domain()])
    _make_module(monkeypatch, fake)
    _name_args(state="present", remark="Updated remark")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["domain"]["Remark"] == "Updated remark"
    ops = [c for c, unused in fake.calls]
    assert "ModifyDomainRemark" in ops


def test_status_drift_re_enables_domain(monkeypatch):
    fake = FakeDnspodClient(domains=[_domain(Status="DISABLE")])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["domain"]["Status"] == "ENABLE"
    ops = [c for c, unused in fake.calls]
    assert "ModifyDomainStatus" in ops


def test_duplicate_name_fails_lookup(monkeypatch):
    fake = FakeDnspodClient(domains=[_domain(), _domain(DomainId=1002)])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DNSPod domains have the requested name" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeDomainList(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
