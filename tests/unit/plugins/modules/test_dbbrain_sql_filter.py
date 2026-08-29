from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.modules import dbbrain_sql_filter as m
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import FakeModels

P = {
    "instance_id": "cdb-x",
    "sql_type": "SELECT",
    "filter_key": "select,user",
    "max_concurrency": 2,
    "duration": -1,
    "session_token": "secret",
    "product": "mysql",
}


def test_builders():
    models = FakeModels()
    assert m.build_create_request(models, P).FilterKey == "select,user"
    assert m.build_describe_request(models, P).Statuses == ["RUNNING"]
    assert m.build_delete_request(models, P, [1]).FilterIds == [1]


def test_desired():
    assert m._desired(P)["MaxConcurrency"] == 2


def test_find_running_filter():
    item = type("Item", (), {"SqlType": "SELECT", "OriginKeys": "select,user", "Status": "RUNNING", "_serialize": lambda self, allow_none=True: {"Id": 1}})()
    assert m._find([item], P) == {"Id": 1}
