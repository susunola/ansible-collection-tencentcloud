"""Tests for postgresql_account."""

from ansible_collections.susunola.tencentcloud.plugins.modules import postgresql_account
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels


def test_request_builders():
    models = FakeModels()
    params = {"instance_id": "postgres-1", "username": "app", "password": "secret", "account_type": "normal", "remark": "application", "cam_auth": False}
    create = postgresql_account.build_create_request(models, params)
    assert create.UserName == "app"
    assert create.Type == "normal"
    assert postgresql_account.build_password_request(models, "postgres-1", "app", "next").Password == "next"
    assert postgresql_account.build_delete_request(models, "postgres-1", "app").UserName == "app"
