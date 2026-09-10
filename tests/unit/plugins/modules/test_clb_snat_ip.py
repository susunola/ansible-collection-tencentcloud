"""Unit tests for the clb_snat_ip write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake CLB client whose
SNAT IP operations mutate a per-load-balancer SNAT IP store, so the module's
post-write ``DescribeLoadBalancers`` refetch observes the new state immediately.

Scenario matrix:

* create when missing (real Create + converged refetch)
* idempotent no-op when all requested IPs already present
* partial add (only the missing IPs are created)
* absent when missing (no-op)
* delete when present (real Delete + converged refetch)
* check-mode dry run for create (no Create call)
* check-mode dry run for delete (no Delete call)
* CLB not found fails
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import clb_snat_ip as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _lb(lb_id, snat_ips):
    return FakeResource({"LoadBalancerId": lb_id, "SnatIps": list(snat_ips), "SnatPro": False})


class FakeClbClient(object):
    """In-memory CLB client mutating a SNAT IP store keyed by load balancer id."""

    def __init__(self, lb_id="lb-abc123", snat_ips=None):
        self.lb_id = lb_id
        self.snat_ips = list(snat_ips or [])
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeLoadBalancers(self, request):
        self._record("DescribeLoadBalancers", request)
        return SimpleNamespace(
            LoadBalancerSet=[_lb(self.lb_id, self.snat_ips)],
            TotalCount=1,
            RequestId="req-fake",
        )

    def CreateLoadBalancerSnatIps(self, request):
        self._record("CreateLoadBalancerSnatIps", request)
        for ip in list(getattr(request, "SnatIps", None) or []):
            if ip not in self.snat_ips:
                self.snat_ips.append(ip)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteLoadBalancerSnatIps(self, request):
        self._record("DeleteLoadBalancerSnatIps", request)
        remove = set(getattr(request, "Ips", None) or [])
        self.snat_ips = [ip for ip in self.snat_ips if ip not in remove]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_clb", lambda: (models or FakeModels(), SimpleNamespace(ClbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# create / delete flows
# ---------------------------------------------------------------------------


def test_create_when_missing(monkeypatch):
    fake = FakeClbClient(snat_ips=[])
    _make_module(monkeypatch, fake)
    module_args(load_balancer_id="lb-abc123", snat_ips=["10.0.0.10", "10.0.0.11"], state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["load_balancer_id"] == "lb-abc123"
    assert set(result["snat_ips"]) == {"10.0.0.10", "10.0.0.11"}
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeLoadBalancers"
    assert "CreateLoadBalancerSnatIps" in ops
    assert "DeleteLoadBalancerSnatIps" not in ops
    assert set(fake.snat_ips) == {"10.0.0.10", "10.0.0.11"}


def test_delete_when_present(monkeypatch):
    fake = FakeClbClient(snat_ips=["10.0.0.10", "10.0.0.11"])
    _make_module(monkeypatch, fake)
    module_args(load_balancer_id="lb-abc123", snat_ips=["10.0.0.10"], state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert set(result["snat_ips"]) == {"10.0.0.11"}
    ops = [c for c, unused in fake.calls]
    assert "DeleteLoadBalancerSnatIps" in ops
    assert "CreateLoadBalancerSnatIps" not in ops
    assert fake.snat_ips == ["10.0.0.11"]


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_already_present_is_idempotent(monkeypatch):
    fake = FakeClbClient(snat_ips=["10.0.0.10", "10.0.0.11"])
    _make_module(monkeypatch, fake)
    module_args(load_balancer_id="lb-abc123", snat_ips=["10.0.0.10", "10.0.0.11"], state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    ops = [c for c, unused in fake.calls]
    assert ops == ["DescribeLoadBalancers"]
    assert "CreateLoadBalancerSnatIps" not in ops


def test_absent_when_missing_is_idempotent(monkeypatch):
    fake = FakeClbClient(snat_ips=["10.0.0.10"])
    _make_module(monkeypatch, fake)
    module_args(load_balancer_id="lb-abc123", snat_ips=["10.0.0.99"], state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "DeleteLoadBalancerSnatIps" not in [c for c, unused in fake.calls]


def test_partial_add_only_creates_missing(monkeypatch):
    fake = FakeClbClient(snat_ips=["10.0.0.10"])
    _make_module(monkeypatch, fake)
    module_args(load_balancer_id="lb-abc123", snat_ips=["10.0.0.10", "10.0.0.11"], state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert set(result["snat_ips"]) == {"10.0.0.10", "10.0.0.11"}
    created = [r for c, r in fake.calls if c == "CreateLoadBalancerSnatIps"]
    assert created and set(created[0].SnatIps) == {"10.0.0.11"}


# ---------------------------------------------------------------------------
# check-mode dry runs
# ---------------------------------------------------------------------------


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeClbClient(snat_ips=[])
    _make_module(monkeypatch, fake)
    module_args(load_balancer_id="lb-abc123", snat_ips=["10.0.0.10"], state="present", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "CreateLoadBalancerSnatIps" not in [c for c, unused in fake.calls]
    assert fake.snat_ips == []


def test_delete_check_mode_is_dry_run(monkeypatch):
    fake = FakeClbClient(snat_ips=["10.0.0.10"])
    _make_module(monkeypatch, fake)
    module_args(load_balancer_id="lb-abc123", snat_ips=["10.0.0.10"], state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "DeleteLoadBalancerSnatIps" not in [c for c, unused in fake.calls]
    assert fake.snat_ips == ["10.0.0.10"]


# ---------------------------------------------------------------------------
# error path
# ---------------------------------------------------------------------------


def test_clb_not_found_fails(monkeypatch):
    fake = FakeClbClient(snat_ips=[])
    fake.DescribeLoadBalancers = lambda request: SimpleNamespace(LoadBalancerSet=[], TotalCount=0, RequestId="req-fake")
    _make_module(monkeypatch, fake)
    module_args(load_balancer_id="lb-missing", snat_ips=["10.0.0.10"], state="present")
    try:
        run(mod.run_module)
    except SystemExit as exc:
        assert getattr(exc, "failed", False) or exc.args[0].get("failed")
        assert "not found" in exc.args[0]["msg"]
    else:
        raise AssertionError("expected module to fail")
