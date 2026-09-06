"""Main-path unit tests for the tke_cluster_autoscaler module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tke_cluster_autoscaler
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CLUSTER_ID = "cls-12345678"


class FakeSdkError(Exception):
    def __init__(self, code, request_id="req-fake"):
        super(FakeSdkError, self).__init__(code)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


class FakeTkeClient(object):
    """In-memory stand-in for the TkeClient autoscaler-option operations."""

    def __init__(self, options=None):
        self.options = dict(options or {})
        self.ModifyClusterAsGroupOptionAttribute = MagicMock(side_effect=self._modify)

    def DescribeClusterAsGroupOption(self, request):
        assert request.ClusterId == CLUSTER_ID
        option = FakeResource(dict(self.options))
        return SimpleNamespace(ClusterAsGroupOption=option)

    def _modify(self, request):
        incoming = request.ClusterAsGroupOption
        merged = dict(self.options)
        for key, value in incoming.__dict__.items():
            if key.startswith("_"):
                key = key[1:]
            if value is not None:
                merged[key] = value
        self.options = merged
        return SimpleNamespace()


BASE_CURRENT = {
    "IsScaleDownEnabled": True,
    "Expander": "random",
    "ScaleDownUnneededTime": 10,
    "ScaleDownUtilizationThreshold": 50,
}


@pytest.fixture
def client(monkeypatch):
    fake = FakeTkeClient(options=BASE_CURRENT)
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        tke_cluster_autoscaler, "_load_tke",
        lambda: (FakeModels(), SimpleNamespace(TkeClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_no_change_when_options_match(client):
    module_args(
        cluster_id=CLUSTER_ID,
        is_scale_down_enabled=True,
        expander="random",
    )
    result = run(tke_cluster_autoscaler.run_module)
    assert result["changed"] is False
    client.ModifyClusterAsGroupOptionAttribute.assert_not_called()


def test_updates_changed_field(client):
    module_args(
        cluster_id=CLUSTER_ID,
        scale_down_unneeded_time=20,
    )
    result = run(tke_cluster_autoscaler.run_module)
    assert result["changed"] is True
    request = client.ModifyClusterAsGroupOptionAttribute.call_args[0][0]
    assert request.ClusterId == CLUSTER_ID
    assert request.ClusterAsGroupOption.ScaleDownUnneededTime == 20


def test_unset_params_are_ignored(client):
    module_args(
        cluster_id=CLUSTER_ID,
        scale_down_unneeded_time=20,
    )
    run(tke_cluster_autoscaler.run_module)
    request = client.ModifyClusterAsGroupOptionAttribute.call_args[0][0]
    option = request.ClusterAsGroupOption
    # only the provided field travels in the write
    assert option.ScaleDownUnneededTime == 20
    assert getattr(option, "IsScaleDownEnabled", None) is None
    assert getattr(option, "Expander", None) is None


def test_multiple_fields_diff(client):
    module_args(
        cluster_id=CLUSTER_ID,
        is_scale_down_enabled=False,
        scale_down_utilization_threshold=35,
        _ansible_diff=True,
    )
    result = run(tke_cluster_autoscaler.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"]["IsScaleDownEnabled"] is True
    assert result["diff"]["after"]["IsScaleDownEnabled"] is False
    assert result["diff"]["before"]["ScaleDownUtilizationThreshold"] == 50
    assert result["diff"]["after"]["ScaleDownUtilizationThreshold"] == 35


def test_check_mode_reports_without_writing(client):
    module_args(
        cluster_id=CLUSTER_ID,
        expander="least-waste",
        _ansible_check_mode=True,
    )
    result = run(tke_cluster_autoscaler.run_module)
    assert result["changed"] is True
    client.ModifyClusterAsGroupOptionAttribute.assert_not_called()


def test_updates_when_current_option_empty(client):
    client.options = {}
    module_args(cluster_id=CLUSTER_ID, is_scale_down_enabled=True)
    result = run(tke_cluster_autoscaler.run_module)
    assert result["changed"] is True
    request = client.ModifyClusterAsGroupOptionAttribute.call_args[0][0]
    assert request.ClusterAsGroupOption.IsScaleDownEnabled is True


def test_invalid_expander_choice_fails(client):
    module_args(cluster_id=CLUSTER_ID, expander="bogus")
    with pytest.raises(AnsibleFailJson):
        run(tke_cluster_autoscaler.run_module)
    client.ModifyClusterAsGroupOptionAttribute.assert_not_called()


def test_sdk_error_fails(client, monkeypatch):
    def boom(self, fn, request, **kwargs):
        raise FakeSdkError("InternalError")

    monkeypatch.setattr(TencentCloudModule, "sdk_call", boom)
    module_args(cluster_id=CLUSTER_ID, is_scale_down_enabled=False)
    with pytest.raises(AnsibleFailJson) as exc:
        run(tke_cluster_autoscaler.run_module)
    assert exc.value.args[0]["failed"] is True
