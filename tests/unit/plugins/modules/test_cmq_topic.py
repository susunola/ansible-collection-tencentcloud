"""Unit tests for the cmq_topic write module (helpers + run_module).

Creates, updates and deletes CMQ topics idempotently. Lookup is a single
DescribeCmqTopics call matched by exact topic name, failing on multiple
matches. present converges MaxMsgSize / MsgRetentionSeconds / Trace via
ModifyCmqTopicAttribute (existing) or creates with FilterType + Tags then
re-finds; absent deletes by name. FilterType is immutable on existing
topics (settable only at creation).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cmq_topic as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

_ORIG_LOAD = mod._load  # captured before any monkeypatching


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "topic_name": "order-events",
        "max_msg_size": 65536,
        "message_retention_seconds": 86400,
        "filter_type": 1,
        "trace": False,
        "tags": {},
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    return module_args(**{k: v for k, v in _params(**extra).items() if v is not None})


def _load_real_or_fake():
    """Exercise the real lazy SDK import body when the SDK is installed.

    The coverage gate runs with the SDK present (see ci.yml "SDK contract
    tests"), so the real import executes and the ``_load`` body is covered;
    in SDK-less environments (``ansible-test units``) the import falls back
    to fake models so the same test file stays portable.
    """
    try:
        return _ORIG_LOAD()
    except ImportError:
        return FakeModels(), SimpleNamespace(TdmqClient=object)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or {}

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


def _topic(topic_id, name, **overrides):
    """A serialized CMQ topic record matching the SDK's DescribeCmqTopics."""
    record = {
        "TopicName": name,
        "TopicId": topic_id,
        "MaxMsgSize": 65536,
        "MsgRetentionSeconds": 86400,
        "FilterType": 1,
        "Trace": False,
    }
    record.update(overrides)
    return record


class FakeCmqClient(object):
    """In-memory TdmqClient stand-in storing CMQ topic records.

    DescribeCmqTopics filters by the request TopicName (mirroring the SDK);
    CreateCmqTopic assigns a fresh TopicId; ModifyCmqTopicAttribute and
    DeleteCmqTopic address records by TopicName.
    """

    def __init__(self, topics=None):
        self.topics = [dict(t) for t in (topics or [])]
        self.calls = []
        self._next_id = 1

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeCmqTopics(self, request):
        self._record("DescribeCmqTopics", request)
        topics = [t for t in self.topics if t["TopicName"] == request.TopicName]
        return SimpleNamespace(TopicList=[FakeResource(dict(t)) for t in topics])

    def CreateCmqTopic(self, request):
        self._record("CreateCmqTopic", request)
        topic_id = "cmq-%d" % self._next_id
        self._next_id += 1
        self.topics.append(
            {
                "TopicName": request.TopicName,
                "TopicId": topic_id,
                "MaxMsgSize": request.MaxMsgSize,
                "MsgRetentionSeconds": request.MsgRetentionSeconds,
                "FilterType": request.FilterType,
                "Trace": request.Trace,
                "Tags": request.Tags,
            }
        )
        return SimpleNamespace(TopicId=topic_id)

    def ModifyCmqTopicAttribute(self, request):
        self._record("ModifyCmqTopicAttribute", request)
        for topic in self.topics:
            if topic["TopicName"] == request.TopicName:
                topic["MaxMsgSize"] = request.MaxMsgSize
                topic["MsgRetentionSeconds"] = request.MsgRetentionSeconds
                topic["Trace"] = request.Trace
        return SimpleNamespace()

    def DeleteCmqTopic(self, request):
        self._record("DeleteCmqTopic", request)
        self.topics = [t for t in self.topics if t["TopicName"] != request.TopicName]
        return SimpleNamespace()


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", _load_real_or_fake)
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# request-builder and mapping helper tests
# ---------------------------------------------------------------------------


def test_describe_request_fields():
    request = mod.describe_request(FakeModels(), "order-events")
    assert type(request).__name__ == "DescribeCmqTopicsRequest"
    assert request.Offset == 0
    assert request.Limit == 100
    assert request.TopicName == "order-events"


def test_tags_sorted_and_stringified():
    items = mod.tags(FakeModels(), {"b": 2, "a": "x", "c": None})
    assert [i.Key for i in items] == ["a", "b", "c"]
    assert [i.Value for i in items] == ["x", "2", "None"]


def test_tags_empty_returns_empty_list():
    assert mod.tags(FakeModels(), {}) == []


def test_desired_maps_params():
    params = _params(topic_name="orders", max_msg_size=1024, message_retention_seconds=3600, filter_type=2, trace=True)
    assert mod.desired(params) == {
        "TopicName": "orders",
        "MaxMsgSize": 1024,
        "MsgRetentionSeconds": 3600,
        "FilterType": 2,
        "Trace": True,
    }


# ---------------------------------------------------------------------------
# find helper tests
# ---------------------------------------------------------------------------


def test_find_matches_by_name():
    fake = FakeCmqClient([_topic("cmq-1", "order-events"), _topic("cmq-2", "other")])
    found = mod.find(FakeModule(), fake, FakeModels(), "order-events")
    assert found["TopicId"] == "cmq-1"
    assert found["TopicName"] == "order-events"


def test_find_no_match_returns_none():
    fake = FakeCmqClient([_topic("cmq-1", "other")])
    assert mod.find(FakeModule(), fake, FakeModels(), "order-events") is None


def test_find_empty_store_returns_none():
    assert mod.find(FakeModule(), FakeCmqClient(), FakeModels(), "order-events") is None


def test_find_multiple_name_matches_fail():
    fake = FakeCmqClient([_topic("cmq-1", "dup"), _topic("cmq-2", "dup")])
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(FakeModule(), fake, FakeModels(), "dup")
    payload = exc.value.args[0]
    assert payload["msg"] == "Multiple CMQ topics have the requested name"
    assert payload["topic_name"] == "dup"


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeCmqClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["topic"] is None
    assert not any(name == "DeleteCmqTopic" for name, request in fake.calls)


def test_absent_deletes_topic(monkeypatch):
    fake = FakeCmqClient([_topic("cmq-1", "order-events")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"] is None
    delete = [req for name, req in fake.calls if name == "DeleteCmqTopic"][0]
    assert delete.TopicName == "order-events"
    assert fake.topics == []  # record removed


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCmqClient([_topic("cmq-1", "order-events")])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"]["TopicId"] == "cmq-1"  # current kept for preview
    assert result["diff"]["before"]["TopicName"] == "order-events"
    assert result["diff"]["after"] is None
    assert not any(name == "DeleteCmqTopic" for name, request in fake.calls)
    assert len(fake.topics) == 1  # remote untouched


def test_present_creates_topic_and_refinds(monkeypatch):
    fake = FakeCmqClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"]["TopicId"] == "cmq-1"
    assert result["topic"]["TopicName"] == "order-events"
    assert [name for name, request in fake.calls] == ["DescribeCmqTopics", "CreateCmqTopic", "DescribeCmqTopics"]
    create = [req for name, req in fake.calls if name == "CreateCmqTopic"][0]
    assert create.TopicName == "order-events"
    assert create.MaxMsgSize == 65536
    assert create.MsgRetentionSeconds == 86400
    assert create.FilterType == 1
    assert create.Trace is False
    assert create.Tags == []  # no tags requested


def test_present_create_sends_sorted_tags(monkeypatch):
    fake = FakeCmqClient()
    _make_module(monkeypatch, fake)
    _run_args(tags={"env": "prod", "team": "pay"})
    run(mod.run_module)
    create = [req for name, req in fake.calls if name == "CreateCmqTopic"][0]
    assert [t.Key for t in create.Tags] == ["env", "team"]  # sorted by key
    assert [t.Value for t in create.Tags] == ["prod", "pay"]


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeCmqClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"] is None
    assert result["diff"]["before"] is None
    # falsy Trace is retained by the diff normalizer (only empty containers stripped)
    assert result["diff"]["after"] == {
        "TopicName": "order-events",
        "MaxMsgSize": 65536,
        "MsgRetentionSeconds": 86400,
        "FilterType": 1,
        "Trace": False,
    }
    assert not any(name == "CreateCmqTopic" for name, request in fake.calls)


def test_present_unchanged_is_noop(monkeypatch):
    fake = FakeCmqClient([_topic("cmq-1", "order-events")])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["topic"]["TopicId"] == "cmq-1"
    assert not any(name in ("CreateCmqTopic", "ModifyCmqTopicAttribute") for name, request in fake.calls)


def test_present_retention_drift_modifies(monkeypatch):
    fake = FakeCmqClient([_topic("cmq-1", "order-events", MsgRetentionSeconds=3600)])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"]["MsgRetentionSeconds"] == 86400  # re-find after modify
    assert [name for name, request in fake.calls] == ["DescribeCmqTopics", "ModifyCmqTopicAttribute", "DescribeCmqTopics"]
    modify = [req for name, req in fake.calls if name == "ModifyCmqTopicAttribute"][0]
    assert modify.TopicName == "order-events"
    assert modify.MsgRetentionSeconds == 86400


def test_present_max_msg_size_drift_modifies(monkeypatch):
    fake = FakeCmqClient([_topic("cmq-1", "order-events", MaxMsgSize=1024)])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    modify = [req for name, req in fake.calls if name == "ModifyCmqTopicAttribute"][0]
    assert modify.MaxMsgSize == 65536


def test_present_trace_drift_modifies(monkeypatch):
    fake = FakeCmqClient([_topic("cmq-1", "order-events", Trace=True)])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"]["Trace"] is False
    modify = [req for name, req in fake.calls if name == "ModifyCmqTopicAttribute"][0]
    assert modify.Trace is False


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeCmqClient([_topic("cmq-1", "order-events", MsgRetentionSeconds=3600)])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"]["MsgRetentionSeconds"] == 3600  # pre-update current
    assert result["diff"]["before"]["MsgRetentionSeconds"] == 3600
    assert result["diff"]["after"]["MsgRetentionSeconds"] == 86400
    assert not any(name == "ModifyCmqTopicAttribute" for name, request in fake.calls)


def test_present_filter_type_drift_fails_immutable(monkeypatch):
    fake = FakeCmqClient([_topic("cmq-1", "order-events", FilterType=2)])
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Immutable fields cannot be changed on an existing CMQ topic"
    assert payload["immutable_changes"] == {"FilterType": {"before": 2, "after": 1}}
    assert payload["replacement_required"] is True
    assert not any(name == "ModifyCmqTopicAttribute" for name, request in fake.calls)


def test_present_filter_type_drift_fails_even_in_check_mode(monkeypatch):
    fake = FakeCmqClient([_topic("cmq-1", "order-events", FilterType=2)])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "Immutable fields cannot be changed on an existing CMQ topic"


def test_invalid_filter_type_choice_fails_validation(monkeypatch):
    _make_module(monkeypatch, FakeCmqClient())
    _run_args(filter_type=3)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "filter_type" in exc.value.args[0]["msg"]


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TdmqClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: _BoomClient())
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeCmqClient([_topic("cmq-1", "order-events")])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.main)
    assert result["changed"] is False
    assert result["topic"]["TopicId"] == "cmq-1"
