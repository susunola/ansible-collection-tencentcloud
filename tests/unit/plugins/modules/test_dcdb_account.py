"""Tests for DCDB account helper semantics."""

from ansible_collections.susunola.tencentcloud.plugins.modules.dcdb_account import comparable, desired


def params():
    return {
        "username": "app",
        "host": "%",
        "description": "application",
        "read_only": 0,
        "delay_threshold": 10,
        "sticky_replica": False,
        "max_user_connections": 0,
    }


def test_desired_maps_account_properties():
    assert desired(params()) == {
        "UserName": "app",
        "Host": "%",
        "Description": "application",
        "ReadOnly": 0,
        "DelayThresh": 10,
        "SlaveConst": 0,
        "MaxUserConnections": 0,
    }


def test_comparable_ignores_server_only_fields():
    value = desired(params())
    value["CreateTime"] = "now"
    assert comparable(value) == desired(params())
