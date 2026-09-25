# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for the tdmysql_backup_policy_info read module.

The module makes one describe call and reports the policy list exactly as the
API returned it, without assuming there is exactly one policy: the write
module is the side that insists on cardinality, while this read side reports
``total_count`` beside the items it actually received. The tests pin the
single-call contract, the plain-dict serialization of each policy, the
boolean normalization of ``EnableFull``/``EnableLog`` (including the fact
that flags the API omits are left alone rather than invented) and the
zero-count empty response.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.modules import tdmysql_backup_policy_info as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "tdsql3-abcd1234"

POLICIES = [
    {"BackupMethod": "physical", "BackupStartTime": "00:00", "BackupEndTime": "04:00",
     "EnableFull": 1, "EnableLog": 0, "FullRetentionPeriod": 7, "LogRetentionPeriod": 7,
     "PeriodTime": "0,1,2,3,4,5,6"},
    {"BackupMethod": "snapshot", "BackupStartTime": "02:00", "BackupEndTime": "06:00",
     "EnableFull": 0, "EnableLog": 1, "FullRetentionPeriod": 3, "LogRetentionPeriod": 3,
     "PeriodTime": "1,3,5"},
]


class FakeTdmysqlClient(object):
    """Records every call and returns one canned backup-policy response."""

    def __init__(self, policies=None, total_count=None):
        self.policies = [dict(item) for item in (policies if policies is not None else POLICIES)]
        self.total_count = len(self.policies) if total_count is None else total_count
        self.calls = []

    def DescribeDBSBackupPolicy(self, request):
        self.calls.append(("DescribeDBSBackupPolicy", request))
        return FakeResource({"Items": [FakeResource(item) for item in self.policies],
                             "TotalCount": self.total_count,
                             "RequestId": "req-policy"})

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
# describing the backup policy
# ---------------------------------------------------------------------------

def test_describe_returns_every_policy_serialized(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID)
    result = run(mod.run_module)

    assert result["changed"] is False
    assert result["backup_policies"] == [
        dict(POLICIES[0], EnableFull=True, EnableLog=False),
        dict(POLICIES[1], EnableFull=False, EnableLog=True),
    ]
    assert all(isinstance(item, dict) for item in result["backup_policies"])
    assert result["total_count"] == 2
    assert result["request_id"] == "req-policy"
    assert client.operations() == ["DescribeDBSBackupPolicy"]


def test_describe_sends_the_instance_id(monkeypatch):
    client = FakeTdmysqlClient()
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID)
    run(mod.run_module)
    request = client.calls[0][1]
    assert request.InstanceId == INSTANCE_ID


def test_policy_flags_are_normalized_to_booleans(monkeypatch):
    """The API reports the two switches as 0/1 integers; the payload must
    carry real booleans so ``when: policy.EnableLog`` reads correctly."""
    client = FakeTdmysqlClient(policies=[{"EnableFull": 1, "EnableLog": 0}])
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID)
    result = run(mod.run_module)
    policy = result["backup_policies"][0]

    assert policy["EnableFull"] is True
    assert policy["EnableLog"] is False


def test_absent_and_null_flags_are_left_alone(monkeypatch):
    """Normalization coerces only the flags the API actually reported, so a
    policy that omits them does not gain a misleading ``false``."""
    client = FakeTdmysqlClient(policies=[{"BackupMethod": "physical", "EnableLog": None}])
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID)
    result = run(mod.run_module)
    policy = result["backup_policies"][0]

    assert policy == {"BackupMethod": "physical", "EnableLog": None}
    assert "EnableFull" not in policy


def test_empty_response_reports_zero_total(monkeypatch):
    client = FakeTdmysqlClient(policies=[], total_count=0)
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID)
    result = run(mod.run_module)

    assert result["changed"] is False
    assert result["backup_policies"] == []
    assert result["total_count"] == 0
    assert result["request_id"] == "req-policy"
    assert client.operations() == ["DescribeDBSBackupPolicy"]


def test_a_null_total_count_does_not_break_the_payload(monkeypatch):
    client = FakeTdmysqlClient(policies=[dict(POLICIES[0])])
    client.total_count = None
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID)
    result = run(mod.run_module)

    assert result["total_count"] == 0
    assert len(result["backup_policies"]) == 1


def test_total_count_is_reported_apart_from_the_page(monkeypatch):
    """The read side reports the API's count even when it does not match the
    number of items in the response, instead of assuming cardinality."""
    client = FakeTdmysqlClient(policies=[dict(POLICIES[0])], total_count=3)
    _wire(monkeypatch, client)
    module_args(instance_id=INSTANCE_ID)
    result = run(mod.run_module)

    assert result["total_count"] == 3
    assert [item["BackupMethod"] for item in result["backup_policies"]] == ["physical"]


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
