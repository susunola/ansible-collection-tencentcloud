"""Main-path unit tests for the scf_alias module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import scf_alias
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ALIAS = {
    "Name": "prod",
    "FunctionVersion": "2",
    "Description": "Production traffic",
    "AddTime": "2026-08-28 10:00:00",
    "ModTime": "2026-08-28 10:00:00",
}


class FakeNotFound(Exception):
    def get_code(self):
        return "ResourceNotFound.AliasNotFound"


class FakeScfClient(object):
    def __init__(self, alias=None):
        self.alias = dict(alias) if alias else None
        self.CreateAlias = MagicMock(side_effect=self._create)
        self.UpdateAlias = MagicMock(side_effect=self._update)
        self.DeleteAlias = MagicMock(side_effect=self._delete)

    def GetAlias(self, request):
        if self.alias and self.alias["Name"] == request.Name:
            return FakeResource(self.alias)
        raise FakeNotFound()

    def _create(self, request):
        self.alias = {
            "Name": request.Name,
            "FunctionVersion": request.FunctionVersion,
            "Description": getattr(request, "Description", "") or "",
        }
        return SimpleNamespace()

    def _update(self, request):
        self.alias["FunctionVersion"] = request.FunctionVersion
        if getattr(request, "Description", None) is not None:
            self.alias["Description"] = request.Description
        return SimpleNamespace()

    def _delete(self, request):
        self.alias = None
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeScfClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        scf_alias, "_load_scf",
        lambda: (FakeModels(), SimpleNamespace(ScfClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_creates_alias(client):
    module_args(function_name="my-func", name="prod",
                function_version="2", description="Production traffic")
    result = run(scf_alias.run_module)
    assert result["changed"] is True
    assert result["msg"] == "SCF alias created"
    client.CreateAlias.assert_called_once()
    request = client.CreateAlias.call_args[0][0]
    assert request.FunctionName == "my-func"
    assert request.Name == "prod"
    assert request.FunctionVersion == "2"
    assert result["alias"]["FunctionVersion"] == "2"


def test_second_run_is_idempotent(client):
    client.alias = dict(ALIAS)
    module_args(function_name="my-func", name="prod",
                function_version="2", description="Production traffic")
    result = run(scf_alias.run_module)
    assert result["changed"] is False
    assert result["msg"] == "SCF alias is up to date"
    client.CreateAlias.assert_not_called()
    client.UpdateAlias.assert_not_called()


def test_version_drift_triggers_update(client):
    client.alias = dict(ALIAS)
    module_args(function_name="my-func", name="prod", function_version="3")
    result = run(scf_alias.run_module)
    assert result["changed"] is True
    assert result["msg"] == "SCF alias updated"
    request = client.UpdateAlias.call_args[0][0]
    assert request.FunctionVersion == "3"
    assert result["alias"]["FunctionVersion"] == "3"


def test_absent_deletes(client):
    client.alias = dict(ALIAS)
    module_args(function_name="my-func", name="prod",
                function_version="2", state="absent")
    result = run(scf_alias.run_module)
    assert result["changed"] is True
    assert result["msg"] == "SCF alias deleted"
    assert result["alias"] is None
    request = client.DeleteAlias.call_args[0][0]
    assert request.Name == "prod"


def test_absent_already_absent(client):
    module_args(function_name="my-func", name="prod",
                function_version="2", state="absent")
    result = run(scf_alias.run_module)
    assert result["changed"] is False
    assert result["msg"] == "SCF alias already absent"
    client.DeleteAlias.assert_not_called()


def test_check_mode_create_does_not_write(client):
    module_args(_ansible_check_mode=True, function_name="my-func", name="prod",
                function_version="2")
    result = run(scf_alias.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create SCF alias"
    client.CreateAlias.assert_not_called()


def test_fails_without_function_version(client):
    module_args(function_name="my-func", name="prod")
    with pytest.raises(AnsibleFailJson) as exc:
        run(scf_alias.run_module)
    assert "function_version" in exc.value.args[0]["msg"]
