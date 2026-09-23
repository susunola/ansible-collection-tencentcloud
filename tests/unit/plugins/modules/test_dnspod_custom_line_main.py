"""Unit tests for the dnspod_custom_line write module (run_module flows).

Drives ``run_module()`` against an in-memory fake DNSPod client whose custom
line store is mutated by create / modify / delete so post-write describes
converge immediately.

Scenario matrix:

* absent on a missing custom line (idempotent no-op)
* absent with a matching line (check-mode dry run, real delete)
* creation when missing (happy path, check mode)
* no-op when name and area already match
* area drift triggers an update (name is the immutable identity)
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dnspod_custom_line as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

LINE = {
    "Name": "office-network",
    "Area": "203.0.113.1-203.0.113.254",
}


def _line(**overrides):
    item = copy.deepcopy(LINE)
    item.update(overrides)
    return item


def _name_args(**overrides):
    params = {"domain": "example.com", "name": "office-network", "area": "203.0.113.1-203.0.113.254"}
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {"domain_id": 1001, "name": "office-network", "area": "203.0.113.1-203.0.113.254"}
    params.update(overrides)
    return module_args(**params)


class FakeDnspodClient(object):
    """In-memory DNSPod client mutating a custom line store."""

    def __init__(self, lines=None):
        self.lines = [copy.deepcopy(t) for t in (lines or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_name(self, name):
        for item in self.lines:
            if item.get("Name") == name:
                return item
        return None

    def DescribeDomainCustomLineList(self, request):
        self._record("DescribeDomainCustomLineList", request)
        return SimpleNamespace(LineList=[FakeResource(t) for t in self.lines])

    def CreateDomainCustomLine(self, request):
        self._record("CreateDomainCustomLine", request)
        self.lines.append({"Name": request.Name, "Area": request.Area})
        return SimpleNamespace(RequestId="req-fake")

    def ModifyDomainCustomLine(self, request):
        self._record("ModifyDomainCustomLine", request)
        item = self._by_name(getattr(request, "PreName", None))
        if item is not None:
            item["Name"] = getattr(request, "Name", item.get("Name"))
            item["Area"] = getattr(request, "Area", item.get("Area"))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteDomainCustomLine(self, request):
        self._record("DeleteDomainCustomLine", request)
        self.lines = [t for t in self.lines if t.get("Name") != request.Name]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(DnspodClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_line_is_idempotent(monkeypatch):
    fake = FakeDnspodClient(lines=[])
    _make_module(monkeypatch, fake)
    _name_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["custom_line"] is None
    assert [c for c, unused in fake.calls] == ["DescribeDomainCustomLineList"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDnspodClient(lines=[_line()])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["custom_line"]["Name"] == "office-network"
    assert len(fake.lines) == 1
    assert "DeleteDomainCustomLine" not in [c for c, unused in fake.calls]


def test_absent_deletes_line(monkeypatch):
    fake = FakeDnspodClient(lines=[_line()])
    _make_module(monkeypatch, fake)
    _name_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["custom_line"] is None
    assert fake.lines == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteDomainCustomLine" in ops


def test_absent_by_domain_id_deletes_line(monkeypatch):
    fake = FakeDnspodClient(lines=[_line()])
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.lines == []


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_custom_line(monkeypatch):
    fake = FakeDnspodClient(lines=[])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["custom_line"]["Name"] == "office-network"
    assert result["custom_line"]["Area"] == "203.0.113.1-203.0.113.254"
    assert len(fake.lines) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeDomainCustomLineList"
    assert "CreateDomainCustomLine" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDnspodClient(lines=[])
    _make_module(monkeypatch, fake)
    _name_args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.lines == []
    assert "CreateDomainCustomLine" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-line flows
# ---------------------------------------------------------------------------


def test_existing_line_no_drift_is_idempotent(monkeypatch):
    fake = FakeDnspodClient(lines=[_line()])
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["custom_line"]["Name"] == "office-network"
    assert "ModifyDomainCustomLine" not in [c for c, unused in fake.calls]


def test_area_drift_updates_line(monkeypatch):
    fake = FakeDnspodClient(lines=[_line()])
    _make_module(monkeypatch, fake)
    _name_args(state="present", area="198.51.100.1-198.51.100.100")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["custom_line"]["Area"] == "198.51.100.1-198.51.100.100"
    ops = [c for c, unused in fake.calls]
    assert "ModifyDomainCustomLine" in ops


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeDomainCustomLineList(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _name_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
