"""Unit tests for the config_aggregate_delivery write module (run_module flows).

Drives ``run_module()`` against an in-memory fake Config client whose
update operation mutates an aggregate-delivery store so post-write
describes converge immediately.

There is no delete: ``enabled=false`` flips the delivery ``Status`` to 0
through the same ``UpdateAggregateConfigDeliver`` call (disable, not
destroy), and the account group is carried on every request.

Scenario matrix:

* matching aggregate delivery configuration is idempotent
* name/prefix/uin/content-type drift triggers an update
* disabling (enabled=false) flips Status to 0 via UpdateAggregateConfigDeliver
* check-mode dry run and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import config_aggregate_delivery as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ACCOUNT_GROUP_ID = "ag-77"

DELIVERY = {
    "AccountGroupId": ACCOUNT_GROUP_ID,
    "Status": 1,
    "DeliverName": "organization-archive",
    "TargetArn": "qcs::cos:ap-guangzhou:100000000001:prefix/1250000000/config-org",
    "DeliverPrefix": "config",
    "DeliverType": "COS",
    "DeliverUin": 0,
    "DeliverContentType": 3,
}


def _delivery(**overrides):
    item = copy.deepcopy(DELIVERY)
    item.update(overrides)
    return item


def _args(enabled=True, **overrides):
    params = {
        "account_group_id": ACCOUNT_GROUP_ID,
        "enabled": enabled,
        "name": "organization-archive",
        "target_arn": DELIVERY["TargetArn"],
        "prefix": "config",
        "delivery_type": "COS",
        "delivery_uin": 0,
        "content_type": 3,
    }
    params.update(overrides)
    return module_args(**params)


class FakeConfigClient(object):
    """In-memory Config client holding one aggregate delivery configuration."""

    def __init__(self, delivery=None):
        self.delivery = copy.deepcopy(delivery or _delivery())
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeAggregateConfigDeliver(self, request):
        self._record("DescribeAggregateConfigDeliver", request)
        return FakeResource(copy.deepcopy(self.delivery))

    def UpdateAggregateConfigDeliver(self, request):
        self._record("UpdateAggregateConfigDeliver", request)
        self.delivery["Status"] = getattr(request, "Status", self.delivery.get("Status"))
        self.delivery["DeliverName"] = getattr(request, "DeliverName", self.delivery.get("DeliverName"))
        self.delivery["TargetArn"] = getattr(request, "TargetArn", self.delivery.get("TargetArn"))
        self.delivery["DeliverPrefix"] = getattr(request, "DeliverPrefix", self.delivery.get("DeliverPrefix"))
        self.delivery["DeliverType"] = getattr(request, "DeliverType", self.delivery.get("DeliverType"))
        self.delivery["DeliverUin"] = getattr(request, "DeliverUin", self.delivery.get("DeliverUin"))
        self.delivery["DeliverContentType"] = getattr(request, "DeliverContentType", self.delivery.get("DeliverContentType"))
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(ConfigClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def test_no_drift_is_idempotent(monkeypatch):
    fake = FakeConfigClient(delivery=_delivery())
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["delivery"]["DeliverName"] == "organization-archive"
    assert [c for c, unused in fake.calls] == ["DescribeAggregateConfigDeliver"]


def test_name_drift_updates(monkeypatch):
    fake = FakeConfigClient(delivery=_delivery())
    _make_module(monkeypatch, fake)
    _args(name="renamed-archive")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["delivery"]["DeliverName"] == "renamed-archive"
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribeAggregateConfigDeliver", "UpdateAggregateConfigDeliver", "DescribeAggregateConfigDeliver"]


def test_delivery_uin_drift_updates(monkeypatch):
    fake = FakeConfigClient(delivery=_delivery())
    _make_module(monkeypatch, fake)
    _args(delivery_uin=125000000002)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["delivery"]["DeliverUin"] == 125000000002


def test_content_type_drift_updates(monkeypatch):
    fake = FakeConfigClient(delivery=_delivery())
    _make_module(monkeypatch, fake)
    _args(content_type=2)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["delivery"]["DeliverContentType"] == 2


def test_disable_flips_status_to_zero(monkeypatch):
    fake = FakeConfigClient(delivery=_delivery())
    _make_module(monkeypatch, fake)
    _args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["delivery"]["Status"] == 0
    update_call = [r for c, r in fake.calls if c == "UpdateAggregateConfigDeliver"][0]
    assert update_call.Status == 0
    assert update_call.AccountGroupId == ACCOUNT_GROUP_ID


def test_re_enable_restores_status(monkeypatch):
    fake = FakeConfigClient(delivery=_delivery(Status=0))
    _make_module(monkeypatch, fake)
    _args(enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["delivery"]["Status"] == 1


def test_check_mode_is_dry_run(monkeypatch):
    fake = FakeConfigClient(delivery=_delivery())
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, name="preview-name")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.delivery["DeliverName"] == "organization-archive"
    assert [c for c, unused in fake.calls] == ["DescribeAggregateConfigDeliver"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAggregateConfigDeliver(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
