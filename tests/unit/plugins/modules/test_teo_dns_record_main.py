"""Unit tests for the teo_dns_record write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake EdgeOne client
whose write operations mutate the DNS-record store so the post-write
``wait_for_record`` loops converge immediately.

Scenario matrix:

* identity/creation parameter guards (``required_one_of``, ``required_if``)
* absent on a missing record (idempotent no-op)
* absent with a matching record (check-mode dry run, real delete)
* creation when missing (check mode, happy path with the created RecordId
  waiter)
* no-op when nothing drifts
* content/TTL drift updates (with and without check mode)
* multiple-records-same-name ambiguity and the blanket error payload path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import teo_dns_record as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ZONE_ID = "zone-abcdef12"
RECORD_ID = "record-8b0a1c2d"
RECORD_NAME = "api.example.com"

RECORD = {
    "RecordId": RECORD_ID,
    "ZoneId": ZONE_ID,
    "Name": RECORD_NAME,
    "Type": "A",
    "Content": "203.0.113.10",
    "Location": "Default",
    "TTL": 300,
    "Weight": -1,
    "Priority": 0,
}


def _record(**overrides):
    item = dict(RECORD)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"zone_id": ZONE_ID}
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {"record_id": RECORD_ID}
    params.update(overrides)
    return params


def _name_args(**overrides):
    params = {"name": RECORD_NAME}
    params.update(overrides)
    return params


class FakeTeoClient(object):
    """In-memory EdgeOne client mutating a small DNS-record store."""

    def __init__(self, records=None):
        self.records = [dict(t) for t in (records or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _rows(self, request):
        rows = [r for r in self.records if r.get("ZoneId") == getattr(request, "ZoneId", None)]
        for item in getattr(request, "Filters", None) or []:
            values = list(getattr(item, "Values", None) or [])
            if item.Name == "id":
                rows = [r for r in rows if r.get("RecordId") in values]
            elif item.Name == "name":
                rows = [r for r in rows if r.get("Name") in values]
        return rows

    def DescribeDnsRecords(self, request):
        self._record("DescribeDnsRecords", request)
        rows = self._rows(request)
        return SimpleNamespace(DnsRecords=[FakeResource(r) for r in rows], TotalCount=len(rows), RequestId="req-list")

    def CreateDnsRecord(self, request):
        self._record("CreateDnsRecord", request)
        self._next += 1
        row = {
            "RecordId": "record-new-%03d" % self._next,
            "ZoneId": getattr(request, "ZoneId", None),
            "Name": getattr(request, "Name", None),
            "Type": getattr(request, "Type", None),
            "Content": getattr(request, "Content", None),
            "Location": getattr(request, "Location", None),
            "TTL": getattr(request, "TTL", None),
            "Weight": getattr(request, "Weight", None),
            "Priority": getattr(request, "Priority", None),
        }
        self.records.append(row)
        return SimpleNamespace(RecordId=row["RecordId"], RequestId="req-create")

    def ModifyDnsRecords(self, request):
        self._record("ModifyDnsRecords", request)
        for item in getattr(request, "DnsRecords", None) or []:
            for row in self.records:
                if row.get("RecordId") == getattr(item, "RecordId", None):
                    for attr in ("Name", "Type", "Content", "Location", "TTL", "Weight", "Priority"):
                        if getattr(item, attr, None) is not None:
                            row[attr] = getattr(item, attr, None)
        return SimpleNamespace(RequestId="req-modify")

    def DeleteDnsRecords(self, request):
        self._record("DeleteDnsRecords", request)
        ids = list(getattr(request, "RecordIds", None) or [])
        self.records = [r for r in self.records if r.get("RecordId") not in ids]
        return SimpleNamespace(RequestId="req-delete")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_teo", lambda: (models or FakeModels(), SimpleNamespace(TeoClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)


# ---------------------------------------------------------------------------
# guards
# ---------------------------------------------------------------------------


def test_present_requires_record_type_and_content(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _base(state="present", **_name_args())
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "record_type" in payload["msg"]
    assert "content" in payload["msg"]


def test_absent_requires_identity(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "one of the following is required" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_record_is_idempotent(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _base(state="absent", **_name_args())
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["record"] is None
    assert result["msg"] == "EdgeOne DNS record is absent"
    assert [c for c, unused in fake.calls] == ["DescribeDnsRecords"]


def test_absent_deletes_record(monkeypatch):
    fake = FakeTeoClient(records=[_record()])
    _make_module(monkeypatch, fake)
    _base(state="absent", **_name_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record"] is None
    assert result["msg"] == "EdgeOne DNS record deleted"
    assert fake.records == []
    assert "DeleteDnsRecords" in [c for c, unused in fake.calls]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTeoClient(records=[_record()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", **_name_args())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record"]["RecordId"] == RECORD_ID
    assert result["msg"] == "Would delete EdgeOne DNS record"
    assert len(fake.records) == 1
    assert "DeleteDnsRecords" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_record(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        **_name_args(record_type="A", content="203.0.113.10", ttl=300),
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record"]["RecordId"].startswith("record-new-")
    assert result["record"]["Name"] == RECORD_NAME
    assert result["record"]["Content"] == "203.0.113.10"
    assert result["record"]["TTL"] == 300
    assert result["msg"] == "EdgeOne DNS record created"
    assert len(fake.records) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeDnsRecords"
    assert "CreateDnsRecord" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        **_name_args(record_type="A", content="203.0.113.10", ttl=300),
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record"] is None
    assert result["msg"] == "Would create EdgeOne DNS record"
    assert fake.records == []
    assert "CreateDnsRecord" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-record flows
# ---------------------------------------------------------------------------


def test_existing_record_no_drift_is_idempotent(monkeypatch):
    fake = FakeTeoClient(records=[_record()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        **_name_args(record_type="A", content="203.0.113.10", ttl=300),
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["record"]["RecordId"] == RECORD_ID
    assert result["msg"] == "EdgeOne DNS record is up to date"
    ops = [c for c, unused in fake.calls]
    assert "ModifyDnsRecords" not in ops


def test_update_record_content_and_ttl(monkeypatch):
    fake = FakeTeoClient(records=[_record()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        **_name_args(record_type="A", content="203.0.113.20", ttl=600),
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record"]["Content"] == "203.0.113.20"
    assert result["record"]["TTL"] == 600
    assert result["msg"] == "EdgeOne DNS record updated"
    assert "ModifyDnsRecords" in [c for c, unused in fake.calls]


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeTeoClient(records=[_record()])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        **_name_args(record_type="A", content="203.0.113.20", ttl=600),
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["record"]["Content"] == "203.0.113.10"
    assert result["msg"] == "Would update EdgeOne DNS record"
    assert fake.records[0]["Content"] == "203.0.113.10"
    assert "ModifyDnsRecords" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards / failure paths
# ---------------------------------------------------------------------------


def test_multiple_records_with_same_name_fail(monkeypatch):
    fake = FakeTeoClient(records=[_record(), _record(RecordId="record-dup", Content="203.0.113.11")])
    _make_module(monkeypatch, fake)
    _base(state="present", **_name_args(record_type="A", content="203.0.113.10"))
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Multiple EdgeOne DNS records have the requested name; use record_id" in payload["msg"]
    assert payload["name"] == RECORD_NAME


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        def get_code(self):
            return "InternalError"

        def get_request_id(self):
            return "req-boom"

    class ExplodingClient(object):
        def DescribeDnsRecords(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    # retries=0 so the retryable "InternalError" does not back off for 5s.
    _base(state="present", retries=0, **_name_args(record_type="A", content="203.0.113.10"))
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
    assert payload["error_code"] == "InternalError"
    assert payload["request_id"] == "req-boom"


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_teo_dns_record.py)
# ---------------------------------------------------------------------------

PARAMS = {
    "zone_id": "zone-x",
    "name": "api.example.com",
    "record_type": "A",
    "content": "203.0.113.10",
    "location": "Default",
    "ttl": 300,
    "weight": -1,
    "priority": 0,
}


def test_request_builders():
    models = FakeModels()
    assert mod.build_describe_request(models, "zone-x", name="api.example.com").Filters[0].Name == "name"
    assert mod.build_create_request(models, PARAMS).Content == "203.0.113.10"
    update = mod.build_update_request(models, "record-x", PARAMS)
    assert update.DnsRecords[0].RecordId == "record-x"
    assert mod.build_delete_request(models, "zone-x", "record-x").RecordIds == ["record-x"]


def test_exact_idempotency():
    desired = mod._desired(PARAMS)
    assert mod._matches(dict(desired), desired)
    changed = dict(desired)
    changed["TTL"] = 600
    assert not mod._matches(changed, desired)
