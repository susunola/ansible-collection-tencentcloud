# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for the tdmysql_parameter_info read module.

The module reads the instance's parameter metadata once and republishes it
keyed by parameter name, because the API returns a list while a playbook
wants ``parameters.max_connections.Value``. The tests pin that mapping, the
optional ``names`` projection (which is sorted, so the payload does not
depend on the order the caller listed names in), and the unknown-name guard
that names every missing parameter instead of returning a silently short
mapping. The guard runs after the describe call, so the tests also record
that the list request is the one the module made before failing.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.modules import tdmysql_parameter_info as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "tdsql3-abcd1234"

PARAMETERS = [
    {"Param": "max_connections", "Value": "151", "Default": "151", "NeedRestart": 0,
     "Description": "Maximum permitted simultaneous client connections"},
    {"Param": "slow_query_log", "Value": "ON", "Default": "OFF", "NeedRestart": 1,
     "Description": "Whether the slow query log is enabled"},
    {"Param": "innodb_buffer_pool_size", "Value": "134217728", "Default": "134217728",
     "NeedRestart": 0, "Description": "InnoDB buffer pool size in bytes"},
]


class FakeTdmysqlClient(object):
    """Records every call and returns canned parameter metadata."""

    def __init__(self, parameters=None, request_id="req-parameters"):
        self.parameters = [dict(item) for item in (parameters if parameters is not None else PARAMETERS)]
        self.request_id = request_id
        self.calls = []

    def DescribeDBParameters(self, request):
        self.calls.append(("DescribeDBParameters", request))
        return FakeResource({"Params": [FakeResource(item) for item in self.parameters],
                             "RequestId": self.request_id})

    def operations(self):
        return [name for name, _request in self.calls]


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


def _wire(monkeypatch, client):
    """Point the module at the fake client and a no-op SDK check."""
    monkeypatch.setattr(mod.TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load",
                        lambda: (FakeModels(), SimpleNamespace(TdmysqlClient=object())))
    monkeypatch.setattr(mod.TencentCloudModule, "create_client",
                        lambda self, cls, endpoint: client)


# ---------------------------------------------------------------------------
# listing parameters
# ---------------------------------------------------------------------------

def test_listing_returns_every_parameter_keyed_by_name(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID)
    result = run(mod.run_module)

    assert result["changed"] is False
    assert list(result["parameters"]) == ["max_connections", "slow_query_log", "innodb_buffer_pool_size"]
    assert result["parameters"]["max_connections"] == {
        "Param": "max_connections", "Value": "151", "Default": "151", "NeedRestart": 0,
        "Description": "Maximum permitted simultaneous client connections",
    }
    assert result["parameters"]["slow_query_log"]["NeedRestart"] == 1
    assert client.operations() == ["DescribeDBParameters"]


def test_listing_sends_the_instance_id(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID)
    run(mod.run_module)
    request = client.calls[0][1]
    assert request.InstanceId == INSTANCE_ID


def test_listing_an_instance_with_no_parameters_is_empty(monkeypatch):
    client = FakeTdmysqlClient(parameters=[])
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID)
    result = run(mod.run_module)

    assert result["changed"] is False
    assert result["parameters"] == {}
    assert client.operations() == ["DescribeDBParameters"]


def test_duplicate_parameter_names_keep_the_last_entry(monkeypatch):
    """The mapping is keyed by name, so a name the API repeats collapses to
    one entry rather than producing a list the caller cannot index."""
    client = FakeTdmysqlClient(parameters=[
        {"Param": "max_connections", "Value": "151"},
        {"Param": "max_connections", "Value": "200"},
    ])
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID)
    result = run(mod.run_module)

    assert result["parameters"] == {"max_connections": {"Param": "max_connections", "Value": "200"}}


# ---------------------------------------------------------------------------
# the names projection
# ---------------------------------------------------------------------------

def test_names_selects_the_requested_parameters_sorted(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, names=["slow_query_log", "max_connections"])
    result = run(mod.run_module)

    assert result["changed"] is False
    assert list(result["parameters"]) == ["max_connections", "slow_query_log"]
    assert result["parameters"]["slow_query_log"]["Value"] == "ON"
    assert "innodb_buffer_pool_size" not in result["parameters"]


def test_an_empty_names_list_selects_nothing(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, names=[])
    result = run(mod.run_module)

    assert result["parameters"] == {}
    assert client.operations() == ["DescribeDBParameters"]


def test_unknown_names_fail_and_name_every_missing_parameter(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID, names=["max_connections", "nope", "also_missing"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]

    assert payload["msg"] == "unknown TDSQL MySQL parameter names"
    assert payload["unknown_parameters"] == ["also_missing", "nope"]
    assert "parameters" not in payload
    # The describe call is what discovers the names, so it happens first.
    assert client.operations() == ["DescribeDBParameters"]


# ---------------------------------------------------------------------------
# guard rails
# ---------------------------------------------------------------------------

def test_instance_id_is_required(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "instance_id" in exc.value.args[0]["msg"]
    assert client.calls == []


# ---------------------------------------------------------------------------
# failures
# ---------------------------------------------------------------------------

def test_sdk_error_is_surfaced(monkeypatch):
    _wire(monkeypatch, _BoomClient())
    module_args(instance_id=INSTANCE_ID)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["failed"] is True
    assert "service exploded" in payload["error"]
    assert payload["error_kind"] == "other"
