"""Tests for dts_consumer_group."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.modules import dts_consumer_group
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels

PARAMS = {"subscribe_id": "subs-x", "consumer_group_name": "analytics", "account_name": "reader", "password": "secret", "description": "analytics"}


def test_request_builders():
    models = FakeModels()
    create = dts_consumer_group.build_create_request(models, PARAMS)
    assert create.SubscribeId == "subs-x"
    assert create.Password == "secret"
    update = dts_consumer_group.build_update_request(models, "subs-x", "consumer-full", "account-full", "new")
    assert update.Description == "new"
    delete = dts_consumer_group.build_delete_request(models, "subs-x", "consumer-full", "account-full")
    assert delete.AccountName == "account-full"


def test_generated_name_matching():
    assert dts_consumer_group._name_matches("consumer-grp-subs-x-analytics", "analytics", "consumer-grp-subs-x")
    assert dts_consumer_group._name_matches("analytics", "analytics", "consumer-grp-subs-x")
    assert not dts_consumer_group._name_matches("other", "analytics", "consumer-grp-subs-x")
