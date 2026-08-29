"""Tests for as_scaling_group."""

from ansible_collections.susunola.tencentcloud.plugins.modules import as_scaling_group
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels


PARAMS = {"name": "web", "launch_configuration_id": "asc-x", "vpc_id": "vpc-x", "subnet_ids": ["subnet-a", "subnet-b"], "min_size": 0, "max_size": 10, "desired_capacity": 0, "default_cooldown": 300, "termination_policy": "OLDEST_INSTANCE", "retry_policy": "IMMEDIATE_RETRY", "subnet_policy": "PRIORITY", "health_check_type": "CVM", "capacity_rebalance": False, "project_id": 0}


def test_request_builders():
    models = FakeModels()
    create = as_scaling_group.build_create_request(models, PARAMS)
    assert create.DesiredCapacity == 0
    assert create.SubnetIds == ["subnet-a", "subnet-b"]
    update = as_scaling_group.build_update_request(models, "asg-x", PARAMS)
    assert update.AutoScalingGroupId == "asg-x"
    assert as_scaling_group.build_delete_request(models, "asg-x").AutoScalingGroupId == "asg-x"


def test_exact_idempotency():
    desired = as_scaling_group._desired(PARAMS)
    assert as_scaling_group._matches(dict(desired), desired)
    changed = dict(desired)
    changed["DesiredCapacity"] = 1
    assert not as_scaling_group._matches(changed, desired)
