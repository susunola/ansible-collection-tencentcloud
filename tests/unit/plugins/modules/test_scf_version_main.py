"""Main-path unit tests for the scf_version module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import scf_version
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

VERSION = {
    "Version": "2",
    "Description": "Deployed by ansible",
    "AddTime": "2026-08-28 10:00:00",
    "ModTime": "2026-08-28 10:00:00",
    "Status": "Active",
}


class FakeScfClient(object):
    def __init__(self, version=None):
        self.version = dict(version) if version else None
        self.PublishVersion = MagicMock(side_effect=self._publish)
        self.DeleteFunctionVersion = MagicMock(side_effect=self._delete)

    def ListVersionByFunction(self, request):
        items = []
        if self.version:
            items = [self.version]
        return SimpleNamespace(Versions=[FakeResource(s) for s in items],
                               TotalCount=len(items))

    def _publish(self, request):
        self.version = {
            "Version": "2",
            "Description": getattr(request, "Description", "") or "",
            "Status": "Active",
        }
        return SimpleNamespace(FunctionVersion="2")

    def _delete(self, request):
        self.version = None
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeScfClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        scf_version, "_load_scf",
        lambda: (FakeModels(), SimpleNamespace(ScfClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_publishes_version(client):
    module_args(function_name="my-func", version="2",
                description="Deployed by ansible")
    result = run(scf_version.run_module)
    assert result["changed"] is True
    assert result["msg"] == "SCF version published"
    client.PublishVersion.assert_called_once()
    request = client.PublishVersion.call_args[0][0]
    assert request.FunctionName == "my-func"
    assert request.Description == "Deployed by ansible"
    assert result["version"]["Version"] == "2"


def test_second_run_is_idempotent(client):
    client.version = dict(VERSION)
    module_args(function_name="my-func", version="2")
    result = run(scf_version.run_module)
    assert result["changed"] is False
    assert result["msg"] == "SCF version already exists"
    client.PublishVersion.assert_not_called()


def test_absent_deletes(client):
    client.version = dict(VERSION)
    module_args(function_name="my-func", version="2", state="absent")
    result = run(scf_version.run_module)
    assert result["changed"] is True
    assert result["msg"] == "SCF version deleted"
    assert result["version"] is None
    request = client.DeleteFunctionVersion.call_args[0][0]
    assert request.Qualifier == "2"


def test_absent_already_absent(client):
    module_args(function_name="my-func", version="2", state="absent")
    result = run(scf_version.run_module)
    assert result["changed"] is False
    assert result["msg"] == "SCF version already absent"
    client.DeleteFunctionVersion.assert_not_called()


def test_check_mode_publish_does_not_write(client):
    module_args(_ansible_check_mode=True, function_name="my-func", version="2")
    result = run(scf_version.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would publish SCF version"
    client.PublishVersion.assert_not_called()


def test_force_delete_sets_flag(client):
    client.version = dict(VERSION)
    module_args(function_name="my-func", version="2", state="absent", force_delete=True)
    run(scf_version.run_module)
    request = client.DeleteFunctionVersion.call_args[0][0]
    assert request.ForceDelete is True


def test_fails_managing_latest(client):
    module_args(function_name="my-func", version="$LATEST")
    with pytest.raises(AnsibleFailJson) as exc:
        run(scf_version.run_module)
    assert "cannot be managed" in exc.value.args[0]["msg"]
