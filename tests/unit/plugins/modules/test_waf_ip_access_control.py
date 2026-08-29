"""Tests for waf_ip_access_control."""

from ansible_collections.susunola.tencentcloud.plugins.modules import waf_ip_access_control
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels


def test_request_builders():
    models = FakeModels()
    params = {"rule_id": 123, "domain": "api.example.com", "action": "block", "ip_list": ["203.0.113.0/24"], "note": "abuse", "valid_until": 0, "instance_id": "waf-1", "edition": "sparta-waf"}
    create = waf_ip_access_control.build_create_request(models, params)
    assert create.ActionType == 42
    assert create.IpList == ["203.0.113.0/24"]
    update = waf_ip_access_control.build_update_request(models, params)
    assert update.RuleId == 123
    assert waf_ip_access_control.build_delete_request(models, params).Items == ["123"]
