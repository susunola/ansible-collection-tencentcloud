"""Tests for clb_target_group."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import clb_target_group
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels, module_args, run


def test_builders_and_member_normalization():
    models = FakeModels()
    params = {
        "name": "api",
        "vpc_id": "vpc-1",
        "type": "v2",
        "protocol": "HTTP",
        "port": 8080,
        "schedule_algorithm": "WRR",
        "weight": 10,
        "tags": {"env": "prod"},
    }
    request = clb_target_group.build_create_request(models, params)
    assert request.TargetGroupName == "api"
    assert request.Tags[0].TagKey == "env"
    members = clb_target_group._members([{"BindIP": "10.0.0.1", "Port": 8080, "Weight": 20}])
    assert members == [{"ip": "10.0.0.1", "port": 8080, "weight": 20}]


def test_create_main_path(monkeypatch):
    models = FakeModels()
    client = SimpleNamespace(CreateTargetGroup=MagicMock(return_value=SimpleNamespace(TargetGroupId="lbtg-1")))
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(clb_target_group, "_load_clb", lambda: (models, SimpleNamespace(ClbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, cls, endpoint: client)
    monkeypatch.setattr(clb_target_group, "find_group", lambda *args: None)
    monkeypatch.setattr(clb_target_group, "wait_for_group", MagicMock(return_value={"TargetGroupId": "lbtg-1"}))
    module_args(state="present", name="api", vpc_id="vpc-1", protocol="HTTP", port=8080)
    result = run(clb_target_group.run_module)
    assert result["changed"] is True
    assert result["target_group"]["TargetGroupId"] == "lbtg-1"
    client.CreateTargetGroup.assert_called_once()


def test_check_mode_create_does_not_write(monkeypatch):
    models = FakeModels()
    client = SimpleNamespace(CreateTargetGroup=MagicMock())
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(clb_target_group, "_load_clb", lambda: (models, SimpleNamespace(ClbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, cls, endpoint: client)
    monkeypatch.setattr(clb_target_group, "find_group", lambda *args: None)
    module_args(state="present", name="api", vpc_id="vpc-1", protocol="HTTP", port=8080, _ansible_check_mode=True)
    result = run(clb_target_group.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.CreateTargetGroup.assert_not_called()
