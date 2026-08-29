"""Tests for config_rule."""

from ansible_collections.susunola.tencentcloud.plugins.modules import config_rule
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels


PARAMS = {"name": "encrypted-disks", "identifier": "CBS_DISK_ENCRYPTED", "identifier_type": "SYSTEM", "resource_types": ["QCS::CBS::Disk"], "triggers": [{"message_type": "ConfigurationItemChangeNotification", "maximum_execution_frequency": None}], "risk_level": 1, "input_parameters": {"required": "true"}, "description": "Encrypted disks", "regions": ["ap-shanghai", "ap-guangzhou"], "tags": {"env": "prod"}, "excluded_resource_ids": ["disk-x"]}


def test_request_builders():
    models = FakeModels()
    create = config_rule.build_create_request(models, PARAMS)
    assert create.Identifier == "CBS_DISK_ENCRYPTED"
    assert create.InputParameter[0].ParameterKey == "required"
    update = config_rule.build_update_request(models, "rule-x", PARAMS)
    assert update.RuleId == "rule-x"
    assert config_rule.build_delete_request(models, "rule-x").RuleId == "rule-x"
    assert config_rule.build_describe_request(models, "rule-x").RuleId == "rule-x"


def test_exact_idempotency_normalizes_order():
    desired = config_rule._desired(PARAMS)
    current = dict(desired)
    current["RegionsScope"] = list(reversed(current["RegionsScope"]))
    assert config_rule._matches(current, desired)
    current["RiskLevel"] = 3
    assert not config_rule._matches(current, desired)
