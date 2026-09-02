"""Unit tests for the cos_bucket event source helpers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import asyncio
import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.event_source import (
    cos_bucket as src,
)


class FakeModels(object):
    GetCallerIdentityRequest = type("GetCallerIdentityRequest", (), {})


# ---------------------------------------------------------------------------
# bucket naming
# ---------------------------------------------------------------------------


def test_bucket_full_name_appends_appid():
    assert src.bucket_full_name("mybucket", "1300000000") == "mybucket-1300000000"


def test_bucket_full_name_idempotent_on_full_name():
    assert src.bucket_full_name("mybucket-1300000000", "1300000000") == "mybucket-1300000000"


def test_bucket_full_name_keeps_unrelated_suffix():
    assert src.bucket_full_name("mybucket-other", "1300000000") == "mybucket-other-1300000000"


# ---------------------------------------------------------------------------
# object listing
# ---------------------------------------------------------------------------


class FakeCosClient(object):
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def list_objects(self, **kwargs):
        self.calls.append(kwargs)
        return self.pages.pop(0)


def _object(key, last_modified="2026-09-01T10:00:00.000Z", etag='"abc"', size=10):
    return {
        "Key": key,
        "LastModified": last_modified,
        "ETag": etag,
        "Size": size,
        "StorageClass": "STANDARD",
    }


def test_list_bucket_objects_parses_page():
    client = FakeCosClient([
        {"Contents": [_object("a.txt"), _object("b.txt")], "IsTruncated": "false"}
    ])
    objects = src.list_bucket_objects(client, "mybucket-1300000000")
    assert objects == [
        {"key": "a.txt", "etag": "abc", "size": 10, "last_modified": "2026-09-01T10:00:00.000Z", "storage_class": "STANDARD"},
        {"key": "b.txt", "etag": "abc", "size": 10, "last_modified": "2026-09-01T10:00:00.000Z", "storage_class": "STANDARD"},
    ]
    assert client.calls[0]["Bucket"] == "mybucket-1300000000"
    assert client.calls[0]["MaxKeys"] == 1000


def test_list_bucket_objects_paginates_with_marker():
    client = FakeCosClient([
        {"Contents": [_object("a.txt")], "IsTruncated": "true", "NextMarker": "a.txt"},
        {"Contents": [_object("b.txt")], "IsTruncated": "false"},
    ])
    objects = src.list_bucket_objects(client, "b")
    assert [o["key"] for o in objects] == ["a.txt", "b.txt"]
    assert "Marker" not in client.calls[0]
    assert client.calls[1]["Marker"] == "a.txt"


def test_list_bucket_objects_uses_prefix():
    client = FakeCosClient([
        {"Contents": [_object("images/a.png")], "IsTruncated": "false"}
    ])
    src.list_bucket_objects(client, "b", prefix="images/")
    assert client.calls[0]["Prefix"] == "images/"


def test_list_bucket_objects_caps_at_max_objects():
    client = FakeCosClient([
        {"Contents": [_object("a.txt"), _object("b.txt"), _object("c.txt")], "IsTruncated": "false"}
    ])
    objects = src.list_bucket_objects(client, "b", max_objects=2)
    assert [o["key"] for o in objects] == ["a.txt", "b.txt"]


def test_list_bucket_objects_empty_bucket():
    client = FakeCosClient([{"Contents": [], "IsTruncated": "false"}])
    assert src.list_bucket_objects(client, "b") == []


# ---------------------------------------------------------------------------
# env helpers
# ---------------------------------------------------------------------------


def test_env_or_prefers_args(monkeypatch):
    monkeypatch.setenv("TENCENTCLOUD_REGION", "ap-shanghai")
    assert src._env_or("region", {"region": "ap-guangzhou"}, "TENCENTCLOUD_REGION") == "ap-guangzhou"
    assert src._env_or("region", {}, "TENCENTCLOUD_REGION") == "ap-shanghai"
    assert src._env_or("token", {}, "TENCENTCLOUD_TOKEN") is None


# ---------------------------------------------------------------------------
# _build_cos_client error paths (qcloud_cos SDK faked)
# ---------------------------------------------------------------------------


def _install_fake_cos_sdk(monkeypatch):
    qcloud_cos = types.ModuleType("qcloud_cos")
    qcloud_cos.CosConfig = lambda **kwargs: kwargs
    qcloud_cos.CosS3Client = lambda config: object()
    monkeypatch.setitem(sys.modules, "qcloud_cos", qcloud_cos)


def test_build_cos_client_requires_credentials(monkeypatch):
    _install_fake_cos_sdk(monkeypatch)
    monkeypatch.delenv("TENCENTCLOUD_SECRET_ID", raising=False)
    monkeypatch.delenv("TENCENTCLOUD_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="secret_id"):
        src._build_cos_client({})


def test_build_cos_client_requires_region(monkeypatch):
    _install_fake_cos_sdk(monkeypatch)
    monkeypatch.setenv("TENCENTCLOUD_SECRET_ID", "akid")
    monkeypatch.setenv("TENCENTCLOUD_SECRET_KEY", "secret")
    monkeypatch.delenv("TENCENTCLOUD_REGION", raising=False)
    with pytest.raises(RuntimeError, match="region"):
        src._build_cos_client({})


# ---------------------------------------------------------------------------
# appid resolution (STS SDK faked)
# ---------------------------------------------------------------------------


def _install_fake_sts_sdk(monkeypatch):
    class FakeCredential(object):
        def __init__(self, secret_id, secret_key, token=None):
            self.secret_id = secret_id
            self.secret_key = secret_key
            self.token = token

    class FakeHttpProfile(object):
        def __init__(self):
            self.endpoint = None
            self.reqTimeout = None

    class FakeClientProfile(object):
        def __init__(self):
            self.httpProfile = None
            self.language = None

    class FakeStsClient(object):
        def __init__(self, *args, **kwargs):
            self.args = args

        def GetCallerIdentity(self, request):
            return type("Resp", (), {"AccountId": 1300000000})()

    credential = types.ModuleType("tencentcloud.common.credential")
    credential.Credential = FakeCredential

    http_profile = types.ModuleType("tencentcloud.common.profile.http_profile")
    http_profile.HttpProfile = FakeHttpProfile

    client_profile = types.ModuleType("tencentcloud.common.profile.client_profile")
    client_profile.ClientProfile = FakeClientProfile

    sts_client = types.ModuleType("tencentcloud.sts.v20180813.sts_client")
    sts_client.StsClient = FakeStsClient

    models = types.ModuleType("tencentcloud.sts.v20180813.models")
    models.GetCallerIdentityRequest = FakeModels.GetCallerIdentityRequest

    v20180813 = types.ModuleType("tencentcloud.sts.v20180813")
    v20180813.sts_client = sts_client
    v20180813.models = models

    profile_pkg = types.ModuleType("tencentcloud.common.profile")
    profile_pkg.http_profile = http_profile
    profile_pkg.client_profile = client_profile

    common = types.ModuleType("tencentcloud.common")
    common.credential = credential
    common.profile = profile_pkg

    sts_pkg = types.ModuleType("tencentcloud.sts")
    sts_pkg.v20180813 = v20180813

    tencentcloud = types.ModuleType("tencentcloud")
    tencentcloud.common = common
    tencentcloud.sts = sts_pkg

    for name, module in {
        "tencentcloud": tencentcloud,
        "tencentcloud.common": common,
        "tencentcloud.common.credential": credential,
        "tencentcloud.common.profile": profile_pkg,
        "tencentcloud.common.profile.http_profile": http_profile,
        "tencentcloud.common.profile.client_profile": client_profile,
        "tencentcloud.sts": sts_pkg,
        "tencentcloud.sts.v20180813": v20180813,
        "tencentcloud.sts.v20180813.sts_client": sts_client,
        "tencentcloud.sts.v20180813.models": models,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)


def test_resolve_appid_prefers_args():
    assert src._resolve_appid({"appid": "1300000001"}) == "1300000001"


def test_resolve_appid_prefers_env(monkeypatch):
    monkeypatch.setenv("TENCENTCLOUD_APPID", "1300000002")
    assert src._resolve_appid({}) == "1300000002"


def test_resolve_appid_falls_back_to_sts(monkeypatch):
    _install_fake_sts_sdk(monkeypatch)
    monkeypatch.delenv("TENCENTCLOUD_APPID", raising=False)
    assert src._resolve_appid({}) == "1300000000"


# ---------------------------------------------------------------------------
# main loop
# ---------------------------------------------------------------------------


def _drive_main(monkeypatch, client, args, poll_results, max_events=1):
    """Run main() for a fixed sequence of poll results, collecting events.

    After the scripted results are exhausted the last result is returned on
    every further poll, so the loop settles into a no-change steady state
    instead of looking like a deletion or emitting spurious events.
    """
    monkeypatch.setattr(src, "_build_cos_client", lambda a: client)
    monkeypatch.setattr(src, "_resolve_appid", lambda a: "1300000000")
    results = list(poll_results)
    steady = poll_results[-1]

    def fake_list(client_, bucket, prefix=None, max_objects=None):
        return results.pop(0) if results else steady

    monkeypatch.setattr(src, "list_bucket_objects", fake_list)

    async def run():
        queue = asyncio.Queue()
        task = asyncio.create_task(src.main(queue, args))
        events = []
        try:
            while len(events) < max_events:
                events.append(await asyncio.wait_for(queue.get(), 2.0))
        except asyncio.TimeoutError:
            pass
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return events

    return asyncio.run(run())


def _obj(key, stamp="2026-09-01T10:00:00.000Z"):
    return {"key": key, "etag": "abc", "size": 1, "last_modified": stamp, "storage_class": "STANDARD"}


def test_main_baseline_then_emits_new_objects(monkeypatch):
    events = _drive_main(
        monkeypatch,
        object(),
        {"region": "ap-guangzhou", "bucket": "mybucket", "appid": "1300000000", "interval": 0.01},
        poll_results=[
            [_obj("a.txt"), _obj("b.txt")],  # baseline: recorded, not emitted
            [_obj("a.txt"), _obj("b.txt"), _obj("c.txt")],  # c.txt is new
        ],
        max_events=1,
    )
    assert len(events) == 1
    assert events[0]["cos"]["key"] == "c.txt"
    assert events[0]["cos"]["event_type"] == "ObjectCreated"
    assert events[0]["cos"]["bucket"] == "mybucket-1300000000"
    assert events[0]["cos"]["region"] == "ap-guangzhou"


def test_main_emits_changed_last_modified(monkeypatch):
    events = _drive_main(
        monkeypatch,
        object(),
        {"region": "ap-guangzhou", "bucket": "b", "interval": 0.01},
        poll_results=[
            [_obj("a.txt", stamp="2026-09-01T10:00:00.000Z")],
            [_obj("a.txt", stamp="2026-09-01T10:05:00.000Z")],
        ],
        max_events=1,
    )
    assert len(events) == 1
    assert events[0]["cos"]["key"] == "a.txt"
    assert events[0]["cos"]["event_type"] == "ObjectCreated"


def test_main_initial_emits_existing_objects(monkeypatch):
    events = _drive_main(
        monkeypatch,
        object(),
        {"region": "ap-guangzhou", "bucket": "b", "initial": True},
        poll_results=[[_obj("a.txt"), _obj("b.txt")]],
        max_events=2,
    )
    assert [e["cos"]["key"] for e in events] == ["a.txt", "b.txt"]


def test_main_skips_unchanged_objects(monkeypatch):
    events = _drive_main(
        monkeypatch,
        object(),
        {"region": "ap-guangzhou", "bucket": "b", "interval": 0.01},
        poll_results=[
            [_obj("a.txt")],
            [_obj("a.txt")],
        ],
        max_events=1,
    )
    assert events == []


def test_main_emits_error_event_on_poll_failure(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("bucket listing failed")

    monkeypatch.setattr(src, "_build_cos_client", lambda a: object())
    monkeypatch.setattr(src, "_resolve_appid", lambda a: "1300000000")
    monkeypatch.setattr(src, "list_bucket_objects", boom)

    async def drive():
        queue = asyncio.Queue()
        task = asyncio.create_task(
            src.main(queue, {"region": "ap-guangzhou", "bucket": "b"})
        )
        event = await asyncio.wait_for(queue.get(), 2.0)
        task.cancel()
        return event

    event = asyncio.run(drive())
    assert "error" in event["cos"]
    assert "bucket listing failed" in event["cos"]["error"]


def test_main_requires_bucket(monkeypatch):
    monkeypatch.setattr(src, "_build_cos_client", lambda a: object())
    with pytest.raises(RuntimeError, match="bucket"):
        asyncio.run(src.main(asyncio.Queue(), {"region": "ap-guangzhou"}))
