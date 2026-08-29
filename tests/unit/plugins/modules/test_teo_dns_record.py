"""Tests for teo_dns_record."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.modules import teo_dns_record
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels

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
    assert teo_dns_record.build_describe_request(models, "zone-x", name="api.example.com").Filters[0].Name == "name"
    assert teo_dns_record.build_create_request(models, PARAMS).Content == "203.0.113.10"
    update = teo_dns_record.build_update_request(models, "record-x", PARAMS)
    assert update.DnsRecords[0].RecordId == "record-x"
    assert teo_dns_record.build_delete_request(models, "zone-x", "record-x").RecordIds == ["record-x"]


def test_exact_idempotency():
    desired = teo_dns_record._desired(PARAMS)
    assert teo_dns_record._matches(dict(desired), desired)
    changed = dict(desired)
    changed["TTL"] = 600
    assert not teo_dns_record._matches(changed, desired)
