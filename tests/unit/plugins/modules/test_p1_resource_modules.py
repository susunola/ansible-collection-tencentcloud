"""Unit tests for the P1 resource-module request and comparison helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import cam_policy_attachment
from ansible_collections.susunola.tencentcloud.plugins.modules import kms_key
from ansible_collections.susunola.tencentcloud.plugins.modules import monitor_alarm_policy
from ansible_collections.susunola.tencentcloud.plugins.modules import tcr_repository
from ansible_collections.susunola.tencentcloud.plugins.modules import tke_addon


class Request(object):
    def from_json_string(self, value):
        self.raw_json = value


class Models(object):
    def __getattr__(self, name):
        return type(name, (Request,), {})


@pytest.fixture
def models():
    return Models()


def test_tcr_repository_create_request(models):
    request = tcr_repository.build_create_request(models, {
        "registry_id": "tcr-x", "namespace": "prod", "name": "api",
        "brief_description": "API", "description": "Production API",
    })
    assert request.RegistryId == "tcr-x"
    assert request.NamespaceName == "prod"
    assert request.RepositoryName == "api"


@pytest.mark.parametrize("kind,id_value,name,attribute", [
    ("user", 1001, None, "AttachUin"),
    ("role", 2, "deploy", "AttachRoleId"),
    ("group", 3, None, "AttachGroupId"),
])
def test_cam_attach_request_for_each_target(models, kind, id_value, name, attribute):
    params = {"target_type": kind, "target_id": id_value, "target_name": name, "policy_id": 9}
    request = cam_policy_attachment.build_mutation_request(models, params, True)
    assert request.PolicyId == 9
    expected = str(id_value) if kind == "role" else id_value
    assert getattr(request, attribute) == expected


def test_cam_detach_role_can_use_name(models):
    request = cam_policy_attachment.build_mutation_request(models, {
        "target_type": "role", "target_id": None,
        "target_name": "deploy", "policy_id": 9,
    }, False)
    assert request.DetachRoleName == "deploy"


def test_cam_attachment_detection():
    module = SimpleNamespace(sdk_call=lambda method, request: method(request))
    client = SimpleNamespace(
        ListAttachedUserPolicies=lambda request: SimpleNamespace(
            List=[SimpleNamespace(PolicyId=9)]
        )
    )
    params = {"target_type": "user", "target_id": 1001, "target_name": None, "policy_id": 9}
    assert cam_policy_attachment.is_attached(module, client, Models(), params) is True


def test_cam_attachment_detection_paginates():
    calls = []

    def list_policies(request):
        calls.append(request.Page)
        policies = [SimpleNamespace(PolicyId=1)] if request.Page == 1 else [SimpleNamespace(PolicyId=9)]
        return SimpleNamespace(List=policies, TotalNum=201)

    module = SimpleNamespace(sdk_call=lambda method, request: method(request))
    client = SimpleNamespace(ListAttachedUserPolicies=list_policies)
    params = {"target_type": "user", "target_id": 1001, "target_name": None, "policy_id": 9}
    assert cam_policy_attachment.is_attached(module, client, Models(), params) is True
    assert calls == [1, 2]


def test_kms_create_request(models):
    request = kms_key.build_create_request(models, {
        "alias": "production", "description": "Data key",
        "key_usage": "ENCRYPT_DECRYPT", "key_type": 1,
    })
    assert request.Alias == "production"
    assert request.KeyUsage == "ENCRYPT_DECRYPT"
    assert request.Type == 1


def test_monitor_create_request_maps_conditions(models):
    request = monitor_alarm_policy.build_create_request(models, {
        "module": "monitor", "name": "cpu-high", "monitor_type": "MT_QCE",
        "namespace": "QCE/CVM", "remark": "CPU", "enabled": True,
        "condition": {"IsUnionRule": 0}, "event_condition": None,
        "notice_ids": ["notice-1"],
    })
    assert request.PolicyName == "cpu-high"
    assert request.Enable == 1
    assert request.Condition.raw_json == '{"IsUnionRule": 0}'


def test_tke_values_are_canonical_json():
    assert tke_addon._raw({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    assert tke_addon._raw('{"b":2,"a":1}') == '{"a":1,"b":2}'


def test_tke_install_request(models):
    request = tke_addon.build_install_request(models, {
        "cluster_id": "cls-x", "name": "cbs", "version": "1.4.0",
        "values": {"replicaCount": 2},
    })
    assert request.ClusterId == "cls-x"
    assert request.AddonName == "cbs"
    assert request.RawValues == '{"replicaCount":2}'
