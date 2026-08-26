"""Main-path unit tests for the key_pair module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.tencentcloud.cloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.tencentcloud.cloud.plugins.modules import key_pair
from ansible_collections.tencentcloud.cloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)

KEY_PAIR = {
    "KeyId": "skey-existing1",
    "KeyName": "deploy-key",
    "ProjectId": 0,
}


class FakeCvmClient(object):
    def __init__(self, key_pairs=None):
        self.key_pairs = list(key_pairs or [])
        self.CreateKeyPair = MagicMock(side_effect=self._create)
        self.ImportKeyPair = MagicMock(side_effect=self._import)
        self.DeleteKeyPairs = MagicMock(side_effect=self._delete)

    def DescribeKeyPairs(self, request):
        matched = self.key_pairs
        ids = getattr(request, "KeyIds", None)
        if ids:
            matched = [k for k in matched if k["KeyId"] in ids]
        return SimpleNamespace(KeyPairSet=[FakeResource(k) for k in matched])

    def _create(self, request):
        new_key = {
            "KeyId": "skey-new00001",
            "KeyName": request.KeyName,
            "ProjectId": request.ProjectId,
            "PrivateKey": "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----",
        }
        self.key_pairs.append({k: v for k, v in new_key.items() if k != "PrivateKey"})
        return SimpleNamespace(KeyPair=FakeResource(new_key))

    def _import(self, request):
        new_key = {
            "KeyId": "skey-imported1",
            "KeyName": request.KeyName,
            "ProjectId": request.ProjectId,
        }
        self.key_pairs.append(new_key)
        return SimpleNamespace(KeyId=new_key["KeyId"])

    def _delete(self, request):
        self.key_pairs = [k for k in self.key_pairs if k["KeyId"] not in request.KeyIds]
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeCvmClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        key_pair, "_load_cvm",
        lambda: (FakeModels(), SimpleNamespace(CvmClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_create_reports_changed_with_private_key(client):
    module_args(state="present", name="deploy-key")
    result = run(key_pair.run_module)
    assert result["changed"] is True
    assert result["key_pair"]["KeyName"] == "deploy-key"
    assert "PrivateKey" not in result["key_pair"]
    assert result["private_key"].startswith("-----BEGIN RSA PRIVATE KEY-----")
    client.CreateKeyPair.assert_called_once()
    assert "diff" not in result


def test_import_public_key_reports_changed(client):
    module_args(state="present", name="deploy-key", public_key="ssh-rsa AAAAfake")
    result = run(key_pair.run_module)
    assert result["changed"] is True
    assert result["key_pair"]["KeyId"] == "skey-imported1"
    assert "private_key" not in result
    client.ImportKeyPair.assert_called_once()


def test_second_run_is_idempotent(client):
    client.key_pairs.append(dict(KEY_PAIR))
    module_args(state="present", name="deploy-key")
    result = run(key_pair.run_module)
    assert result["changed"] is False
    assert result["key_pair"]["KeyId"] == "skey-existing1"
    client.CreateKeyPair.assert_not_called()
    client.ImportKeyPair.assert_not_called()


def test_absent_deletes_existing_key_pair(client):
    client.key_pairs.append(dict(KEY_PAIR))
    module_args(state="absent", name="deploy-key")
    result = run(key_pair.run_module)
    assert result["changed"] is True
    client.DeleteKeyPairs.assert_called_once()
    assert client.key_pairs == []


def test_absent_on_missing_key_pair_is_unchanged(client):
    module_args(state="absent", name="deploy-key")
    result = run(key_pair.run_module)
    assert result["changed"] is False
    client.DeleteKeyPairs.assert_not_called()


def test_check_mode_create_makes_no_sdk_writes(client):
    module_args(state="present", name="deploy-key", _ansible_check_mode=True)
    result = run(key_pair.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.CreateKeyPair.assert_not_called()
    client.ImportKeyPair.assert_not_called()
    client.DeleteKeyPairs.assert_not_called()


def test_diff_mode_create_includes_diff(client):
    module_args(state="present", name="deploy-key", _ansible_diff=True)
    result = run(key_pair.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["name"] == "deploy-key"
    client.CreateKeyPair.assert_called_once()
