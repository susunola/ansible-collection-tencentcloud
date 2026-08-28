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


def test_kms_alias_lookup_uses_exact_match_and_paginates(models):
    calls = []

    class Metadata(SimpleNamespace):
        def to_json_string(self):
            return '{"Alias":"%s","KeyId":"%s"}' % (self.Alias, self.KeyId)

    def list_keys(request):
        calls.append(request.Offset)
        items = (
            [Metadata(Alias="production-copy", KeyId="key-copy")]
            if request.Offset == 0
            else [Metadata(Alias="production", KeyId="key-exact")]
        )
        return SimpleNamespace(KeyMetadatas=items, TotalCount=2)

    module = SimpleNamespace(
        sdk_call=lambda method, request: method(request),
        fail_json=lambda **kwargs: pytest.fail(kwargs["msg"]),
    )
    client = SimpleNamespace(ListKeyDetail=list_keys)
    result = kms_key.find_key_by_alias(module, client, models, "production")
    assert result["KeyId"] == "key-exact"
    assert calls == [0, 1]


@pytest.mark.parametrize("enabled,request_name,rotate_days", [
    (None, "GetKeyRotationStatusRequest", None),
    (True, "EnableKeyRotationRequest", 90),
    (False, "DisableKeyRotationRequest", None),
])
def test_kms_rotation_requests(models, enabled, request_name, rotate_days):
    request = kms_key.build_rotation_request(models, "key-x", enabled, rotate_days)
    assert type(request).__name__ == request_name
    assert request.KeyId == "key-x"
    if enabled:
        assert request.RotateDays == 90


def test_kms_cancel_deletion_request(models):
    request = kms_key.build_cancel_deletion_request(models, "key-x")
    assert request.KeyId == "key-x"


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


def test_monitor_condition_update_preserves_unmanaged_event(models):
    request = monitor_alarm_policy.build_condition_request(models, {
        "module": "monitor", "name": None,
        "condition": {"IsUnionRule": 1}, "event_condition": None,
        "notice_ids": ["notice-1"],
    }, "policy-x", {
        "PolicyName": "cpu-high", "EventCondition": {"Rules": []},
    })
    assert request.PolicyName == "cpu-high"
    assert request.Condition.raw_json == '{"IsUnionRule": 1}'
    assert request.EventCondition.raw_json == '{"Rules": []}'
    assert request.NoticeIds == ["notice-1"]


def test_tke_values_are_canonical_json():
    encoded = tke_addon._raw({"b": 2, "a": 1})
    assert tke_addon._canonical_raw(encoded) == '{"a":1,"b":2}'
    assert tke_addon._canonical_raw('{"b":2,"a":1}') == '{"a":1,"b":2}'


def test_tke_install_request(models):
    request = tke_addon.build_install_request(models, {
        "cluster_id": "cls-x", "name": "cbs", "version": "1.4.0",
        "values": {"replicaCount": 2},
    })
    assert request.ClusterId == "cls-x"
    assert request.AddonName == "cbs"
    assert tke_addon._canonical_raw(request.RawValues) == '{"replicaCount":2}'


def test_tke_describe_selects_named_addon(models):
    class Addon(SimpleNamespace):
        def to_json_string(self):
            return '{"AddonName":"%s","Phase":"%s"}' % (self.AddonName, self.Phase)

    response = SimpleNamespace(Addons=[
        Addon(AddonName="cbs", Phase="Succeeded"),
        Addon(AddonName="metrics", Phase="Installing"),
    ])
    module = SimpleNamespace(sdk_call=lambda method, request: response)
    client = SimpleNamespace(DescribeAddon=lambda request: response)
    result = tke_addon.describe_addon(module, client, models, "cls-x", "metrics")
    assert result == {"AddonName": "metrics", "Phase": "Installing"}


def test_tke_waiter_surfaces_failed_phase(monkeypatch, models):
    addon = {"AddonName": "cbs", "Phase": "InstallFailed", "Reason": "bad values"}
    monkeypatch.setattr(tke_addon, "describe_addon", lambda *args: addon)
    module = SimpleNamespace(
        params={"waiter_timeout": 10, "waiter_delay": 0},
        fail_json=lambda **kwargs: (_ for _ in ()).throw(RuntimeError(kwargs["reason"])),
    )
    with pytest.raises(RuntimeError, match="bad values"):
        tke_addon.wait_for_addon(module, None, models, "cls-x", "cbs")
