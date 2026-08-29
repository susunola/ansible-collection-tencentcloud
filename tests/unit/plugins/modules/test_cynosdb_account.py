"""Tests for cynosdb_account."""

from ansible_collections.susunola.tencentcloud.plugins.modules import cynosdb_account
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels


def test_request_builders():
    models = FakeModels()
    params = {"cluster_id": "cluster-1", "account_name": "app", "host": "%", "password": "secret", "description": "application", "max_user_connections": 100, "password_rotation": 90}
    create = cynosdb_account.build_create_request(models, params)
    assert create.Accounts[0].AccountName == "app"
    assert create.Accounts[0].MaxUserConnections == 100
    assert cynosdb_account.build_password_request(models, params).AccountPassword == "secret"
    assert cynosdb_account.build_delete_request(models, params).Accounts[0].Host == "%"
