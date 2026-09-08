"""Unit tests for the dnspod_record write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake DNSPod client
whose write operations mutate the record store, so the module's post-write
``find_record`` refetch returns the mutated state immediately.

Scenario matrix:

* the domain-or-domain_id identity guard
* absent on a missing record (idempotent no-op)
* absent with a matching record (check-mode dry run and real delete)
* creation when missing (value required, check mode, full create)
* no-op when nothing drifts
* drift updates on value / ttl / weight / mx / remark / status
* update check-mode dry run
* the blanket SDK-failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dnspod_record as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RECORD = {
    "RecordId": 87654321,
    "Name": "www",
    "Type": "A",
    "Line": "默认",
    "Value": "1.2.3.4",
    "TTL": 600,
    "Remark": "front door",
    "Status": "ENABLE",
}


def _record(**overrides):
    item = copy.deepcopy(RECORD)
    item.update(overrides)
    return item


def _stored(record, domain="example.com", domain_id=None):
    return {"domain": domain, "domain_id": domain_id, "record": record}


def _base(**overrides):
    # A record is identified by domain (or domain_id) + name + type + line.
    params = {"domain": "example.com", "subdomain": "www", "record_type": "A", "value": "1.2.3.4"}
    params.update(overrides)
    return module_args(**params)


class FakeDnspodClient(object):
    """In-memory DNSPod client mutating a record store.

    Store entries keep the lookup domain/domain_id separate from the DNS
    record payload so the fake response mimics the real DescribeRecordList
    (which does not echo the domain back on every record).
    """

    def __init__(self, stored=None):
        self.stored = [copy.deepcopy(t) for t in (stored or [])]
        self.calls = []
        self._next_id = 20000000

    def _record(self, name, request):
        self.calls.append((name, request))

    def _matches(self, request):
        matched = []
        for entry in self.stored:
            if getattr(request, "Domain", None) and entry.get("domain") != request.Domain:
                continue
            if getattr(request, "DomainId", None) and entry.get("domain_id") != request.DomainId:
                continue
            record = entry["record"]
            if getattr(request, "Subdomain", None) and record.get("Name") != request.Subdomain:
                continue
            if getattr(request, "RecordType", None) and record.get("Type") != request.RecordType:
                continue
            if getattr(request, "RecordLine", None) and record.get("Line") != request.RecordLine:
                continue
            matched.append(entry)
        return matched

    def DescribeRecordList(self, request):
        self._record("DescribeRecordList", request)
        matches = self._matches(request)
        return SimpleNamespace(
            RecordList=[FakeResource(dict(e["record"])) for e in matches],
        )

    def CreateRecord(self, request):
        self._record("CreateRecord", request)
        record = {
            "RecordId": self._next_id,
            "Name": request.SubDomain,
            "Type": request.RecordType,
            "Line": request.RecordLine,
            "Value": request.Value,
            "TTL": getattr(request, "TTL", None),
            "Weight": getattr(request, "Weight", None),
            "MX": getattr(request, "MX", None),
            "Remark": getattr(request, "Remark", None),
            "Status": getattr(request, "Status", None),
        }
        self._next_id += 1
        self.stored.append(_stored(
            record,
            domain=getattr(request, "Domain", None),
            domain_id=getattr(request, "DomainId", None),
        ))
        return SimpleNamespace(RecordId=record["RecordId"], RequestId="req-fake")

    def ModifyRecord(self, request):
        self._record("ModifyRecord", request)
        for entry in self.stored:
            record = entry["record"]
            if record.get("RecordId") != request.RecordId:
                continue
            for attr, field in (
                ("SubDomain", "Name"),
                ("RecordType", "Type"),
                ("RecordLine", "Line"),
                ("Value", "Value"),
                ("TTL", "TTL"),
                ("Weight", "Weight"),
                ("MX", "MX"),
                ("Remark", "Remark"),
                ("Status", "Status"),
            ):
                value = getattr(request, attr, None)
                if value is not None:
                    record[field] = value
        return SimpleNamespace(RequestId="req-fake")

    def DeleteRecord(self, request):
        self._record("DeleteRecord", request)
        self.stored = [
            e for e in self.stored if e["record"].get("RecordId") != request.RecordId
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_dnspod", lambda: (models or FakeModels(), SimpleNamespace(DnspodClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# identity guard
# ---------------------------------------------------------------------------


def test_domain_or_domain_id_required(monkeypatch):
    fake = FakeDnspodClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", subdomain="www", record_type="A", value="1.2.3.4")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "domain or domain_id is required" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_record_is_idempotent(monkeypatch):
    fake = FakeDnspodClient()
    _make_module(monkeypatch, fake)
    _base(state="absent", domain="ghost.example")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "DNS record already absent"
    assert [c for c, unused in fake.calls] == ["DescribeRecordList"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDnspodClient(stored=[_stored(_record())])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete DNS record"
    assert "DeleteRecord" not in [c for c, unused in fake.calls]


def test_absent_deletes_record(monkeypatch):
    fake = FakeDnspodClient(stored=[_stored(_record())])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record"] is None
    assert fake.stored == []
    assert "DeleteRecord" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_value(monkeypatch):
    fake = FakeDnspodClient()
    _make_module(monkeypatch, fake)
    _base(state="present", value=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "value is required when creating a DNS record" in exc.value.args[0]["msg"]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDnspodClient()
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", value="5.6.7.8", ttl=300)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create DNS record"
    assert fake.stored == []
    assert "CreateRecord" not in [c for c, unused in fake.calls]


def test_create_record(monkeypatch):
    fake = FakeDnspodClient()
    _make_module(monkeypatch, fake)
    _base(state="present", value="5.6.7.8", ttl=300)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "created" in result["msg"]
    assert result["record"]["Value"] == "5.6.7.8"
    assert result["record"]["TTL"] == 300
    assert len(fake.stored) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeRecordList"
    assert "CreateRecord" in ops


def test_create_by_domain_id(monkeypatch):
    fake = FakeDnspodClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", domain_id=12345, subdomain="api", record_type="CNAME", value="lb.example.com", record_line="默认")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record"]["Name"] == "api"
    assert fake.stored[0]["domain_id"] == 12345
    assert fake.stored[0]["domain"] is None


# ---------------------------------------------------------------------------
# existing-record flows
# ---------------------------------------------------------------------------


def test_record_no_drift_is_idempotent(monkeypatch):
    fake = FakeDnspodClient(stored=[_stored(_record())])
    _make_module(monkeypatch, fake)
    _base(state="present", ttl=600)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["record"]["RecordId"] == 87654321
    assert "ModifyRecord" not in [c for c, unused in fake.calls]


def test_update_value_drift(monkeypatch):
    fake = FakeDnspodClient(stored=[_stored(_record())])
    _make_module(monkeypatch, fake)
    _base(state="present", value="5.6.7.8", ttl=600)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record"]["Value"] == "5.6.7.8"
    assert "ModifyRecord" in [c for c, unused in fake.calls]
    assert "updated" in result["msg"]


def test_update_attributes_drift(monkeypatch):
    stored = _stored(_record(Weight=10, MX=5, Remark="old remark", Status="ENABLE", TTL=600))
    fake = FakeDnspodClient(stored=[stored])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        value="1.2.3.4",
        ttl=1200,
        weight=20,
        mx=10,
        remark="new remark",
        status="DISABLE",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record"]["TTL"] == 1200
    assert result["record"]["Weight"] == 20
    assert result["record"]["MX"] == 10
    assert result["record"]["Remark"] == "new remark"
    assert result["record"]["Status"] == "DISABLE"
    assert "ModifyRecord" in [c for c, unused in fake.calls]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeDnspodClient(stored=[_stored(_record())])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", value="5.6.7.8", ttl=600)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update DNS record"
    assert "record" not in result
    assert "ModifyRecord" not in [c for c, unused in fake.calls]


def test_non_default_record_line_scope(monkeypatch):
    # A record on a non-default line is only matched when the module asks
    # for that exact line; the default-line record is out of scope.
    fake = FakeDnspodClient(stored=[_stored(_record(Line="电信"))])
    _make_module(monkeypatch, fake)
    _base(state="absent", subdomain="www", record_line="电信")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.stored == []


def test_record_line_mismatch_is_out_of_scope(monkeypatch):
    # A default-line record must not be deleted by an absent request that
    # targets the 电信 line.
    fake = FakeDnspodClient(stored=[_stored(_record(Line="默认"))])
    _make_module(monkeypatch, fake)
    _base(state="absent", subdomain="www", record_line="电信")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert len(fake.stored) == 1


# ---------------------------------------------------------------------------
# failure path
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeRecordList(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
