"""Tests for ccn."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.modules import ccn
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels


def test_request_builders():
    models = FakeModels()
    params = {
        "name": "backbone",
        "description": "prod",
        "qos_level": "AU",
        "instance_charge_type": "POSTPAID",
        "bandwidth_limit_type": None,
        "route_ecmp": True,
        "route_overlap": False,
        "traffic_marking_policy": True,
        "tags": {"env": "prod"},
    }
    create = ccn.build_create_request(models, params)
    assert create.CcnName == "backbone"
    assert create.Tags[0].Key == "env"
    update = ccn.build_update_request(models, "ccn-1", params)
    assert update.RouteECMPFlag is True
    assert ccn.build_delete_request(models, "ccn-1").CcnId == "ccn-1"
