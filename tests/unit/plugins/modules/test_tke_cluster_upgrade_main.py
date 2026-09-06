"""Main-path unit tests for the tke_cluster_upgrade module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tke_cluster_upgrade
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CLUSTER_ID = "cls-12345678"
OLD_VERSION = "1.26.1"
NEW_VERSION = "1.28.5"


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
    """In-memory stand-in for the TkeClient upgrade operations."""

    def __init__(self, version=OLD_VERSION):
        self.version = version
        self.UpdateClusterVersion = MagicMock(side_effect=self._update)

    def DescribeClusters(self, request):
        assert request.ClusterIds == [CLUSTER_ID]
        cluster = FakeResource({"ClusterId": CLUSTER_ID, "ClusterVersion": self.version})
        return SimpleNamespace(Clusters=[cluster])

    def _update(self, request):
        self.version = request.DstVersion
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeTkeClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        tke_cluster_upgrade, "_load_tke",
        lambda: (FakeModels(), SimpleNamespace(TkeClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_upgrade_submits_when_version_differs(client):
    module_args(cluster_id=CLUSTER_ID, version=NEW_VERSION)
    result = run(tke_cluster_upgrade.run_module)
    assert result["changed"] is True
    assert result["current_version"] == OLD_VERSION
    assert result["desired_version"] == NEW_VERSION
    assert client.version == NEW_VERSION
    client.UpdateClusterVersion.assert_called_once()
    request = client.UpdateClusterVersion.call_args[0][0]
    assert request.ClusterId == CLUSTER_ID
    assert request.DstVersion == NEW_VERSION


def test_no_change_when_already_on_version(client):
    client.version = NEW_VERSION
    module_args(cluster_id=CLUSTER_ID, version=NEW_VERSION)
    result = run(tke_cluster_upgrade.run_module)
    assert result["changed"] is False
    assert result["current_version"] == NEW_VERSION
    client.UpdateClusterVersion.assert_not_called()


def test_check_mode_reports_change_without_writing(client):
    module_args(
        cluster_id=CLUSTER_ID, version=NEW_VERSION,
        _ansible_check_mode=True,
    )
    result = run(tke_cluster_upgrade.run_module)
    assert result["changed"] is True
    assert client.version == OLD_VERSION
    client.UpdateClusterVersion.assert_not_called()


def test_passes_tuning_options(client):
    module_args(
        cluster_id=CLUSTER_ID, version=NEW_VERSION,
        max_not_ready_percent=10.0, skip_pre_check=True,
    )
    run(tke_cluster_upgrade.run_module)
    request = client.UpdateClusterVersion.call_args[0][0]
    assert request.MaxNotReadyPercent == 10.0
    assert request.SkipPreCheck is True


def test_zero_tuning_defaults_are_passed(client):
    module_args(cluster_id=CLUSTER_ID, version=NEW_VERSION)
    run(tke_cluster_upgrade.run_module)
    request = client.UpdateClusterVersion.call_args[0][0]
    # unset (falsy) float option is left untouched; SkipPreCheck is always written
    assert getattr(request, "MaxNotReadyPercent", None) is None
    assert request.SkipPreCheck is False


def test_cluster_not_found_fails(client, monkeypatch):
    monkeypatch.setattr(
        tke_cluster_upgrade, "find_cluster",
        lambda module, client, models, cluster_id: None,
    )
    module_args(cluster_id=CLUSTER_ID, version=NEW_VERSION)
    with pytest.raises(AnsibleFailJson) as exc:
        run(tke_cluster_upgrade.run_module)
    assert "not found" in exc.value.args[0]["msg"]
    client.UpdateClusterVersion.assert_not_called()


def test_sdk_error_fails(client, monkeypatch):
    def boom(self, fn, request, **kwargs):
        raise FakeSdkError("InternalError")

    monkeypatch.setattr(TencentCloudModule, "sdk_call", boom)
    module_args(cluster_id=CLUSTER_ID, version=NEW_VERSION)
    with pytest.raises(AnsibleFailJson) as exc:
        run(tke_cluster_upgrade.run_module)
    assert exc.value.args[0]["failed"] is True
