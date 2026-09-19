from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)

from ansible_collections.susunola.tencentcloud.plugins.modules import ckafka_route_info


class FakeRequest:
    pass


class FakeModels:
    DescribeRouteRequest = FakeRequest


def test_build_request_sets_instance_and_route_id():
    request = ckafka_route_info.build_request(FakeModels, "ckafka-1", 42)
    assert request.InstanceId == "ckafka-1"
    assert request.RouteId == 42


def test_matches_route_by_observable_network_identity():
    route = {"RouteId": 42, "VipType": 3, "AccessType": 3, "VpcId": "vpc-1", "Subnet": "subnet-1"}
    assert ckafka_route_info.matches(route, network_type=3, access_type=3, vpc_id="vpc-1", subnet_id="subnet-1")
    assert not ckafka_route_info.matches(route, subnet_id="subnet-2")


def test_matches_route_id_normalizes_sdk_value():
    assert ckafka_route_info.matches({"RouteId": "42"}, route_id=42)
