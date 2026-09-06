"""Unit tests for the cls_shipper write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/cls_shipper.py`` with an in-memory fake CLS client whose
write operations mutate the shipper store, so the module's post-write
``find`` refetch converges immediately. Shippers are matched by
``shipper_id`` or by the (name, topic_id) pair; the paginated lookup, the
multiple-match guard, the stale-``shipper_id`` failure, the
disable-after-create path (``enabled: false``) and check-mode dry runs are
exercised.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cls_shipper as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

SHIPPER = {
    "ShipperId": "shipper-8b0a1c2d",
    "TopicId": "0f6c6e3a-8b0a",
    "ShipperName": "archive-to-cos",
    "Bucket": "logs-1250000000",
    "Prefix": "",
    "Status": True,
    "Interval": 300,
    "MaxSize": 256,
    "Partition": "%Y/%m/%d/%H",
    "Compress": {"Format": "gzip"},
    "Content": {"Format": "json"},
    "FilterRules": [],
    "FilenameMode": 0,
    "StorageType": "STANDARD",
    "RoleArn": None,
    "ExternalId": None,
    "TimeZone": "UTC+08:00",
    "DSLFilter": "",
}


def _shipper(**overrides):
    """Return a shipper fixture isolated from the shared constant."""
    item = copy.deepcopy(SHIPPER)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base included)."""
    params = {
        "state": "present",
        "shipper_id": None,
        "topic_id": "0f6c6e3a-8b0a",
        "name": "archive-to-cos",
        "bucket": "logs-1250000000",
        "prefix": "",
        "enabled": True,
        "interval": 300,
        "max_size": 256,
        "partition": "%Y/%m/%d/%H",
        "compress": {"Format": "gzip"},
        "content": {"Format": "json"},
        "filter_rules": [],
        "filename_mode": 0,
        "storage_type": "STANDARD",
        "role_arn": None,
        "external_id": None,
        "time_zone": "UTC+08:00",
        "dsl_filter": "",
        "retries": 5,
        "waiter_delay": 5,
        "waiter_timeout": 120,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    args = dict(_params())
    args.update(extra)
    return module_args(**args)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or _params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


def _plain(value):
    """Convert a fake SDK model back to plain data for the store."""
    if value is None:
        return None
    if hasattr(value, "_value"):  # _DeserializeModel payload
        return value._value
    if hasattr(value, "__dict__"):  # FakeRequest attribute bag
        return {k: _plain(v) for k, v in vars(value).items() if not k.startswith("_")}
    return value


def _plain_list(values):
    return [_plain(v) for v in (values or [])]


class FakeClsClient(object):
    """In-memory CLS client that mutates a small shipper store."""

    def __init__(self, shippers=None):
        self.shippers = [copy.deepcopy(s) for s in (shippers or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeShippers(self, request):
        self._record("DescribeShippers", request)
        offset = getattr(request, "Offset", 0)
        limit = getattr(request, "Limit", 100)
        page = self.shippers[offset : offset + limit]
        return SimpleNamespace(
            Shippers=[FakeResource(dict(s)) for s in page],
            TotalCount=len(self.shippers),
        )

    def CreateShipper(self, request):
        self._record("CreateShipper", request)
        self._next += 1
        item = {
            "ShipperId": "shipper-fake-%03d" % self._next,
            "TopicId": request.TopicId,
            "ShipperName": request.ShipperName,
            "Bucket": request.Bucket,
            "Prefix": request.Prefix,
            "Status": True,  # server-side default before any disable call
            "Interval": request.Interval,
            "MaxSize": request.MaxSize,
            "Partition": request.Partition,
            "Compress": _plain(request.Compress),
            "Content": _plain(request.Content),
            "FilterRules": _plain_list(request.FilterRules),
            "FilenameMode": request.FilenameMode,
            "StorageType": request.StorageType,
            "RoleArn": _plain(request.RoleArn),
            "ExternalId": _plain(request.ExternalId),
            "TimeZone": request.TimeZone,
            "DSLFilter": request.DSLFilter,
        }
        self.shippers.append(item)
        return SimpleNamespace(ShipperId=item["ShipperId"], RequestId="req-fake")

    def ModifyShipper(self, request):
        self._record("ModifyShipper", request)
        for item in self.shippers:
            if item.get("ShipperId") == request.ShipperId:
                if getattr(request, "Status", None) is not None:
                    item["Status"] = request.Status
                for attr in (
                    "TopicId",
                    "ShipperName",
                    "Bucket",
                    "Prefix",
                    "Interval",
                    "MaxSize",
                    "Partition",
                    "Compress",
                    "Content",
                    "FilterRules",
                    "FilenameMode",
                    "StorageType",
                    "TimeZone",
                    "DSLFilter",
                ):
                    value = getattr(request, attr, None)
                    if value is not None:
                        item[attr] = _plain(value)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteShipper(self, request):
        self._record("DeleteShipper", request)
        self.shippers = [s for s in self.shippers if s.get("ShipperId") != request.ShipperId]
        return SimpleNamespace(RequestId="req-fake")


class _DeserializeModel(object):
    """SDK payload model built via ``_deserialize`` (cls models)."""

    def __init__(self):
        self._value = None

    def _deserialize(self, value):
        self._value = copy.deepcopy(value)


class FakeClsModels(FakeModels):
    """FakeModels whose payload models resolve to _deserialize-able classes."""

    _deserialize_models = ("CompressInfo", "ContentInfo", "FilterRuleInfo")

    def __getattr__(self, name):
        if name in self._deserialize_models:
            return _DeserializeModel
        return super(FakeClsModels, self).__getattr__(name)


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeClsModels(), SimpleNamespace(ClsClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_model_deserializes_payload():
    obj = mod._model(FakeClsModels(), "CompressInfo", {"Format": "gzip"})
    assert obj._value == {"Format": "gzip"}


def test_models_deserializes_list():
    objs = mod._models(FakeClsModels(), "FilterRuleInfo", [{"Key": "a", "Regex": "", "Value": "b"}])
    assert [o._value for o in objs] == [{"Key": "a", "Regex": "", "Value": "b"}]


def test_describe_request_without_shipper_id_builds_filter():
    request = mod.describe_request(FakeClsModels(), _params(), offset=10)
    assert request.Offset == 10
    assert request.Limit == 100
    assert request.PreciseSearch == 1
    assert request.Filters[0].Key == "shipperName"
    assert request.Filters[0].Values == ["archive-to-cos"]


def test_describe_request_with_shipper_id_skips_filter():
    request = mod.describe_request(FakeClsModels(), _params(shipper_id="shipper-abc"))
    assert getattr(request, "Filters", None) is None


def test_common_populates_delivery_config():
    models = FakeClsModels()
    p = _params(
        prefix="cls/archive/",
        interval=600,
        max_size=512,
        partition="%Y/%m/%d",
        filter_rules=[{"Key": "level", "Regex": "", "Value": "error"}],
        compress={"Format": "lzop"},
        content={"Format": "csv"},
        filename_mode=1,
        storage_type="IA",
        role_arn="qcs::cam::uin/1:role/x",
        external_id="ext-1",
        time_zone="UTC",
        dsl_filter="level:error",
    )
    request = mod._common(FakeClsModels().ModifyShipperRequest(), models, p)
    assert request.Bucket == "logs-1250000000"
    assert request.Prefix == "cls/archive/"
    assert request.ShipperName == "archive-to-cos"
    assert request.Interval == 600
    assert request.MaxSize == 512
    assert request.Partition == "%Y/%m/%d"
    assert request.FilterRules[0]._value["Value"] == "error"
    assert request.Compress._value == {"Format": "lzop"}
    assert request.Content._value == {"Format": "csv"}
    assert request.FilenameMode == 1
    assert request.StorageType == "IA"
    assert request.RoleArn == "qcs::cam::uin/1:role/x"
    assert request.ExternalId == "ext-1"
    assert request.TimeZone == "UTC"
    assert request.DSLFilter == "level:error"


def test_create_request_sets_topic():
    request = mod.create_request(FakeClsModels(), _params())
    assert request.TopicId == "0f6c6e3a-8b0a"
    assert request.ShipperName == "archive-to-cos"


def test_update_request_sets_id_and_status():
    request = mod.update_request(FakeClsModels(), _params(enabled=False), "shipper-abc")
    assert request.ShipperId == "shipper-abc"
    assert request.Status is False


def test_delete_request_sets_id():
    request = mod.delete_request(FakeClsModels(), "shipper-abc")
    assert request.ShipperId == "shipper-abc"


def test_comparable_sorts_filter_rules_and_defaults_text():
    value = mod.comparable(
        _shipper(
            Prefix="cls/",
            FilterRules=[
                {"Key": "b", "Regex": "r2", "Value": "2"},
                {"Key": "a", "Regex": "r1", "Value": "1"},
            ],
        )
    )
    assert value["Prefix"] == "cls/"
    assert value["DSLFilter"] == ""
    assert value["FilterRules"][0]["Key"] == "a"
    assert value["FilterRules"][1]["Key"] == "b"


def test_comparable_missing_text_fields_default_empty():
    value = mod.comparable(_shipper())
    assert value["Prefix"] == ""
    assert value["DSLFilter"] == ""
    assert value["FilterRules"] == []


def test_desired_maps_params_to_api_fields():
    target = mod.desired(_params(interval=600, enabled=False))
    assert target["Interval"] == 600
    assert target["Status"] is False
    assert target["TopicId"] == "0f6c6e3a-8b0a"
    assert target["ShipperName"] == "archive-to-cos"
    assert target["Prefix"] == ""
    assert target["StorageType"] == "STANDARD"


def test_find_matches_by_shipper_id(monkeypatch):
    fake = FakeClsClient([_shipper()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(shipper_id="shipper-8b0a1c2d"))
    value = mod.find(module, fake, FakeClsModels(), module.params)
    assert value["ShipperId"] == "shipper-8b0a1c2d"


def test_find_matches_by_name_and_topic(monkeypatch):
    fake = FakeClsClient([_shipper()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeClsModels(), module.params)
    assert value["ShipperName"] == "archive-to-cos"


def test_find_ignores_same_name_other_topic(monkeypatch):
    fake = FakeClsClient([_shipper(TopicId="other-topic")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeClsModels(), module.params) is None


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeClsClient()
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="missing"))
    assert mod.find(module, fake, FakeClsModels(), module.params) is None


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeClsClient(
        [
            _shipper(ShipperId="shipper-1", ShipperName="dup"),
            _shipper(ShipperId="shipper-2", ShipperName="dup"),
        ]
    )
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="dup"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeClsModels(), module.params)
    assert "multiple CLS shippers matched" in exc.value.args[0]["msg"]


def test_find_paginates_until_match(monkeypatch):
    # 100 non-matching shippers on page one force a second DescribeShippers.
    store = [_shipper(ShipperId="shipper-%03d" % i, ShipperName="other-%03d" % i) for i in range(100)]
    store.append(_shipper(ShipperId="shipper-needle", ShipperName="needle"))
    fake = FakeClsClient(store)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="needle"))
    value = mod.find(module, fake, FakeClsModels(), module.params)
    assert value["ShipperId"] == "shipper-needle"
    assert len([c for c in fake.calls if c[0] == "DescribeShippers"]) == 2


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_arguments_enforced(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    module_args()
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeClsModels(), SimpleNamespace(ClsClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


def test_present_creates_shipper(monkeypatch):
    fake = FakeClsClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", topic_id="0f6c6e3a-8b0a", name="archive-to-cos",
                bucket="logs-1250000000")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["shipper"]["ShipperId"] == "shipper-fake-001"
    assert result["shipper"]["ShipperName"] == "archive-to-cos"
    assert result["shipper"]["Status"] is True
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeShippers") == 2  # find + refetch
    assert names.count("CreateShipper") == 1
    assert "ModifyShipper" not in names


def test_present_create_disabled_then_disables(monkeypatch):
    fake = FakeClsClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", topic_id="0f6c6e3a-8b0a", name="archive-to-cos",
                bucket="logs-1250000000", enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["shipper"]["Status"] is False
    names = [c[0] for c in fake.calls]
    assert names.count("CreateShipper") == 1
    assert names.count("ModifyShipper") == 1  # disable-after-create


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeClsClient([_shipper()])
    _make_module(monkeypatch, fake)
    module_args(state="present", topic_id="0f6c6e3a-8b0a", name="archive-to-cos",
                bucket="logs-1250000000")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["shipper"]["ShipperId"] == "shipper-8b0a1c2d"
    names = [c[0] for c in fake.calls]
    assert "CreateShipper" not in names
    assert "ModifyShipper" not in names


def test_present_drift_triggers_update(monkeypatch):
    fake = FakeClsClient([_shipper()])
    _make_module(monkeypatch, fake)
    module_args(state="present", topic_id="0f6c6e3a-8b0a", name="archive-to-cos",
                bucket="logs-1250000000", interval=600)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["shipper"]["Interval"] == 600
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyShipper") == 1
    assert "CreateShipper" not in names


def test_present_stale_shipper_id_fails(monkeypatch):
    fake = FakeClsClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", shipper_id="shipper-gone", topic_id="0f6c6e3a-8b0a",
                name="archive-to-cos", bucket="logs-1250000000")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "shipper_id was not found" in exc.value.args[0]["msg"]
    assert not any("CreateShipper" == c[0] for c in fake.calls)


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeClsClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="present", topic_id="0f6c6e3a-8b0a",
                name="archive-to-cos", bucket="logs-1250000000")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["shipper"] is None  # no write means nothing to report
    assert not any("CreateShipper" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeClsClient([_shipper()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="present", topic_id="0f6c6e3a-8b0a",
                name="archive-to-cos", bucket="logs-1250000000", interval=600)
    result = run(mod.run_module)
    assert result["changed"] is True
    # No write happened, so the reported shipper is the pre-change state.
    assert result["shipper"]["Interval"] == 300
    assert not any("ModifyShipper" == c[0] for c in fake.calls)


def test_absent_removes_shipper(monkeypatch):
    fake = FakeClsClient([_shipper()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", shipper_id="shipper-8b0a1c2d", topic_id="0f6c6e3a-8b0a",
                name="archive-to-cos", bucket="logs-1250000000")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["shipper"] is None
    names = [c[0] for c in fake.calls]
    assert names.count("DeleteShipper") == 1
    assert fake.shippers == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeClsClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", shipper_id="shipper-gone", topic_id="0f6c6e3a-8b0a",
                name="archive-to-cos", bucket="logs-1250000000")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["shipper"] is None
    assert not any("DeleteShipper" == c[0] for c in fake.calls)


def test_absent_check_mode_reports_current(monkeypatch):
    fake = FakeClsClient([_shipper()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", shipper_id="shipper-8b0a1c2d",
                topic_id="0f6c6e3a-8b0a", name="archive-to-cos", bucket="logs-1250000000")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["shipper"]["ShipperId"] == "shipper-8b0a1c2d"
    assert not any("DeleteShipper" == c[0] for c in fake.calls)
    assert len(fake.shippers) == 1
