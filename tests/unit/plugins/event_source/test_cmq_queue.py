"""Unit tests for the cmq_queue event source helpers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import asyncio
import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.event_source import (
    cmq_queue as src,
)


class FakeRequest(object):
    pass


class FakeModels(object):
    ReceiveMessageRequest = FakeRequest
    DeleteMessageRequest = FakeRequest


class FakeReceiveResponse(object):
    def __init__(self, msg_body=None, msg_id="m-1", receipt="r-1", dequeue_count=1):
        self.MsgBody = msg_body
        self.MsgId = msg_id
        self.ReceiptHandle = receipt
        self.DequeueCount = dequeue_count


class FakeDeleteResponse(object):
    pass


class FakeClient(object):
    def __init__(self):
        self.received = []
        self.deleted = []

    def ReceiveMessage(self, request):
        self.received.append(request)
        return FakeReceiveResponse()

    def DeleteMessage(self, request):
        self.deleted.append(request)
        return FakeDeleteResponse()


# ---------------------------------------------------------------------------
# request building
# ---------------------------------------------------------------------------


def test_receive_message_fields():
    client = FakeClient()
    src.receive_message(client, FakeModels, "orders", 20)
    assert client.received[0].QueueName == "orders"
    assert client.received[0].PollingWaitSeconds == 20


def test_delete_message_fields():
    client = FakeClient()
    src.delete_message(client, FakeModels, "orders", "r-42")
    assert client.deleted[0].QueueName == "orders"
    assert client.deleted[0].ReceiptHandle == "r-42"


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

    cmq_client = types.ModuleType("tencentcloud.cmq.v20190304.cmq_client")
    cmq_client.CmqClient = lambda *a, **k: object()

    models = types.ModuleType("tencentcloud.cmq.v20190304.models")

    v20190304 = types.ModuleType("tencentcloud.cmq.v20190304")
    v20190304.cmq_client = cmq_client
    v20190304.models = models

    profile_pkg = types.ModuleType("tencentcloud.common.profile")
    profile_pkg.http_profile = http_profile
    profile_pkg.client_profile = client_profile

    common = types.ModuleType("tencentcloud.common")
    common.credential = credential
    common.profile = profile_pkg

    cmq_pkg = types.ModuleType("tencentcloud.cmq")
    cmq_pkg.v20190304 = v20190304

    tencentcloud = types.ModuleType("tencentcloud")
    tencentcloud.common = common
    tencentcloud.cmq = cmq_pkg

    for name, module in {
        "tencentcloud": tencentcloud,
        "tencentcloud.common": common,
        "tencentcloud.common.credential": credential,
        "tencentcloud.common.profile": profile_pkg,
        "tencentcloud.common.profile.http_profile": http_profile,
        "tencentcloud.common.profile.client_profile": client_profile,
        "tencentcloud.cmq": cmq_pkg,
        "tencentcloud.cmq.v20190304": v20190304,
        "tencentcloud.cmq.v20190304.cmq_client": cmq_client,
        "tencentcloud.cmq.v20190304.models": models,
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


def _drive_main(monkeypatch, client, args):
    """Run main() until the first event, then cancel; return the event."""
    monkeypatch.setattr(src, "_build_client", lambda a: (client, FakeModels))

    async def run():
        queue = asyncio.Queue()
        task = asyncio.create_task(src.main(queue, args))
        event = await asyncio.wait_for(queue.get(), 2.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return event

    return asyncio.run(run())


class RespondingClient(FakeClient):
    """ReceiveMessage returns one real message, then raises StopIteration to
    let the loop terminate the run through the error path."""

    def __init__(self, response):
        super(RespondingClient, self).__init__()
        self.response = response
        self.calls = 0

    def ReceiveMessage(self, request):
        self.calls += 1
        if self.calls == 1:
            return self.response
        raise RuntimeError("queue empty")


def test_main_yields_message_and_acknowledges(monkeypatch):
    client = RespondingClient(
        FakeReceiveResponse(msg_body='{"order": 1}', receipt="r-1")
    )
    event = _drive_main(
        monkeypatch,
        client,
        {"region": "ap-guangzhou", "queue_name": "orders", "acknowledge": True},
    )
    assert event["cmq"]["msg_body"] == '{"order": 1}'
    assert event["cmq"]["msg_body_json"] == {"order": 1}
    assert event["cmq"]["queue_name"] == "orders"
    assert event["cmq"]["region"] == "ap-guangzhou"
    # the message was deleted after being yielded
    assert len(client.deleted) == 1
    assert client.deleted[0].ReceiptHandle == "r-1"


def test_main_keeps_message_when_acknowledge_false(monkeypatch):
    client = RespondingClient(
        FakeReceiveResponse(msg_body="plain text", receipt="r-2")
    )
    event = _drive_main(
        monkeypatch,
        client,
        {"region": "ap-guangzhou", "queue_name": "orders", "acknowledge": False},
    )
    assert event["cmq"]["msg_body"] == "plain text"
    assert "msg_body_json" not in event["cmq"]
    assert client.deleted == []


def test_main_emits_error_event_when_poll_fails(monkeypatch):
    class BoomClient(FakeClient):
        def ReceiveMessage(self, request):
            raise RuntimeError("throttled")

    event = _drive_main(
        monkeypatch,
        BoomClient(),
        {"region": "ap-guangzhou", "queue_name": "orders"},
    )
    assert "error" in event["cmq"]
    assert "throttled" in event["cmq"]["error"]
