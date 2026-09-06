"""Main-path unit tests for the tke_cluster_kubeconfig module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tke_cluster_kubeconfig
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    module_args,
    run,
)

KUBECONFIG = "apiVersion: v1\nclusters: []\n"


class FakeTkeClient(object):
    def __init__(self, kubeconfig=KUBECONFIG):
        self.kubeconfig = kubeconfig
        self.DescribeClusterKubeconfig = MagicMock(side_effect=self._describe)

    def _describe(self, request):
        return SimpleNamespace(Kubeconfig=self.kubeconfig, RequestId="req-fake")


@pytest.fixture
def client(monkeypatch):
    fake = FakeTkeClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        tke_cluster_kubeconfig, "_load_tke",
        lambda: (FakeModels(), SimpleNamespace(TkeClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_returns_kubeconfig_without_dest(client):
    module_args(cluster_id="cls-xxxxxxxx")
    result = run(tke_cluster_kubeconfig.run_module)
    assert result["changed"] is False
    assert result["kubeconfig"] == KUBECONFIG
    assert result["cluster_id"] == "cls-xxxxxxxx"
    assert result["is_extranet"] is False
    client.DescribeClusterKubeconfig.assert_called_once()
    request = client.DescribeClusterKubeconfig.call_args[0][0]
    assert request.ClusterId == "cls-xxxxxxxx"
    assert request.IsExtranet is False


def test_writes_dest_with_0600(client, tmp_path):
    dest = str(tmp_path / "kube.config")
    module_args(cluster_id="cls-xxxxxxxx", is_extranet=True, dest=dest)
    result = run(tke_cluster_kubeconfig.run_module)
    assert result["changed"] is True
    assert result["dest"] == dest
    assert "kubeconfig" not in result
    with open(dest) as handle:
        assert handle.read() == KUBECONFIG
    assert os.stat(dest).st_mode & 0o777 == 0o600
    request = client.DescribeClusterKubeconfig.call_args[0][0]
    assert request.IsExtranet is True


def test_second_run_is_idempotent(client, tmp_path):
    dest = str(tmp_path / "kube.config")
    with open(dest, "w") as handle:
        handle.write(KUBECONFIG)
    module_args(cluster_id="cls-xxxxxxxx", dest=dest)
    result = run(tke_cluster_kubeconfig.run_module)
    assert result["changed"] is False
    assert "diff" not in result


def test_updates_drifted_dest_and_normalizes_permissions(client, tmp_path):
    dest = str(tmp_path / "kube.config")
    with open(dest, "w") as handle:
        handle.write("stale")
    os.chmod(dest, 0o644)
    module_args(cluster_id="cls-xxxxxxxx", dest=dest)
    result = run(tke_cluster_kubeconfig.run_module)
    assert result["changed"] is True
    with open(dest) as handle:
        assert handle.read() == KUBECONFIG
    assert os.stat(dest).st_mode & 0o777 == 0o600


def test_check_mode_does_not_write(client, tmp_path):
    dest = str(tmp_path / "kube.config")
    module_args(cluster_id="cls-xxxxxxxx", dest=dest, _ansible_check_mode=True)
    result = run(tke_cluster_kubeconfig.run_module)
    assert result["changed"] is True
    assert "diff" in result
    assert not os.path.exists(dest)


def test_diff_mode_reports_hashes_not_content(client, tmp_path):
    dest = str(tmp_path / "kube.config")
    module_args(cluster_id="cls-xxxxxxxx", dest=dest, _ansible_diff=True)
    result = run(tke_cluster_kubeconfig.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"] is None
    assert "sha256" in result["diff"]["after"]
    assert KUBECONFIG not in str(result["diff"])
