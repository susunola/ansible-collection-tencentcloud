"""Tests for ccn_attachment."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.modules import ccn_attachment
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels


def test_build_requests():
    models = FakeModels()
    params = {
        "ccn_id": "ccn-1",
        "instance_id": "vpc-1",
        "instance_region": "ap-guangzhou",
        "instance_type": "VPC",
        "description": "prod",
        "route_table_id": None,
    }
    instance = ccn_attachment.build_instance(models, params)
    assert instance.InstanceId == "vpc-1"
    request = ccn_attachment.build_mutation_request(models, params, models.AttachCcnInstancesRequest)
    assert request.CcnId == "ccn-1"
    assert request.Instances[0].Description == "prod"
