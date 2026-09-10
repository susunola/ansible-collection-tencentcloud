"""Unit tests for the tdcpg_endpoint_wan write module (run_module flows).

``run_module()`` opens or closes public access on a TDSQL-C PostgreSQL
endpoint and waits for the endpoint metadata to converge. It is driven end
to end against an in-memory fake client whose ``ModifyClusterEndpointWanStatus``
operation mutates the endpoint store, so the post-write ``DescribeClusterEndpoints``
refetch converges immediately.

Scenario matrix:

* open when already open / closed when already closed (idempotent no-ops)
* opening a closed endpoint and closing an open one (check mode and real)
* argument validation (invalid state choice) before any SDK call
* endpoint-not-found and blanket ``sdk_error_payload`` failure paths
* waiter timeout when the status change never converges
* legacy helper regression tests (folded from test_tdcpg_endpoint_wan.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdcpg_endpoint_wan as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CLUSTER_ID = "tdcpg-cluster-abc"
ENDPOINT_ID = "tdcpg-ep-abc"


def _base(**overrides):
    params = {"cluster_id": CLUSTER_ID, "endpoint_id": ENDPOINT_ID, "state": "closed"}
    params.update(overrides)
    return module_args(**params)


def _closed_endpoint():
    return {"EndpointId": ENDPOINT_ID, "WanIp": None, "WanDomain": None}


def _open_endpoint():
    return {"EndpointId": ENDPOINT_ID, "WanIp": "1.2.3.4", "WanDomain": "ep-abc.tencentcdb.com"}


class FakeTdcpgWanClient(object):
    """In-memory TDSQL-C client holding one endpoint's WAN metadata."""

    def __init__(self, endpoint=None, stubborn=False):
        self.endpoint = copy.deepcopy(endpoint) if endpoint is not None else None
        self.stubborn = stubborn
        self.calls = []
        self.last_request = None

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeClusterEndpoints(self, request):
        self._record("DescribeClusterEndpoints", request)
        assert request.ClusterId == CLUSTER_ID
        endpoint_set = [FakeResource(self.endpoint)] if self.endpoint is not None else []
        return SimpleNamespace(EndpointSet=endpoint_set, RequestId="req-fake")

    def ModifyClusterEndpointWanStatus(self, request):
        self._record("ModifyClusterEndpointWanStatus", request)
        self.last_request = request
        if not self.stubborn and self.endpoint is not None:
            if request.WanStatus == "OPEN":
                self.endpoint["WanIp"] = "1.2.3.4"
                self.endpoint["WanDomain"] = "ep-abc.tencentcdb.com"
            else:
                self.endpoint["WanIp"] = None
                self.endpoint["WanDomain"] = None
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TdcpgClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_open_when_already_open_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeTdcpgWanClient(endpoint=_open_endpoint()))
    _base(state="open")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["endpoint"]["WanIp"] == "1.2.3.4"
    assert _names(fake) == ["DescribeClusterEndpoints"]


def test_closed_when_already_closed_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeTdcpgWanClient(endpoint=_closed_endpoint()))
    _base(state="closed")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["endpoint"]["WanIp"] is None
    assert _names(fake) == ["DescribeClusterEndpoints"]


# ---------------------------------------------------------------------------
# open flows
# ---------------------------------------------------------------------------


def test_open_opens_closed_endpoint(monkeypatch):
    fake = _make_module(monkeypatch, FakeTdcpgWanClient(endpoint=_closed_endpoint()))
    _base(state="open")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["endpoint"]["WanIp"] == "1.2.3.4"
    assert fake.endpoint["WanIp"] == "1.2.3.4"
    assert fake.last_request.WanStatus == "OPEN"
    assert fake.last_request.EndpointId == ENDPOINT_ID
    assert _names(fake) == ["DescribeClusterEndpoints", "ModifyClusterEndpointWanStatus", "DescribeClusterEndpoints"]


def test_open_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeTdcpgWanClient(endpoint=_closed_endpoint()))
    _base(state="open", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["endpoint"] == {"EndpointId": ENDPOINT_ID, "Open": True}
    assert "diff" in result
    assert fake.endpoint["WanIp"] is None
    assert _names(fake) == ["DescribeClusterEndpoints"]


# ---------------------------------------------------------------------------
# closed flows
# ---------------------------------------------------------------------------


def test_closed_closes_open_endpoint(monkeypatch):
    fake = _make_module(monkeypatch, FakeTdcpgWanClient(endpoint=_open_endpoint()))
    _base(state="closed")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["endpoint"]["WanIp"] is None
    assert fake.endpoint["WanIp"] is None
    assert fake.last_request.WanStatus == "CLOSE"
    assert _names(fake) == ["DescribeClusterEndpoints", "ModifyClusterEndpointWanStatus", "DescribeClusterEndpoints"]


def test_closed_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeTdcpgWanClient(endpoint=_open_endpoint()))
    _base(state="closed", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["endpoint"] == {"EndpointId": ENDPOINT_ID, "Open": False}
    assert fake.endpoint["WanIp"] == "1.2.3.4"
    assert "ModifyClusterEndpointWanStatus" not in _names(fake)


# ---------------------------------------------------------------------------
# argument validation and failure paths
# ---------------------------------------------------------------------------


def test_invalid_state_choice_fails_before_sdk(monkeypatch):
    fake = _make_module(monkeypatch, FakeTdcpgWanClient(endpoint=_open_endpoint()))
    _base(state="half-open")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "half-open" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_missing_endpoint_fails(monkeypatch):
    fake = _make_module(monkeypatch, FakeTdcpgWanClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "endpoint was not found" in payload["msg"]
    assert payload["endpoint_id"] == ENDPOINT_ID
    assert _names(fake) == ["DescribeClusterEndpoints"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeClusterEndpoints(self, request):
            raise Boom("tdcpg endpoint unreachable")

    _make_module(monkeypatch, ExplodingClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "tdcpg endpoint unreachable" in payload["error"]


def test_waiter_times_out_when_status_does_not_change(monkeypatch):
    _make_module(monkeypatch, FakeTdcpgWanClient(endpoint=_closed_endpoint(), stubborn=True))
    _base(state="open", waiter_timeout=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Timed out waiting for endpoint public access convergence" in payload["msg"]
    assert payload["expected_open"] is True
    assert payload["endpoint"]["WanIp"] is None


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tdcpg_endpoint_wan.py)
# ---------------------------------------------------------------------------


def test_update_request_maps_state_to_wan_status():
    request = mod.update_request(FakeModels(), {"cluster_id": "c1", "endpoint_id": "e1", "state": "closed"})
    assert request.ClusterId == "c1"
    assert request.EndpointId == "e1"
    assert request.WanStatus == "CLOSE"
    request = mod.update_request(FakeModels(), {"cluster_id": "c1", "endpoint_id": "e1", "state": "open"})
    assert request.WanStatus == "OPEN"


def test_is_open_reads_wan_identity_fields():
    assert mod.is_open({"WanDomain": "db.example.com"})
    assert mod.is_open({"WanIp": "1.2.3.4", "WanDomain": None})
    assert not mod.is_open({"WanIp": None, "WanDomain": None})
