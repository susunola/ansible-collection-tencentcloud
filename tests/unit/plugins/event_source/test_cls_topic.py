"""Unit tests for the cls_topic event source helpers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import asyncio
import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.event_source import (
    cls_topic as src,
)


class FakeRequest(object):
    pass


class FakeModels(object):
    SearchLogRequest = FakeRequest
    DescribeTopicsRequest = FakeRequest


class FakeLogItem(object):
    def __init__(self, raw):
        self.RawLog = raw


class FakeSearchResponse(object):
    def __init__(self, items, context=None):
        self.Results = items
        self.Context = context


class FakeTopicsResponse(object):
    def __init__(self, topics):
        self.Topics = topics


class FakeTopic(object):
    def __init__(self, topic_id, topic_name):
        self.TopicId = topic_id
        self.TopicName = topic_name


class FakeSearchClient(object):
    def __init__(self, response):
        self.response = response
        self.request = None

    def SearchLog(self, request):
        self.request = request
        return self.response


# ---------------------------------------------------------------------------
# request building / search
# ---------------------------------------------------------------------------


def test_build_search_request_fields():
    request = src.build_search_request(FakeModels, "topic-1", "level:ERROR", 1, 2, 50, "ctx")
    assert request.TopicId == "topic-1"
    assert request.Query == "level:ERROR"
    assert request.From == 1
    assert request.To == 2
    assert request.Limit == 50
    assert request.Context == "ctx"


def test_build_search_request_without_context():
    request = src.build_search_request(FakeModels, "topic-1", "*", 1, 2, 20, None)
    assert not hasattr(request, "Context")


def test_search_logs_parses_json_records():
    client = FakeSearchClient(
        FakeSearchResponse(
            [FakeLogItem('{"level":"ERROR","msg":"boom"}'), FakeLogItem('{"level":"INFO"}')],
            context="next-ctx",
        )
    )
    records, context = src.search_logs(
        client, FakeModels, "t", "*", 1, 2, 20, None,
    )
    assert records == [{"level": "ERROR", "msg": "boom"}, {"level": "INFO"}]
    assert context == "next-ctx"
    assert client.request.TopicId == "t"
    assert client.request.From == 1


def test_search_logs_falls_back_to_message_on_bad_json():
    client = FakeSearchClient(FakeSearchResponse([FakeLogItem("not json")]))
    records, _context = src.search_logs(
        client, FakeModels, "t", "*", 1, 2, 20, None,
    )
    assert records == [{"message": "not json"}]


def test_search_logs_empty_results():
    client = FakeSearchClient(FakeSearchResponse([]))
    records, context = src.search_logs(client, FakeModels, "t", "*", 1, 2, 20, None)
    assert records == []
    assert context is None


# ---------------------------------------------------------------------------
# topic resolution
# ---------------------------------------------------------------------------


class FakeTopicClient(object):
    def __init__(self, topics):
        self.topics = topics
        self.calls = 0

    def DescribeTopics(self, request):
        self.calls += 1
        return FakeTopicsResponse(self.topics)


def test_describe_topic_id_matches_name():
    client = FakeTopicClient(
        [FakeTopic("topic-other", "other"), FakeTopic("topic-app", "app")]
    )
    topic_id = src.describe_topic_id(client, FakeModels, "ap-guangzhou", "app")
    assert topic_id == "topic-app"
    assert client.calls == 1


def test_describe_topic_id_raises_when_missing():
    client = FakeTopicClient([FakeTopic("topic-other", "other")])
    with pytest.raises(RuntimeError, match="not found"):
        src.describe_topic_id(client, FakeModels, "ap-guangzhou", "missing")


# ---------------------------------------------------------------------------
# env helpers
# ---------------------------------------------------------------------------


def test_env_or_prefers_args(monkeypatch):
    monkeypatch.setenv("TENCENTCLOUD_REGION", "ap-shanghai")
    assert src._env_or("region", {"region": "ap-guangzhou"}, "TENCENTCLOUD_REGION") == "ap-guangzhou"
    assert src._env_or("region", {}, "TENCENTCLOUD_REGION") == "ap-shanghai"
    assert src._env_or("token", {}, "TENCENTCLOUD_TOKEN") is None


# ---------------------------------------------------------------------------
# _build_client error paths (SDK imports faked)
# ---------------------------------------------------------------------------


def _install_fake_sdk(monkeypatch):
    """Register fake tencentcloud.* modules so _build_client imports succeed."""

    class FakeCredential(object):
        def __init__(self, secret_id, secret_key, token=None):
            self.secret_id = secret_id
            self.secret_key = secret_key
            self.token = token

    credential = types.ModuleType("tencentcloud.common.credential")
    credential.Credential = FakeCredential

    http_profile = types.ModuleType("tencentcloud.common.profile.http_profile")
    http_profile.HttpProfile = lambda: None

    client_profile = types.ModuleType("tencentcloud.common.profile.client_profile")
    client_profile.ClientProfile = lambda: None

    cls_client = types.ModuleType("tencentcloud.cls.v20201016.cls_client")
    cls_client.ClsClient = lambda *a, **k: object()

    models = types.ModuleType("tencentcloud.cls.v20201016.models")

    v20201016 = types.ModuleType("tencentcloud.cls.v20201016")
    v20201016.cls_client = cls_client
    v20201016.models = models

    profile_pkg = types.ModuleType("tencentcloud.common.profile")
    profile_pkg.http_profile = http_profile
    profile_pkg.client_profile = client_profile

    common = types.ModuleType("tencentcloud.common")
    common.credential = credential
    common.profile = profile_pkg

    cls_pkg = types.ModuleType("tencentcloud.cls")
    cls_pkg.v20201016 = v20201016

    tencentcloud = types.ModuleType("tencentcloud")
    tencentcloud.common = common
    tencentcloud.cls = cls_pkg

    for name, module in {
        "tencentcloud": tencentcloud,
        "tencentcloud.common": common,
        "tencentcloud.common.credential": credential,
        "tencentcloud.common.profile": profile_pkg,
        "tencentcloud.common.profile.http_profile": http_profile,
        "tencentcloud.common.profile.client_profile": client_profile,
        "tencentcloud.cls": cls_pkg,
        "tencentcloud.cls.v20201016": v20201016,
        "tencentcloud.cls.v20201016.cls_client": cls_client,
        "tencentcloud.cls.v20201016.models": models,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)


def test_build_client_requires_credentials(monkeypatch):
    _install_fake_sdk(monkeypatch)
    monkeypatch.delenv("TENCENTCLOUD_SECRET_ID", raising=False)
    monkeypatch.delenv("TENCENTCLOUD_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="secret_id"):
        src._build_client({})


def test_build_client_requires_region(monkeypatch):
    _install_fake_sdk(monkeypatch)
    monkeypatch.setenv("TENCENTCLOUD_SECRET_ID", "akid")
    monkeypatch.setenv("TENCENTCLOUD_SECRET_KEY", "secret")
    monkeypatch.delenv("TENCENTCLOUD_REGION", raising=False)
    with pytest.raises(RuntimeError, match="region"):
        src._build_client({})


# ---------------------------------------------------------------------------
# main loop
# ---------------------------------------------------------------------------


def _collect_event(queue, timeout=1.0):
    async def _get():
        return await asyncio.wait_for(queue.get(), timeout)

    return asyncio.run(_get())


def test_main_yields_records_and_rolls_window(monkeypatch):
    monkeypatch.setattr(src, "_build_client", lambda args: (None, FakeModels))
    monkeypatch.setattr(src, "describe_topic_id", lambda *a, **k: "topic-1")
    monkeypatch.setattr(src.time, "time", lambda: 1000.0)

    calls = {"n": 0}

    def fake_search_logs(client, models, topic_id, query, from_ms, to_ms, limit, context):
        calls["n"] += 1
        if calls["n"] == 1:
            return [{"level": "ERROR"}], None
        return [], None

    monkeypatch.setattr(src, "search_logs", fake_search_logs)

    async def drive():
        queue = asyncio.Queue()
        task = asyncio.create_task(src.main(queue, {"region": "ap-guangzhou", "topic_name": "app"}))
        event = await asyncio.wait_for(queue.get(), 2.0)
        task.cancel()
        return event

    event = asyncio.run(drive())
    assert event["cls"] == {"level": "ERROR"}
    assert event["topic_id"] == "topic-1"
    assert event["region"] == "ap-guangzhou"


def test_main_emits_error_event_on_api_failure(monkeypatch):
    monkeypatch.setattr(src, "_build_client", lambda args: (None, FakeModels))
    monkeypatch.setattr(src, "describe_topic_id", lambda *a, **k: "topic-1")

    def boom(*args, **kwargs):
        raise RuntimeError("SearchLog failed")

    monkeypatch.setattr(src, "search_logs", boom)

    async def drive():
        queue = asyncio.Queue()
        task = asyncio.create_task(src.main(queue, {"region": "ap-guangzhou", "topic_id": "topic-1"}))
        event = await asyncio.wait_for(queue.get(), 2.0)
        task.cancel()
        return event

    event = asyncio.run(drive())
    assert "error" in event["cls"]
    assert "SearchLog failed" in event["cls"]["error"]
