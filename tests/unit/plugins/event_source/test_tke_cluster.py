"""Unit tests for the tke_cluster event source helpers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import asyncio
import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.event_source import (
    tke_cluster as src,
)


class FakeRequest(object):
    pass


class FakeModels(object):
    DescribeClusterStatusRequest = FakeRequest


class FakeStatus(object):
    def __init__(self, cluster_id, state="Running", instance_state="Running", nodes=3):
        self.ClusterId = cluster_id
        self.ClusterState = state
        self.ClusterInstanceState = instance_state
        self.ClusterRunningNodeNum = nodes
        self.ClusterFailedNodeNum = 0
        self.ClusterClosedNodeNum = 0
        self.ClusterInitNodeNum = 0


class FakeStatusResponse(object):
    def __init__(self, statuses):
        self.ClusterStatusSet = statuses


class FakeStatusClient(object):
    def __init__(self, response):
        self.response = response
        self.request = None

    def DescribeClusterStatus(self, request):
        self.request = request
        return self.response


# ---------------------------------------------------------------------------
# request building / status parsing
# ---------------------------------------------------------------------------


def test_build_status_request_without_ids():
    request = src.build_status_request(FakeModels, None)
    assert not hasattr(request, "ClusterIds")


def test_build_status_request_with_ids():
    request = src.build_status_request(FakeModels, ["cls-1", "cls-2"])
    assert request.ClusterIds == ["cls-1", "cls-2"]


def test_describe_cluster_status_parses_entries():
    client = FakeStatusClient(
        FakeStatusResponse([
            FakeStatus("cls-1", state="Running", nodes=3),
            FakeStatus("cls-2", state="Abnormal", instance_state="Running", nodes=1),
        ])
    )
    clusters = src.describe_cluster_status(client, FakeModels, ["cls-1", "cls-2"])
    assert clusters[0] == {
        "cluster_id": "cls-1",
        "cluster_state": "Running",
        "cluster_instance_state": "Running",
        "running_node_num": 3,
        "failed_node_num": 0,
        "closed_node_num": 0,
        "init_node_num": 0,
    }
    assert clusters[1]["cluster_state"] == "Abnormal"
    assert client.request.ClusterIds == ["cls-1", "cls-2"]


def test_describe_cluster_status_empty():
    client = FakeStatusClient(FakeStatusResponse([]))
    assert src.describe_cluster_status(client, FakeModels, None) == []


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

    tke_client = types.ModuleType("tencentcloud.tke.v20180525.tke_client")
    tke_client.TkeClient = lambda *a, **k: object()

    models = types.ModuleType("tencentcloud.tke.v20180525.models")

    v20180525 = types.ModuleType("tencentcloud.tke.v20180525")
    v20180525.tke_client = tke_client
    v20180525.models = models

    profile_pkg = types.ModuleType("tencentcloud.common.profile")
    profile_pkg.http_profile = http_profile
    profile_pkg.client_profile = client_profile

    common = types.ModuleType("tencentcloud.common")
    common.credential = credential
    common.profile = profile_pkg

    tke_pkg = types.ModuleType("tencentcloud.tke")
    tke_pkg.v20180525 = v20180525

    tencentcloud = types.ModuleType("tencentcloud")
    tencentcloud.common = common
    tencentcloud.tke = tke_pkg

    for name, module in {
        "tencentcloud": tencentcloud,
        "tencentcloud.common": common,
        "tencentcloud.common.credential": credential,
        "tencentcloud.common.profile": profile_pkg,
        "tencentcloud.common.profile.http_profile": http_profile,
        "tencentcloud.common.profile.client_profile": client_profile,
        "tencentcloud.tke": tke_pkg,
        "tencentcloud.tke.v20180525": v20180525,
        "tencentcloud.tke.v20180525.tke_client": tke_client,
        "tencentcloud.tke.v20180525.models": models,
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


def _drive_main(monkeypatch, client, args, poll_results, max_events=1):
    """Run main() for a fixed sequence of poll results, collecting events.

    After the scripted results are exhausted the last result is returned on
    every further poll, so the loop settles into a no-change steady state
    instead of looking like a deletion or emitting spurious events.
    """
    monkeypatch.setattr(src, "_build_client", lambda a: (client, FakeModels))
    results = list(poll_results)
    steady = poll_results[-1]

    def fake_status(client_, models, cluster_ids):
        return results.pop(0) if results else steady

    monkeypatch.setattr(src, "describe_cluster_status", fake_status)

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


def _cluster(cluster_id, state="Running", instance_state="Running", nodes=3):
    return {
        "cluster_id": cluster_id,
        "cluster_state": state,
        "cluster_instance_state": instance_state,
        "running_node_num": nodes,
        "failed_node_num": 0,
        "closed_node_num": 0,
        "init_node_num": 0,
    }


def test_main_baseline_then_emits_state_change(monkeypatch):
    events = _drive_main(
        monkeypatch,
        object(),
        {"region": "ap-guangzhou", "interval": 0.01},
        poll_results=[
            [_cluster("cls-1", state="Running")],
            [_cluster("cls-1", state="Abnormal")],
        ],
        max_events=1,
    )
    assert len(events) == 1
    event = events[0]["tke"]
    assert event["cluster_id"] == "cls-1"
    assert event["cluster_state"] == "Abnormal"
    assert event["previous_state"] == "Running"
    assert event["event_type"] == "ClusterStateChanged"
    assert events[0]["region"] == "ap-guangzhou"


def test_main_emits_when_new_cluster_appears(monkeypatch):
    events = _drive_main(
        monkeypatch,
        object(),
        {"region": "ap-guangzhou", "interval": 0.01},
        poll_results=[
            [_cluster("cls-1")],
            [_cluster("cls-1"), _cluster("cls-2")],
        ],
        max_events=1,
    )
    assert len(events) == 1
    assert events[0]["tke"]["cluster_id"] == "cls-2"
    assert events[0]["tke"]["previous_state"] is None


def test_main_initial_emits_current_state(monkeypatch):
    events = _drive_main(
        monkeypatch,
        object(),
        {"region": "ap-guangzhou", "initial": True},
        poll_results=[[_cluster("cls-1"), _cluster("cls-2")]],
        max_events=2,
    )
    assert [e["tke"]["cluster_id"] for e in events] == ["cls-1", "cls-2"]
    assert all(e["tke"]["event_type"] == "ClusterStateChanged" for e in events)


def test_main_skips_unchanged_state(monkeypatch):
    events = _drive_main(
        monkeypatch,
        object(),
        {"region": "ap-guangzhou", "interval": 0.01},
        poll_results=[
            [_cluster("cls-1")],
            [_cluster("cls-1")],
        ],
        max_events=1,
    )
    assert events == []


def test_main_emits_cluster_deleted(monkeypatch):
    events = _drive_main(
        monkeypatch,
        object(),
        {"region": "ap-guangzhou", "interval": 0.01},
        poll_results=[
            [_cluster("cls-1"), _cluster("cls-2")],
            [_cluster("cls-1")],
        ],
        max_events=1,
    )
    assert len(events) == 1
    assert events[0]["tke"]["cluster_id"] == "cls-2"
    assert events[0]["tke"]["event_type"] == "ClusterDeleted"
    assert events[0]["tke"]["region"] == "ap-guangzhou"


def test_main_emits_error_event_on_api_failure(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("DescribeClusterStatus failed")

    monkeypatch.setattr(src, "_build_client", lambda a: (object(), FakeModels))
    monkeypatch.setattr(src, "describe_cluster_status", boom)

    async def drive():
        queue = asyncio.Queue()
        task = asyncio.create_task(src.main(queue, {"region": "ap-guangzhou"}))
        event = await asyncio.wait_for(queue.get(), 2.0)
        task.cancel()
        return event

    event = asyncio.run(drive())
    assert "error" in event["tke"]
    assert "DescribeClusterStatus failed" in event["tke"]["error"]
