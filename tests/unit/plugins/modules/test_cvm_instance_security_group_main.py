"""Main-path unit tests for the cvm_instance_security_group module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cvm_instance_security_group
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "ins-12345678"
SG_A = "sg-aaaaaaaa"
SG_B = "sg-bbbbbbbb"
SG_C = "sg-cccccccc"


class FakeSdkError(Exception):
    def __init__(self, code, request_id="req-fake"):
        super(FakeSdkError, self).__init__(code)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


class FakeCvmClient(object):
    """In-memory stand-in for the CvmClient security-group operations."""

    def __init__(self, instances=None):
        # instance_id -> set of security group ids
        self.instances = dict(instances or {})
        self.describe_error = None
        self.AssociateSecurityGroups = MagicMock(side_effect=self._associate)
        self.DisassociateSecurityGroups = MagicMock(side_effect=self._disassociate)

    def DescribeInstances(self, request):
        if self.describe_error is not None:
            raise self.describe_error
        instance_id = request.InstanceIds[0]
        groups = sorted(self.instances.get(instance_id, []))
        if not self.instances.get(instance_id):
            # distinguish a missing instance from one with no groups
            if instance_id not in self.instances:
                return SimpleNamespace(InstanceSet=[])
        value = {"InstanceId": instance_id, "SecurityGroupIds": groups}
        return SimpleNamespace(InstanceSet=[FakeResource(value)])

    def _associate(self, request):
        instance_id = request.InstanceIds[0]
        self.instances.setdefault(instance_id, set()).update(request.SecurityGroupIds)

    def _disassociate(self, request):
        instance_id = request.InstanceIds[0]
        self.instances.setdefault(instance_id, set()).difference_update(request.SecurityGroupIds)


@pytest.fixture
def client(monkeypatch):
    fake = FakeCvmClient(instances={INSTANCE_ID: {SG_A}})
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        cvm_instance_security_group, "_load_cvm",
        lambda: (FakeModels(), SimpleNamespace(CvmClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_present_binds_missing_groups(client):
    module_args(
        state="present", instance_id=INSTANCE_ID,
        security_group_ids=[SG_A, SG_B],
    )
    result = run(cvm_instance_security_group.run_module)
    assert result["changed"] is True
    assert result["security_group_ids"] == [SG_A, SG_B]
    client.AssociateSecurityGroups.assert_called_once()
    request = client.AssociateSecurityGroups.call_args[0][0]
    assert request.InstanceIds == [INSTANCE_ID]
    assert request.SecurityGroupIds == [SG_B]


def test_present_unbinds_extra_groups(client):
    client.instances[INSTANCE_ID] = {SG_A, SG_B}
    module_args(
        state="present", instance_id=INSTANCE_ID,
        security_group_ids=[SG_A],
    )
    result = run(cvm_instance_security_group.run_module)
    assert result["changed"] is True
    assert result["security_group_ids"] == [SG_A]
    client.AssociateSecurityGroups.assert_not_called()
    client.DisassociateSecurityGroups.assert_called_once()
    request = client.DisassociateSecurityGroups.call_args[0][0]
    assert request.SecurityGroupIds == [SG_B]


def test_present_binds_and_unbinds(client):
    client.instances[INSTANCE_ID] = {SG_A, SG_B}
    module_args(
        state="present", instance_id=INSTANCE_ID,
        security_group_ids=[SG_B, SG_C],
    )
    result = run(cvm_instance_security_group.run_module)
    assert result["changed"] is True
    assert result["security_group_ids"] == [SG_B, SG_C]
    bind_request = client.AssociateSecurityGroups.call_args[0][0]
    assert bind_request.SecurityGroupIds == [SG_C]
    unbind_request = client.DisassociateSecurityGroups.call_args[0][0]
    assert unbind_request.SecurityGroupIds == [SG_A]


def test_present_unchanged(client):
    module_args(
        state="present", instance_id=INSTANCE_ID,
        security_group_ids=[SG_A],
    )
    result = run(cvm_instance_security_group.run_module)
    assert result["changed"] is False
    assert result["security_group_ids"] == [SG_A]
    client.AssociateSecurityGroups.assert_not_called()
    client.DisassociateSecurityGroups.assert_not_called()


def test_absent_unbinds_given_groups(client):
    client.instances[INSTANCE_ID] = {SG_A, SG_B}
    module_args(
        state="absent", instance_id=INSTANCE_ID,
        security_group_ids=[SG_A],
    )
    result = run(cvm_instance_security_group.run_module)
    assert result["changed"] is True
    assert result["security_group_ids"] == [SG_B]
    client.DisassociateSecurityGroups.assert_called_once()
    request = client.DisassociateSecurityGroups.call_args[0][0]
    assert request.SecurityGroupIds == [SG_A]


def test_absent_unchanged_when_not_bound(client):
    module_args(
        state="absent", instance_id=INSTANCE_ID,
        security_group_ids=[SG_B],
    )
    result = run(cvm_instance_security_group.run_module)
    assert result["changed"] is False
    assert result["security_group_ids"] == [SG_A]
    client.DisassociateSecurityGroups.assert_not_called()


def test_check_mode_reports_without_writes(client):
    module_args(
        state="present", instance_id=INSTANCE_ID,
        security_group_ids=[SG_A, SG_B],
        _ansible_check_mode=True,
    )
    result = run(cvm_instance_security_group.run_module)
    assert result["changed"] is True
    assert result["security_group_ids"] == [SG_A, SG_B]
    assert "Would bind" in result["msg"]
    client.AssociateSecurityGroups.assert_not_called()
    client.DisassociateSecurityGroups.assert_not_called()


def test_check_mode_absent(client):
    client.instances[INSTANCE_ID] = {SG_A, SG_B}
    module_args(
        state="absent", instance_id=INSTANCE_ID,
        security_group_ids=[SG_A],
        _ansible_check_mode=True,
    )
    result = run(cvm_instance_security_group.run_module)
    assert result["changed"] is True
    assert result["security_group_ids"] == [SG_B]
    assert "Would unbind" in result["msg"]
    client.DisassociateSecurityGroups.assert_not_called()


def test_instance_not_found_fails(client):
    module_args(
        state="present", instance_id="ins-missing",
        security_group_ids=[SG_A],
    )
    with pytest.raises(AnsibleFailJson) as excinfo:
        run(cvm_instance_security_group.run_module)
    assert "was not found" in excinfo.value.args[0]["msg"]


def test_empty_security_group_ids_fails(client):
    module_args(
        state="present", instance_id=INSTANCE_ID,
        security_group_ids=[],
    )
    with pytest.raises(AnsibleFailJson) as excinfo:
        run(cvm_instance_security_group.run_module)
    assert "must not be empty" in excinfo.value.args[0]["msg"]


def test_more_than_five_groups_fails(client):
    module_args(
        state="present", instance_id=INSTANCE_ID,
        security_group_ids=["sg-%07d" % i for i in range(6)],
    )
    with pytest.raises(AnsibleFailJson) as excinfo:
        run(cvm_instance_security_group.run_module)
    assert "at most five" in excinfo.value.args[0]["msg"]


def test_sdk_error_fails(client):
    client.describe_error = FakeSdkError("AuthFailure")
    module_args(
        state="present", instance_id=INSTANCE_ID,
        security_group_ids=[SG_A],
    )
    with pytest.raises(AnsibleFailJson) as excinfo:
        run(cvm_instance_security_group.run_module)
    payload = excinfo.value.args[0]
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-fake"
