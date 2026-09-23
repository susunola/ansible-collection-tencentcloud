"""Unit tests for the gwlb_target_group_association write module.

Drives ``run_module()`` against an in-memory fake GWLB client whose
associate/disassociate operations mutate a load-balancer -> target-group
store so the describe state converges immediately.

Scenario matrix:

* present on an already-associated GWLB (idempotent no-op)
* absent on an already-disassociated GWLB (idempotent no-op)
* association when missing (happy path, check mode)
* disassociation of a bound GWLB (happy path, check mode)
* the GWLB-does-not-exist guard and the blanket SDK failure paths
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import gwlb_target_group_association as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)

BOUND = {"LoadBalancerId": "gwlb-aaaa", "TargetGroupId": "lbtg-bbbb"}
VALUE = {"LoadBalancerId": "gwlb-aaaa", "TargetGroupId": "lbtg-bbbb"}


def _association_args(**overrides):
    params = {"state": "present", "load_balancer_id": "gwlb-aaaa", "target_group_id": "lbtg-bbbb"}
    params.update(overrides)
    return module_args(**params)


class FakeGwlbClient(object):
    """In-memory GWLB client storing each LB's bound target-group id."""

    def __init__(self, bound=None):
        # bound: mapping of load-balancer-id -> target-group-id (or None).
        self.bound = dict(bound or {})
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeGatewayLoadBalancers(self, request):
        self._record("DescribeGatewayLoadBalancers", request)
        ids = list(getattr(request, "LoadBalancerIds", None) or [])
        values = []
        for lb_id in ids:
            if lb_id in self.bound:
                values.append(SimpleNamespace(TargetGroupId=self.bound[lb_id]))
        return SimpleNamespace(LoadBalancerSet=values)

    def AssociateTargetGroups(self, request):
        self._record("AssociateTargetGroups", request)
        for association in getattr(request, "Associations", None) or []:
            self.bound[association.LoadBalancerId] = association.TargetGroupId
        return SimpleNamespace(RequestId="req-fake")

    def DisassociateTargetGroups(self, request):
        self._record("DisassociateTargetGroups", request)
        for association in getattr(request, "Associations", None) or []:
            if self.bound.get(association.LoadBalancerId) == association.TargetGroupId:
                self.bound[association.LoadBalancerId] = None
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(GwlbClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# idempotent flows
# ---------------------------------------------------------------------------


def test_present_when_already_associated_is_idempotent(monkeypatch):
    fake = FakeGwlbClient(bound={BOUND["LoadBalancerId"]: BOUND["TargetGroupId"]})
    _make_module(monkeypatch, fake)
    _association_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["association"] == VALUE
    assert [c for c, unused in fake.calls] == ["DescribeGatewayLoadBalancers"]


def test_absent_when_not_associated_is_idempotent(monkeypatch):
    fake = FakeGwlbClient(bound={BOUND["LoadBalancerId"]: None})
    _make_module(monkeypatch, fake)
    _association_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["association"] is None
    assert [c for c, unused in fake.calls] == ["DescribeGatewayLoadBalancers"]


# ---------------------------------------------------------------------------
# state-change flows
# ---------------------------------------------------------------------------


def test_present_associates_when_missing(monkeypatch):
    fake = FakeGwlbClient(bound={BOUND["LoadBalancerId"]: None})
    _make_module(monkeypatch, fake)
    _association_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["association"] == VALUE
    assert fake.bound[BOUND["LoadBalancerId"]] == BOUND["TargetGroupId"]
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeGatewayLoadBalancers"
    assert "AssociateTargetGroups" in ops


def test_present_associate_check_mode_is_dry_run(monkeypatch):
    fake = FakeGwlbClient(bound={BOUND["LoadBalancerId"]: None})
    _make_module(monkeypatch, fake)
    _association_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["association"] == VALUE
    assert "diff" in result
    assert fake.bound[BOUND["LoadBalancerId"]] is None
    assert "AssociateTargetGroups" not in [c for c, unused in fake.calls]


def test_absent_disassociates_bound_gwlb(monkeypatch):
    fake = FakeGwlbClient(bound={BOUND["LoadBalancerId"]: BOUND["TargetGroupId"]})
    _make_module(monkeypatch, fake)
    _association_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["association"] is None
    assert fake.bound[BOUND["LoadBalancerId"]] is None
    ops = [c for c, unused in fake.calls]
    assert "DisassociateTargetGroups" in ops


def test_absent_disassociate_check_mode_is_dry_run(monkeypatch):
    fake = FakeGwlbClient(bound={BOUND["LoadBalancerId"]: BOUND["TargetGroupId"]})
    _make_module(monkeypatch, fake)
    _association_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["association"] is None
    assert fake.bound[BOUND["LoadBalancerId"]] == BOUND["TargetGroupId"]
    assert "DisassociateTargetGroups" not in [c for c, unused in fake.calls]


def test_present_switches_target_group(monkeypatch):
    # An LB bound to one target group is associated to another group; the
    # module sees a mismatch and issues a fresh AssociateTargetGroups call.
    fake = FakeGwlbClient(bound={"gwlb-aaaa": "lbtg-old"})
    _make_module(monkeypatch, fake)
    module_args(state="present", load_balancer_id="gwlb-aaaa", target_group_id="lbtg-bbbb")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.bound["gwlb-aaaa"] == "lbtg-bbbb"
    assert "AssociateTargetGroups" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# guards and failure paths
# ---------------------------------------------------------------------------


def test_missing_gwlb_fails(monkeypatch):
    fake = FakeGwlbClient(bound={})
    _make_module(monkeypatch, fake)
    _association_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "GWLB does not exist"
    assert payload["load_balancer_id"] == "gwlb-aaaa"


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeGatewayLoadBalancers(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _association_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


def test_associate_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeGatewayLoadBalancers(self, request):
            return SimpleNamespace(LoadBalancerSet=[SimpleNamespace(TargetGroupId=None)])

        def AssociateTargetGroups(self, request):
            raise Boom("associate refused")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _association_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "associate refused" in payload["error"]
