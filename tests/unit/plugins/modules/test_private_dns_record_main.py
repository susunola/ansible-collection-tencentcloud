"""Unit tests for the private_dns_record write module (run_module flows).

``private_dns_record`` manages one record inside a Private DNS zone. The
module serializes describe responses through ``to_json_string``, so the
fake describe objects expose ``to_json_string`` (see ``JsonRecord``), and
it polls with ``wait_for_record`` after every write; the fake converges on
the first poll so waiting returns immediately.

Note the lazy SDK import helper is ``_load_private_dns`` (not ``_load``).

Scenario matrix:

* absent identifiers validation and absent-on-missing no-op
* absent delete (real, check mode)
* present create with optional mx/weight (real, check mode)
* present no-drift idempotence and TTL/remark drift update
* blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
import time
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import private_dns_record as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)

RECORD = {
    "RecordId": "pr-abc123",
    "ZoneId": "zone-abc123",
    "SubDomain": "api",
    "RecordType": "A",
    "RecordValue": "10.0.0.8",
    "TTL": 300,
    "Remark": "web api",
    "MX": 10,
    "Weight": 5,
}


def _record(**overrides):
    item = copy.deepcopy(RECORD)
    item.update(overrides)
    return item


def _r_args(**overrides):
    params = {"zone_id": "zone-abc123", "subdomain": "api", "record_type": "A", "value": "10.0.0.8"}
    params.update(overrides)
    return module_args(**params)


class JsonRecord(object):
    """SDK-model stand-in exposing attributes plus ``to_json_string()``."""

    def __init__(self, data):
        self._data = dict(data)

    def __getattr__(self, name):
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name)

    def to_json_string(self):
        return json.dumps(self._data)


class FakePrivateDnsClient(object):
    """In-memory Private DNS client mutating a zone record store."""

    def __init__(self, records=None):
        self.records = [copy.deepcopy(r) for r in (records or [])]
        self.calls = []
        self._next = 1000

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, record_id):
        return next((r for r in self.records if r["RecordId"] == record_id), None)

    def DescribePrivateZoneRecordList(self, request):
        self._record("DescribePrivateZoneRecordList", request)
        matches = [r for r in self.records if r.get("ZoneId") == request.ZoneId]
        return SimpleNamespace(RecordSet=[JsonRecord(r) for r in matches], TotalCount=len(matches))

    def CreatePrivateZoneRecord(self, request):
        self._record("CreatePrivateZoneRecord", request)
        self._next += 1
        record = {
            "RecordId": "pr-new%04d" % self._next,
            "ZoneId": request.ZoneId,
            "SubDomain": request.SubDomain,
            "RecordType": request.RecordType,
            "RecordValue": request.RecordValue,
            "TTL": request.TTL,
            "Remark": request.Remark,
        }
        if getattr(request, "MX", None) is not None:
            record["MX"] = request.MX
        if getattr(request, "Weight", None) is not None:
            record["Weight"] = request.Weight
        self.records.append(record)
        return SimpleNamespace(RecordId=record["RecordId"])

    def ModifyPrivateZoneRecord(self, request):
        self._record("ModifyPrivateZoneRecord", request)
        record = self._find(request.RecordId)
        record["SubDomain"] = request.SubDomain
        record["RecordType"] = request.RecordType
        record["RecordValue"] = request.RecordValue
        record["TTL"] = request.TTL
        record["Remark"] = request.Remark
        if getattr(request, "MX", None) is not None:
            record["MX"] = request.MX
        if getattr(request, "Weight", None) is not None:
            record["Weight"] = request.Weight
        return SimpleNamespace()

    def DeletePrivateZoneRecord(self, request):
        self._record("DeletePrivateZoneRecord", request)
        self.records = [r for r in self.records if r["RecordId"] != request.RecordId]
        return SimpleNamespace()


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_private_dns", lambda: (FakeModels(), SimpleNamespace(PrivatednsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_without_identifiers_fails(monkeypatch):
    fake = FakePrivateDnsClient(records=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", zone_id="zone-abc123")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "record_id or subdomain and record_type" in exc.value.args[0]["msg"]


def test_absent_on_missing_record_is_idempotent(monkeypatch):
    fake = FakePrivateDnsClient(records=[])
    _make_module(monkeypatch, fake)
    _r_args(state="absent", record_id="pr-ghost001")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["record"] is None
    assert "Private DNS record is absent" in result["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakePrivateDnsClient(records=[_record()])
    _make_module(monkeypatch, fake)
    _r_args(_ansible_check_mode=True, state="absent", record_id="pr-abc123")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record"]["RecordId"] == "pr-abc123"
    assert "Would delete private DNS record" in result["msg"]
    assert len(fake.records) == 1
    assert "DeletePrivateZoneRecord" not in [c for c, unused in fake.calls]


def test_absent_deletes_record(monkeypatch):
    fake = FakePrivateDnsClient(records=[_record()])
    _make_module(monkeypatch, fake)
    _r_args(state="absent", record_id="pr-abc123")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record"] is None
    assert "Private DNS record deleted" in result["msg"]
    assert fake.records == []
    ops = [c for c, unused in fake.calls]
    assert "DeletePrivateZoneRecord" in ops


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_creates_record(monkeypatch):
    fake = FakePrivateDnsClient(records=[])
    _make_module(monkeypatch, fake)
    _r_args(remark="web api", ttl=300, mx=10, weight=5)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record"]["RecordId"].startswith("pr-new")
    assert result["record"]["SubDomain"] == "api"
    assert result["record"]["MX"] == 10
    assert "Private DNS record created" in result["msg"]
    assert len(fake.records) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribePrivateZoneRecordList"
    assert "CreatePrivateZoneRecord" in ops


def test_present_create_check_mode_is_dry_run(monkeypatch):
    fake = FakePrivateDnsClient(records=[])
    _make_module(monkeypatch, fake)
    _r_args(_ansible_check_mode=True, remark="web api")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record"] is None
    assert "Would create private DNS record" in result["msg"]
    assert fake.records == []
    assert "CreatePrivateZoneRecord" not in [c for c, unused in fake.calls]


def test_present_no_drift_is_idempotent(monkeypatch):
    fake = FakePrivateDnsClient(records=[_record()])
    _make_module(monkeypatch, fake)
    _r_args(remark="web api", ttl=300, mx=10, weight=5)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["record"]["RecordId"] == "pr-abc123"
    assert "Private DNS record is up to date" in result["msg"]
    assert "ModifyPrivateZoneRecord" not in [c for c, unused in fake.calls]


def test_ttl_drift_updates_record(monkeypatch):
    fake = FakePrivateDnsClient(records=[_record()])
    _make_module(monkeypatch, fake)
    _r_args(remark="web api", ttl=600, mx=10, weight=5)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record"]["TTL"] == 600
    assert "Private DNS record updated" in result["msg"]
    assert fake.records[0]["TTL"] == 600
    ops = [c for c, unused in fake.calls]
    assert "ModifyPrivateZoneRecord" in ops


def test_present_update_check_mode_is_dry_run(monkeypatch):
    fake = FakePrivateDnsClient(records=[_record()])
    _make_module(monkeypatch, fake)
    _r_args(_ansible_check_mode=True, remark="web api", ttl=600, mx=10, weight=5)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record"]["TTL"] == 300
    assert "Would update private DNS record" in result["msg"]
    assert fake.records[0]["TTL"] == 300
    assert "ModifyPrivateZoneRecord" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribePrivateZoneRecordList(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _r_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
