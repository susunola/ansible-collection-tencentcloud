"""Main-path unit tests for the tcr_namespace module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tcr_namespace
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

NAMESPACE = {
    "Name": "team-a",
    "CreationTime": "2026-08-28 10:00:00",
    "RepoCount": 0,
    "Public": False,
    "NamespaceId": "ns-xxxxxxxx",
    "AutoScan": False,
    "PreventVUL": False,
    "Severity": "",
}


class FakeTcrClient(object):
    def __init__(self, namespace=None):
        self.namespace = dict(namespace) if namespace else None
        self.CreateNamespace = MagicMock(side_effect=self._create)
        self.ModifyNamespace = MagicMock(side_effect=self._modify)
        self.DeleteNamespace = MagicMock(side_effect=self._delete)

    def DescribeNamespaces(self, request):
        items = []
        if self.namespace and (not request.NamespaceName
                               or request.NamespaceName == self.namespace["Name"]):
            items = [self.namespace]
        return SimpleNamespace(NamespaceList=[FakeResource(s) for s in items],
                               TotalCount=len(items))

    def _create(self, request):
        self.namespace = {
            "Name": request.NamespaceName,
            "Public": request.IsPublic,
            "AutoScan": getattr(request, "IsAutoScan", False),
            "PreventVUL": getattr(request, "IsPreventVUL", False),
            "Severity": getattr(request, "Severity", "") or "",
        }
        return SimpleNamespace()

    def _modify(self, request):
        if request.IsPublic is not None:
            self.namespace["Public"] = request.IsPublic
        if getattr(request, "IsAutoScan", None) is not None:
            self.namespace["AutoScan"] = request.IsAutoScan
        if getattr(request, "IsPreventVUL", None) is not None:
            self.namespace["PreventVUL"] = request.IsPreventVUL
        if getattr(request, "Severity", None) is not None:
            self.namespace["Severity"] = request.Severity
        return SimpleNamespace()

    def _delete(self, request):
        self.namespace = None
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeTcrClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        tcr_namespace, "_load_tcr",
        lambda: (FakeModels(), SimpleNamespace(TcrClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_creates_private_namespace(client):
    module_args(registry_id="tcr-xxxxxxxx", name="team-a")
    result = run(tcr_namespace.run_module)
    assert result["changed"] is True
    assert result["msg"] == "TCR namespace created"
    client.CreateNamespace.assert_called_once()
    request = client.CreateNamespace.call_args[0][0]
    assert request.RegistryId == "tcr-xxxxxxxx"
    assert request.NamespaceName == "team-a"
    assert request.IsPublic is False


def test_second_run_is_idempotent(client):
    client.namespace = dict(NAMESPACE)
    module_args(registry_id="tcr-xxxxxxxx", name="team-a")
    result = run(tcr_namespace.run_module)
    assert result["changed"] is False
    assert result["msg"] == "TCR namespace is up to date"
    client.CreateNamespace.assert_not_called()
    client.ModifyNamespace.assert_not_called()


def test_public_drift_triggers_update(client):
    client.namespace = dict(NAMESPACE)
    module_args(registry_id="tcr-xxxxxxxx", name="team-a", is_public=True)
    result = run(tcr_namespace.run_module)
    assert result["changed"] is True
    assert result["msg"] == "TCR namespace settings updated"
    client.ModifyNamespace.assert_called_once()
    assert client.ModifyNamespace.call_args[0][0].IsPublic is True
    assert result["namespace"]["Public"] is True


def test_security_settings_drift_triggers_update(client):
    client.namespace = dict(NAMESPACE)
    module_args(registry_id="tcr-xxxxxxxx", name="team-a",
                is_auto_scan=True, is_prevent_vul=True, severity="high")
    result = run(tcr_namespace.run_module)
    assert result["changed"] is True
    request = client.ModifyNamespace.call_args[0][0]
    assert request.IsAutoScan is True
    assert request.IsPreventVUL is True
    assert request.Severity == "high"
    assert result["namespace"]["PreventVUL"] is True


def test_absent_deletes(client):
    client.namespace = dict(NAMESPACE)
    module_args(registry_id="tcr-xxxxxxxx", name="team-a", state="absent")
    result = run(tcr_namespace.run_module)
    assert result["changed"] is True
    assert result["msg"] == "TCR namespace deleted"
    assert result["namespace"] is None
    client.DeleteNamespace.assert_called_once()
    request = client.DeleteNamespace.call_args[0][0]
    assert request.RegistryId == "tcr-xxxxxxxx"
    assert request.NamespaceName == "team-a"


def test_absent_already_absent(client):
    module_args(registry_id="tcr-xxxxxxxx", name="team-a", state="absent")
    result = run(tcr_namespace.run_module)
    assert result["changed"] is False
    assert result["msg"] == "TCR namespace already absent"
    client.DeleteNamespace.assert_not_called()


def test_check_mode_create_does_not_write(client):
    module_args(_ansible_check_mode=True, registry_id="tcr-xxxxxxxx", name="team-a")
    result = run(tcr_namespace.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create TCR namespace"
    client.CreateNamespace.assert_not_called()


def test_check_mode_update_does_not_write(client):
    client.namespace = dict(NAMESPACE)
    module_args(_ansible_check_mode=True, registry_id="tcr-xxxxxxxx",
                name="team-a", is_public=True)
    result = run(tcr_namespace.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update TCR namespace settings"
    client.ModifyNamespace.assert_not_called()


def test_fails_without_registry_id(client):
    module_args(name="team-a")
    with pytest.raises(AnsibleFailJson) as exc:
        run(tcr_namespace.run_module)
    assert "registry_id" in exc.value.args[0]["msg"]
