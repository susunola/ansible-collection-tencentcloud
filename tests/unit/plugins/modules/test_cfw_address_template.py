"""Tests for cfw_address_template."""

from ansible_collections.susunola.tencentcloud.plugins.modules import cfw_address_template
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels


PARAMS = {"name": "trusted", "description": "internal", "addresses": ["192.168.0.0/16", "10.0.0.0/8"], "template_type": "ip", "ip_version": 0}


def test_request_builders_and_normalization():
    models = FakeModels()
    create = cfw_address_template.build_create_request(models, PARAMS)
    assert create.IpString == "10.0.0.0/8,192.168.0.0/16"
    update = cfw_address_template.build_update_request(models, "uuid-x", PARAMS)
    assert update.Uuid == "uuid-x"
    assert cfw_address_template.build_delete_request(models, "uuid-x").Uuid == "uuid-x"
    assert cfw_address_template.build_describe_request(models, name="trusted").SearchValue == "trusted"


def test_exact_idempotency():
    desired = cfw_address_template._desired(PARAMS)
    assert cfw_address_template._matches(dict(desired), desired)
    changed = dict(desired)
    changed["Detail"] = "external"
    assert not cfw_address_template._matches(changed, desired)
