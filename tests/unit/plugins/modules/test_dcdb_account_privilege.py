"""Tests for DCDB privilege request helpers."""

from ansible_collections.susunola.tencentcloud.plugins.modules.dcdb_account_privilege import request


class Request(object):
    pass


class Models(object):
    DescribeAccountPrivilegesRequest = Request
    GrantAccountPrivilegesRequest = Request


def test_privilege_request_maps_scope_and_deduplicates_privileges():
    params = {"instance_id": "dcdb-1", "username": "app", "host": "%", "database": "orders", "object_type": "table", "object_name": "events", "column": "*"}
    value = request(Models, "GrantAccountPrivilegesRequest", params, ["UPDATE", "SELECT", "SELECT"])
    assert value.InstanceId == "dcdb-1"
    assert (value.DbName, value.Type, value.Object, value.ColName) == ("orders", "table", "events", "*")
    assert value.Privileges == ["SELECT", "UPDATE"]
