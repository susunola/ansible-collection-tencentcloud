"""Unit tests for the cmq_subscription write module (helpers + run_module).

Creates, updates and deletes CMQ topic push subscriptions through the TDMQ
client. find() lists the topic's subscriptions (Offset 0, Limit 100) and
returns the first SubscriptionName match — no paging, no multi-match fail.
Protocol and Endpoint are immutable on an existing subscription
(require_immutable_unchanged); notify_strategy / notify_content_format /
filter_tags / binding_key drift goes through ModifyCmqSubscriptionAttribute,
which carries FilterTags (plural). Creation goes through
CreateCmqSubscribe, which carries FilterTag (singular). topic_name,
subscription_name and endpoint are required at module construction for
absent runs too.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cmq_subscription as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


class _SdkError(Exception):
    """Stand-in for TencentCloudSDKException carrying a code/request id."""

    def __init__(self, code, message="", request_id=None):
        super(_SdkError, self).__init__(message)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def _subscription(**overrides):
    """API-shaped stored subscription; fresh copy per call."""
    item = {
        "topic_name": "order-events",
        "subscription_name": "order-webhook",
        "protocol": "http",
        "endpoint": "https://example.com/events",
        "notify_strategy": "BACKOFF_RETRY",
        "notify_content_format": "JSON",
        "filter_tags": ["tag-a"],
        "binding_key": ["key-a"],
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "topic_name": "order-events",
        "subscription_name": "order-webhook",
        "protocol": "http",
        "endpoint": "https://example.com/events",
        "notify_strategy": "BACKOFF_RETRY",
        "notify_content_format": "JSON",
        "filter_tags": ["tag-a"],
        "binding_key": ["key-a"],
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    params = _params(**extra)
    args = {k: v for k, v in params.items() if v is not None}
    for key, value in extra.items():
        if key.startswith("_"):
            args[key] = value
    return module_args(**args)


def _serialize_sub(s):
    """Map a stored subscription dict onto its API response shape."""
    return {
        "SubscriptionName": s["subscription_name"],
        "Protocol": s["protocol"],
        "Endpoint": s["endpoint"],
        "NotifyStrategy": s["notify_strategy"],
        "NotifyContentFormat": s["notify_content_format"],
        "FilterTags": list(s["filter_tags"]),
        "BindingKey": list(s["binding_key"]),
    }


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


class FakeTdmqClient(object):
    """In-memory TdmqClient stand-in storing subscription dicts.

    DescribeCmqSubscriptionDetail returns every subscription of the topic
    (the module filters by SubscriptionName itself); Create/Modify/Delete
    act by topic_name + subscription_name. Create stores FilterTag
    (singular), Modify rewrites FilterTags (plural).
    """

    def __init__(self, subscriptions=None):
        self.subscriptions = [dict(s) for s in (subscriptions or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _find_index(self, topic, name):
        for i, sub in enumerate(self.subscriptions):
            if sub["topic_name"] == topic and sub["subscription_name"] == name:
                return i
        return -1

    def DescribeCmqSubscriptionDetail(self, request):
        self._record("DescribeCmqSubscriptionDetail", request)
        items = [s for s in self.subscriptions if s["topic_name"] == request.TopicName]
        return SimpleNamespace(SubscriptionSet=[FakeResource(_serialize_sub(s)) for s in items], RequestId="req-fake")

    def CreateCmqSubscribe(self, request):
        self._record("CreateCmqSubscribe", request)
        self.subscriptions.append({
            "topic_name": request.TopicName,
            "subscription_name": request.SubscriptionName,
            "protocol": request.Protocol,
            "endpoint": request.Endpoint,
            "notify_strategy": request.NotifyStrategy,
            "notify_content_format": request.NotifyContentFormat,
            "filter_tags": list(getattr(request, "FilterTag", None) or []),
            "binding_key": list(getattr(request, "BindingKey", None) or []),
        })
        return SimpleNamespace(RequestId="req-fake")

    def ModifyCmqSubscriptionAttribute(self, request):
        self._record("ModifyCmqSubscriptionAttribute", request)
        i = self._find_index(request.TopicName, request.SubscriptionName)
        if i >= 0:
            self.subscriptions[i]["notify_strategy"] = request.NotifyStrategy
            self.subscriptions[i]["notify_content_format"] = request.NotifyContentFormat
            self.subscriptions[i]["filter_tags"] = list(request.FilterTags or [])
            self.subscriptions[i]["binding_key"] = list(request.BindingKey or [])
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCmqSubscribe(self, request):
        self._record("DeleteCmqSubscribe", request)
        i = self._find_index(request.TopicName, request.SubscriptionName)
        if i >= 0:
            self.subscriptions.pop(i)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TdmqClient=object)),
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
            raise _SdkError("AuthFailure", "auth rejected", request_id="req-err")

        return boom


# ---------------------------------------------------------------------------
# helper tests
# ---------------------------------------------------------------------------


def test_find_matches_subscription_name():
    fake = FakeTdmqClient([_subscription()])
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), "order-events", "order-webhook")
    assert value["SubscriptionName"] == "order-webhook"
    assert value["Protocol"] == "http"
    request = module.sdk_calls[0][1]
    assert request.TopicName == "order-events"
    assert request.Offset == 0
    assert request.Limit == 100
    assert module.sdk_calls[0][0].__name__ == "DescribeCmqSubscriptionDetail"


def test_find_picks_named_subscription_among_many():
    fake = FakeTdmqClient([
        _subscription(subscription_name="other-hook", endpoint="https://other"),
        _subscription(),
    ])
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), "order-events", "order-webhook")
    assert value["Endpoint"] == "https://example.com/events"


def test_find_no_match_returns_none():
    fake = FakeTdmqClient()
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), "order-events", "ghost") is None


def test_find_ignores_other_topics():
    fake = FakeTdmqClient([_subscription(topic_name="other-topic")])
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), "order-events", "order-webhook") is None


def test_target_sorts_tag_lists():
    params = _params(filter_tags=["z", "a"], binding_key=["y", "b"])
    value = mod.target(params)
    assert value["FilterTags"] == ["a", "z"]
    assert value["BindingKey"] == ["b", "y"]
    assert value["Protocol"] == "http"
    assert value["Endpoint"] == "https://example.com/events"


def test_current_fields_reads_filter_tags():
    value = mod.current_fields(_serialize_sub(_subscription(filter_tags=["b", "a"])))
    assert value["FilterTags"] == ["a", "b"]
    assert value["BindingKey"] == ["key-a"]


def test_current_fields_falls_back_to_filter_tag():
    value = mod.current_fields({"SubscriptionName": "s", "FilterTag": ["q"], "BindingKey": None})
    assert value["FilterTags"] == ["q"]
    assert value["BindingKey"] == []


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("required", ["topic_name", "subscription_name", "endpoint"])
def test_missing_required_fails(monkeypatch, required):
    fake = FakeTdmqClient()
    _make_module(monkeypatch, fake)
    _run_args(**{required: None})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert required in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_absent_noop_when_missing(monkeypatch):
    fake = FakeTdmqClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["subscription"] is None
    assert [c[0] for c in fake.calls] == ["DescribeCmqSubscriptionDetail"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakeTdmqClient([_subscription()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["subscription"]["SubscriptionName"] == "order-webhook"
    assert result["diff"]["before"]["Protocol"] == "http"
    assert result["diff"]["after"] is None
    assert [c[0] for c in fake.calls] == ["DescribeCmqSubscriptionDetail"]
    assert len(fake.subscriptions) == 1


def test_absent_deletes_subscription(monkeypatch):
    fake = FakeTdmqClient([_subscription()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["subscription"] is None
    assert [c[0] for c in fake.calls] == [
        "DescribeCmqSubscriptionDetail",
        "DeleteCmqSubscribe",
    ]
    deleted = fake.calls[1][1]
    assert deleted.TopicName == "order-events"
    assert deleted.SubscriptionName == "order-webhook"
    assert fake.subscriptions == []


def test_present_noop_when_subscription_matches(monkeypatch):
    fake = FakeTdmqClient([_subscription()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["subscription"]["SubscriptionName"] == "order-webhook"
    assert [c[0] for c in fake.calls] == ["DescribeCmqSubscriptionDetail"]


def test_present_updates_notify_strategy(monkeypatch):
    fake = FakeTdmqClient([_subscription()])
    _make_module(monkeypatch, fake)
    _run_args(notify_strategy="EXPONENTIAL_DECAY_RETRY")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["subscription"]["NotifyStrategy"] == "EXPONENTIAL_DECAY_RETRY"
    assert [c[0] for c in fake.calls] == [
        "DescribeCmqSubscriptionDetail",
        "ModifyCmqSubscriptionAttribute",
        "DescribeCmqSubscriptionDetail",
    ]
    updated = fake.calls[1][1]
    assert updated.TopicName == "order-events"
    assert updated.SubscriptionName == "order-webhook"
    assert updated.NotifyStrategy == "EXPONENTIAL_DECAY_RETRY"
    assert updated.NotifyContentFormat == "JSON"
    assert updated.FilterTags == ["tag-a"]
    assert updated.BindingKey == ["key-a"]
    assert not hasattr(updated, "FilterTag")
    assert fake.subscriptions[0]["notify_strategy"] == "EXPONENTIAL_DECAY_RETRY"


def test_present_updates_filter_tags(monkeypatch):
    fake = FakeTdmqClient([_subscription()])
    _make_module(monkeypatch, fake)
    _run_args(filter_tags=["tag-b"])
    result = run(mod.run_module)
    assert result["changed"] is True
    updated = fake.calls[1][1]
    assert updated.FilterTags == ["tag-b"]
    assert fake.subscriptions[0]["filter_tags"] == ["tag-b"]


def test_present_protocol_drift_on_existing_fails(monkeypatch):
    fake = FakeTdmqClient([_subscription()])
    _make_module(monkeypatch, fake)
    _run_args(protocol="queue")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed on an existing CMQ subscription" in payload["msg"]
    assert payload["immutable_changes"]["Protocol"] == {"before": "http", "after": "queue"}
    assert payload["replacement_required"] is True
    assert [c[0] for c in fake.calls] == ["DescribeCmqSubscriptionDetail"]


def test_present_endpoint_drift_on_existing_fails(monkeypatch):
    fake = FakeTdmqClient([_subscription()])
    _make_module(monkeypatch, fake)
    _run_args(endpoint="https://other.example.com/events")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed on an existing CMQ subscription" in payload["msg"]
    assert payload["immutable_changes"]["Endpoint"]["after"] == "https://other.example.com/events"
    assert [c[0] for c in fake.calls] == ["DescribeCmqSubscriptionDetail"]


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeTdmqClient([_subscription()])
    _make_module(monkeypatch, fake)
    _run_args(notify_strategy="EXPONENTIAL_DECAY_RETRY", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["subscription"]["NotifyStrategy"] == "BACKOFF_RETRY"
    assert result["diff"]["before"]["NotifyStrategy"] == "BACKOFF_RETRY"
    assert result["diff"]["after"]["NotifyStrategy"] == "EXPONENTIAL_DECAY_RETRY"
    assert [c[0] for c in fake.calls] == ["DescribeCmqSubscriptionDetail"]
    assert fake.subscriptions[0]["notify_strategy"] == "BACKOFF_RETRY"


def test_present_creates_subscription(monkeypatch):
    fake = FakeTdmqClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["subscription"]["SubscriptionName"] == "order-webhook"
    assert [c[0] for c in fake.calls] == [
        "DescribeCmqSubscriptionDetail",
        "CreateCmqSubscribe",
        "DescribeCmqSubscriptionDetail",
    ]
    created = fake.calls[1][1]
    assert created.TopicName == "order-events"
    assert created.SubscriptionName == "order-webhook"
    assert created.Protocol == "http"
    assert created.Endpoint == "https://example.com/events"
    assert created.NotifyStrategy == "BACKOFF_RETRY"
    assert created.NotifyContentFormat == "JSON"
    assert created.FilterTag == ["tag-a"]
    assert created.BindingKey == ["key-a"]
    assert not hasattr(created, "FilterTags")
    assert len(fake.subscriptions) == 1
    assert fake.subscriptions[0]["subscription_name"] == "order-webhook"


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTdmqClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["subscription"] is None
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["SubscriptionName"] == "order-webhook"
    assert [c[0] for c in fake.calls] == ["DescribeCmqSubscriptionDetail"]
    assert fake.subscriptions == []


def test_sdk_failure_reports_error_payload(monkeypatch):
    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "auth rejected"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeTdmqClient([_subscription()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.main)
    assert result["changed"] is False
    assert result["subscription"]["SubscriptionName"] == "order-webhook"
