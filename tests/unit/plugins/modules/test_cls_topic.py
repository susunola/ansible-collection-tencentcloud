"""Unit tests for the cls_topic write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/cls_topic.py`` with an in-memory fake CLS client whose
write operations mutate the topic store, so the module's post-write
``wait_for_topic`` refetch converges immediately. Topics are matched by
``topic_id`` or by ``LogsetId`` + ``TopicName`` across the paged
DescribeTopics list (Limit 100); duplicate-name stores fail with a
multi-match error.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cls_topic as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

TOPIC = {
    "TopicId": "topic-1",
    "LogsetId": "logset-1",
    "TopicName": "network-flow",
    "PartitionCount": 1,
    "Period": 30,
    "StorageType": "hot",
    "AutoSplit": True,
    "MaxSplitPartitions": 50,
    "Describes": "",
    "HotPeriod": 7,
    "Tags": [{"Key": "env", "Value": "prod"}],
}


def _topic(**overrides):
    """API-shaped topic dict isolated from the shared constant."""
    item = copy.deepcopy(TOPIC)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec."""
    params = {
        "state": "present",
        "topic_id": None,
        "logset_id": "logset-1",
        "name": "network-flow",
        "partition_count": 1,
        "period": 30,
        "hot_period": None,
        "storage_type": "hot",
        "auto_split": True,
        "max_split_partitions": 50,
        "description": "",
        "tags": None,
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


class FakeClsClient(object):
    """In-memory ClsClient stand-in.

    Stores API-shaped topic dicts. DescribeTopics pages over the store
    honouring Offset/Limit so find_topic pagination is exercised; the write
    operations mutate the store so post-write refetches converge.
    """

    def __init__(self, topics=None):
        self.topics = [copy.deepcopy(t) for t in (topics or [])]
        self.calls = []
        self._next_id = 10000

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _new_id(self):
        self._next_id += 1
        return "topic-%05d" % self._next_id

    @staticmethod
    def _tags(request):
        return [{"Key": t.Key, "Value": t.Value} for t in (getattr(request, "Tags", None) or [])]

    def DescribeTopics(self, request):
        self._record("DescribeTopics", request)
        page = self.topics[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            Topics=[FakeResource(dict(t)) for t in page],
            TotalCount=len(self.topics),
            RequestId="req-fake",
        )

    def CreateTopic(self, request):
        self._record("CreateTopic", request)
        topic_id = self._new_id()
        entry = {
            "TopicId": topic_id,
            "LogsetId": request.LogsetId,
            "TopicName": request.TopicName,
            "PartitionCount": request.PartitionCount,
            "Period": request.Period,
            "StorageType": request.StorageType,
            "AutoSplit": request.AutoSplit,
            "MaxSplitPartitions": request.MaxSplitPartitions,
            "Describes": request.Describes,
        }
        if hasattr(request, "HotPeriod"):
            entry["HotPeriod"] = request.HotPeriod
        tags = self._tags(request)
        if tags:
            entry["Tags"] = tags
        self.topics.append(entry)
        return SimpleNamespace(TopicId=topic_id, RequestId="req-fake")

    def ModifyTopic(self, request):
        self._record("ModifyTopic", request)
        for stored in self.topics:
            if stored.get("TopicId") != request.TopicId:
                continue
            stored["TopicName"] = request.TopicName
            stored["PartitionCount"] = request.PartitionCount
            stored["Period"] = request.Period
            stored["StorageType"] = request.StorageType
            stored["AutoSplit"] = request.AutoSplit
            stored["MaxSplitPartitions"] = request.MaxSplitPartitions
            stored["Describes"] = request.Describes
            if hasattr(request, "HotPeriod"):
                stored["HotPeriod"] = request.HotPeriod
            else:
                stored.pop("HotPeriod", None)
            tags = self._tags(request)
            if tags:
                stored["Tags"] = tags
            else:
                stored.pop("Tags", None)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteTopic(self, request):
        self._record("DeleteTopic", request)
        self.topics = [t for t in self.topics if t.get("TopicId") != request.TopicId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load_cls",
        lambda: (FakeModels(), SimpleNamespace(ClsClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# request-builder / tag helper tests
# ---------------------------------------------------------------------------


def test_build_tags_sorted_stringified():
    items = mod.build_tags(FakeModels(), {"z": 2, "a": "x"})
    assert [(i.Key, i.Value) for i in items] == [("a", "x"), ("z", "2")]


def test_build_tags_empty_and_none():
    assert mod.build_tags(FakeModels(), None) == []
    assert mod.build_tags(FakeModels(), {}) == []


def test_describe_request_base_fields():
    request = mod.build_describe_request(FakeModels(), offset=7)
    assert request.Offset == 7
    assert request.Limit == 100
    assert not hasattr(request, "Filters")


def test_describe_request_filters_each_present_key():
    request = mod.build_describe_request(FakeModels(), topic_id="topic-9", logset_id="logset-1", name="app")
    names = {item.Key: item.Values for item in request.Filters}
    assert names == {"topicId": ["topic-9"], "logsetId": ["logset-1"], "topicName": ["app"]}


def test_apply_omits_logset_when_not_creating():
    request = mod._apply(FakeModels().CreateTopicRequest(), FakeModels(), _params())
    assert not hasattr(request, "LogsetId")
    assert request.TopicName == "network-flow"
    assert request.Period == 30


def test_create_request_fields():
    request = mod.build_create_request(FakeModels(), _params(period=7, tags={"env": "prod"}))
    assert request.LogsetId == "logset-1"
    assert request.TopicName == "network-flow"
    assert request.PartitionCount == 1
    assert request.Period == 7
    assert request.StorageType == "hot"
    assert request.AutoSplit is True
    assert request.MaxSplitPartitions == 50
    assert request.Describes == ""
    assert [(t.Key, t.Value) for t in request.Tags] == [("env", "prod")]


def test_create_request_omits_optional_when_absent():
    request = mod.build_create_request(FakeModels(), _params())
    assert not hasattr(request, "HotPeriod")
    assert not hasattr(request, "Tags")


def test_create_request_hot_period_included():
    request = mod.build_create_request(FakeModels(), _params(hot_period=3))
    assert request.HotPeriod == 3


def test_update_request_sets_topic_id():
    request = mod.build_update_request(FakeModels(), "topic-1", _params(description="flow logs"))
    assert request.TopicId == "topic-1"
    assert request.Describes == "flow logs"
    assert not hasattr(request, "LogsetId")  # logset only set at creation


def test_delete_request_fields():
    request = mod.build_delete_request(FakeModels(), "topic-1")
    assert request.TopicId == "topic-1"


def test_tags_from_sdk_values():
    assert mod._tags([{"Key": "a", "Value": "1"}, {"Key": "b", "Value": "2"}]) == {"a": "1", "b": "2"}
    assert mod._tags(None) == {}
    assert mod._tags([]) == {}


def test_desired_mapping_includes_optionals():
    value = mod._desired(_params(hot_period=3, tags={"env": "prod"}))
    assert value == {
        "TopicName": "network-flow",
        "PartitionCount": 1,
        "Period": 30,
        "StorageType": "hot",
        "AutoSplit": True,
        "MaxSplitPartitions": 50,
        "Describes": "",
        "HotPeriod": 3,
        "Tags": {"env": "prod"},
    }


def test_desired_mapping_without_optionals():
    value = mod._desired(_params())
    assert "HotPeriod" not in value
    assert "Tags" not in value


def test_matches_detects_drift():
    desired = mod._desired(_params(period=30, tags={"env": "prod"}))
    assert mod._matches(_topic(), desired) is True
    drifted = mod._desired(_params(period=7))
    assert mod._matches(_topic(), drifted) is False


def test_matches_compares_tags_as_dict():
    desired = mod._desired(_params(tags={"env": "prod"}))
    assert mod._matches(_topic(), desired) is True
    assert mod._matches(_topic(Tags=[{"Key": "env", "Value": "staging"}]), desired) is False


# ---------------------------------------------------------------------------
# find_topic tests
# ---------------------------------------------------------------------------


def test_find_topic_no_match_returns_none(monkeypatch):
    fake = FakeClsClient([_topic(TopicName="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find_topic(module, fake, FakeModels(), None, "logset-1", "ghost") is None


def test_find_topic_by_topic_id(monkeypatch):
    fake = FakeClsClient([_topic(TopicId="topic-2", TopicName="other"), _topic()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(topic_id="topic-1"))
    value = mod.find_topic(module, fake, FakeModels(), "topic-1", "logset-1", None)
    assert value["TopicId"] == "topic-1"


def test_find_topic_by_logset_and_name(monkeypatch):
    fake = FakeClsClient([_topic(TopicName="other"), _topic()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find_topic(module, fake, FakeModels(), None, "logset-1", "network-flow")
    assert value["TopicId"] == "topic-1"


def test_find_topic_name_mismatch_ignores_different_logset(monkeypatch):
    fake = FakeClsClient([_topic(LogsetId="logset-other", TopicName="network-flow"), _topic()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find_topic(module, fake, FakeModels(), None, "logset-1", "network-flow")
    assert value["TopicId"] == "topic-1"


def test_find_topic_multiple_matches_fails(monkeypatch):
    fake = FakeClsClient([_topic(), _topic(TopicId="topic-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find_topic(module, fake, FakeModels(), None, "logset-1", "network-flow")
    assert "Multiple CLS topics have the requested name" in exc.value.args[0]["msg"]


def test_find_topic_paginates_past_100(monkeypatch):
    topics = [_topic(TopicId="bulk-%04d" % i, TopicName="bulk-%04d" % i) for i in range(101)]
    topics.append(_topic())
    fake = FakeClsClient(topics)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find_topic(module, fake, FakeModels(), None, "logset-1", "network-flow")
    assert value["TopicId"] == "topic-1"
    list_calls = [c for c in fake.calls if c[0] == "DescribeTopics"]
    assert len(list_calls) == 2  # pages of 100
    assert [c[1].Offset for c in list_calls] == [0, 100]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced():
    module_args(state="present", logset_id="logset-1")  # neither topic_id nor name
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_creates_topic(monkeypatch):
    fake = FakeClsClient()
    _make_module(monkeypatch, fake)
    _run_args(period=7, tags={"env": "prod"})
    result = run(mod.run_module)
    assert result["changed"] is True
    topic = result["topic"]
    assert topic["TopicId"] == "topic-10001"
    assert topic["TopicName"] == "network-flow"
    assert topic["Period"] == 7
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeTopics") == 2  # find + post-wait refetch
    assert names.count("CreateTopic") == 1


def test_present_creates_with_hot_period(monkeypatch):
    fake = FakeClsClient()
    _make_module(monkeypatch, fake)
    _run_args(hot_period=3)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"]["HotPeriod"] == 3


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeClsClient([_topic()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["topic"]["TopicId"] == "topic-1"
    names = [c[0] for c in fake.calls]
    assert "ModifyTopic" not in names
    assert "CreateTopic" not in names


def test_present_period_drift_triggers_update(monkeypatch):
    fake = FakeClsClient([_topic()])
    _make_module(monkeypatch, fake)
    _run_args(period=7)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"]["Period"] == 7
    modify = [c for c in fake.calls if c[0] == "ModifyTopic"][0][1]
    assert modify.TopicId == "topic-1"
    assert modify.Period == 7


def test_present_tag_drift_triggers_update(monkeypatch):
    fake = FakeClsClient([_topic()])
    _make_module(monkeypatch, fake)
    _run_args(tags={"env": "staging"})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"]["Tags"] == [{"Key": "env", "Value": "staging"}]


def test_present_missing_name_for_new_topic_fails(monkeypatch):
    fake = FakeClsClient()
    _make_module(monkeypatch, fake)
    _run_args(topic_id="topic-ghost", name=None)  # required_one_of satisfied, but topic absent
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name is required when creating a CLS topic" in exc.value.args[0]["msg"]


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load_cls",
        lambda: (FakeModels(), SimpleNamespace(ClsClient=object)),
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
    assert payload["error_code"] is None
    assert payload["request_id"] is None


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeClsClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"] is None
    assert not any("CreateTopic" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeClsClient([_topic()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(period=7))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"]["Period"] == 30  # pre-change state reported
    assert not any("ModifyTopic" == c[0] for c in fake.calls)


def test_absent_removes_topic(monkeypatch):
    fake = FakeClsClient([_topic()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="network-flow")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteTopic"][0][1]
    assert delete.TopicId == "topic-1"
    assert fake.topics == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeClsClient([_topic()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["topic"] is None
    assert not any("DeleteTopic" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeClsClient([_topic()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(state="absent", name="network-flow"))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"] is not None  # pre-change state reported
    assert not any("DeleteTopic" == c[0] for c in fake.calls)
    assert len(fake.topics) == 1


def test_multiple_name_matches_fail(monkeypatch):
    fake = FakeClsClient([_topic(), _topic(TopicId="topic-2")])
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple CLS topics have the requested name" in exc.value.args[0]["msg"]
