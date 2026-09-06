"""Unit tests for the gwlb_load_balancer write module (helpers + run_module).

Creates, updates and deletes Gateway Load Balancer instances. Lookup
lists all GWLBs and filters by ``load_balancer_id`` or, when no id is
given, by ``name``; multiple name matches fail and ask for an id.
``VpcId`` and ``SubnetId`` are immutable after creation
(require_immutable_unchanged), while ``LoadBalancerName`` and
``DeleteProtect`` are the only updatable fields — ``update_request``
carries exactly those two. Deleting an instance whose protection is
enabled requires ``deletion_protection: false``; the real delete then
issues a protection-disable Modify before the Delete.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import gwlb_load_balancer as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _item(**overrides):
    """API-shaped GWLB dict; fresh copy per call."""
    item = {
        "LoadBalancerId": "lb-1",
        "LoadBalancerName": "glb-a",
        "VpcId": "vpc-1",
        "SubnetId": "subnet-1",
        "DeleteProtect": False,
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "load_balancer_id": None,
        "name": None,
        "vpc_id": None,
        "subnet_id": None,
        "charge_type": "POSTPAID_BY_HOUR",
        "deletion_protection": None,
        "tags": None,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    return module_args(**{k: v for k, v in _params(**extra).items() if v is not None})


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


class FakeGwlbClient(object):
    """In-memory GwlbClient stand-in storing GWLB dicts.

    DescribeGatewayLoadBalancers returns every stored item as
    :class:`FakeResource` (the module applies its own identity filter).
    CreateGatewayLoadBalancer synthesises a LoadBalancerId; the API does
    not set deletion protection at creation, so new items start with
    DeleteProtect False. Modify updates name/protection only; Delete
    removes by LoadBalancerIds.
    """

    def __init__(self, items=None):
        self.items = [dict(i) for i in (items or [])]
        self.calls = []
        self._next_id = 100

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeGatewayLoadBalancers(self, request):
        self._record("DescribeGatewayLoadBalancers", request)
        return SimpleNamespace(
            LoadBalancerSet=[FakeResource(dict(i)) for i in self.items],
            RequestId="req-fake",
        )

    def CreateGatewayLoadBalancer(self, request):
        self._record("CreateGatewayLoadBalancer", request)
        load_balancer_id = "lb-new%d" % self._next_id
        self._next_id += 1
        self.items.append(
            {
                "LoadBalancerId": load_balancer_id,
                "LoadBalancerName": request.LoadBalancerName,
                "VpcId": request.VpcId,
                "SubnetId": request.SubnetId,
                "DeleteProtect": False,
                "LBChargeType": request.LBChargeType,
                "Tags": [{"TagKey": t.TagKey, "TagValue": t.TagValue} for t in request.Tags],
            }
        )
        return SimpleNamespace(LoadBalancerIds=[load_balancer_id], RequestId="req-fake")

    def ModifyGatewayLoadBalancerAttribute(self, request):
        self._record("ModifyGatewayLoadBalancerAttribute", request)
        for stored in self.items:
            if stored.get("LoadBalancerId") == request.LoadBalancerId:
                stored["LoadBalancerName"] = request.LoadBalancerName
                stored["DeleteProtect"] = request.DeleteProtect
        return SimpleNamespace(RequestId="req-fake")

    def DeleteGatewayLoadBalancer(self, request):
        self._record("DeleteGatewayLoadBalancer", request)
        self.items = [i for i in self.items if i.get("LoadBalancerId") not in request.LoadBalancerIds]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(GwlbClient=object)),
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
# request-builder / helper tests
# ---------------------------------------------------------------------------


def test_describe_request_without_id_has_no_filter():
    request = mod.describe_request(FakeModels(), _params())
    assert request.Offset == 0
    assert request.Limit == 100
    assert not hasattr(request, "LoadBalancerIds")


def test_describe_request_with_id_filters():
    request = mod.describe_request(FakeModels(), _params(load_balancer_id="lb-9"))
    assert request.LoadBalancerIds == ["lb-9"]


def test_tags_empty_returns_empty_list():
    assert mod._tags(FakeModels(), None) == []
    assert mod._tags(FakeModels(), {}) == []


def test_tags_sorted_builds_tag_models():
    tags = mod._tags(FakeModels(), {"z": "last", "a": "first", "m": "middle"})
    assert [t.TagKey for t in tags] == ["a", "m", "z"]
    assert [t.TagValue for t in tags] == ["first", "middle", "last"]


def test_create_request_maps_fields():
    request = mod.create_request(
        FakeModels(),
        _params(name="glb-b", vpc_id="vpc-2", subnet_id="subnet-2", charge_type="POSTPAID_BY_HOUR", tags={"b": "2", "a": "1"}),
    )
    assert request.VpcId == "vpc-2"
    assert request.SubnetId == "subnet-2"
    assert request.LoadBalancerName == "glb-b"
    assert request.Number == 1
    assert request.LBChargeType == "POSTPAID_BY_HOUR"
    assert [(t.TagKey, t.TagValue) for t in request.Tags] == [("a", "1"), ("b", "2")]


def test_create_request_without_tags_builds_empty_tag_list():
    request = mod.create_request(FakeModels(), _params(name="glb-b", vpc_id="vpc-2", subnet_id="subnet-2"))
    assert request.Tags == []


def test_update_request_carries_name_and_protection_only():
    request = mod.update_request(FakeModels(), "lb-9", "renamed", True)
    assert request.LoadBalancerId == "lb-9"
    assert request.LoadBalancerName == "renamed"
    assert request.DeleteProtect is True
    assert not hasattr(request, "VpcId")
    assert not hasattr(request, "SubnetId")
    assert not hasattr(request, "Tags")


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), "lb-9")
    assert request.LoadBalancerIds == ["lb-9"]


def test_comparable_normalises_protection_to_bool():
    value = mod.comparable({"LoadBalancerName": "glb-a", "VpcId": "vpc-1", "SubnetId": "subnet-1", "DeleteProtect": 1})
    assert value == {"LoadBalancerName": "glb-a", "VpcId": "vpc-1", "SubnetId": "subnet-1", "DeleteProtect": True}


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_matches_by_id(monkeypatch):
    fake = FakeGwlbClient([_item(LoadBalancerId="lb-1"), _item(LoadBalancerId="lb-2", LoadBalancerName="glb-b")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(load_balancer_id="lb-2"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["LoadBalancerId"] == "lb-2"
    assert value["LoadBalancerName"] == "glb-b"


def test_find_matches_by_name(monkeypatch):
    fake = FakeGwlbClient([_item(), _item(LoadBalancerId="lb-2", LoadBalancerName="glb-b")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="glb-b"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["LoadBalancerId"] == "lb-2"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeGwlbClient([_item()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(load_balancer_id="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_multiple_name_matches_fails(monkeypatch):
    fake = FakeGwlbClient([_item(), _item(LoadBalancerId="lb-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="glb-a"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    assert "Multiple GWLB instances matched; specify load_balancer_id" in exc.value.args[0]["msg"]


def test_find_id_filter_ignores_name_lookalikes(monkeypatch):
    fake = FakeGwlbClient([_item(), _item(LoadBalancerId="lb-2", LoadBalancerName="glb-a")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(load_balancer_id="lb-2"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["LoadBalancerId"] == "lb-2"  # no multi-match even though two share the name


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_requires_load_balancer_id_or_name():
    module_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    msg = exc.value.args[0]["msg"]
    assert "load_balancer_id" in msg and "name" in msg


def test_present_creates_load_balancer(monkeypatch):
    fake = FakeGwlbClient()
    _make_module(monkeypatch, fake)
    _run_args(name="glb-new", vpc_id="vpc-2", subnet_id="subnet-2")
    result = run(mod.run_module)
    assert result["changed"] is True
    lb = result["load_balancer"]
    assert lb["LoadBalancerId"] == "lb-new100"
    assert lb["LoadBalancerName"] == "glb-new"
    assert lb["VpcId"] == "vpc-2"
    assert lb["SubnetId"] == "subnet-2"
    assert [c[0] for c in fake.calls].count("DescribeGatewayLoadBalancers") == 2  # find + refetch
    create = [c for c in fake.calls if c[0] == "CreateGatewayLoadBalancer"][0][1]
    assert create.Number == 1
    assert create.LBChargeType == "POSTPAID_BY_HOUR"
    assert len(fake.items) == 1


def test_present_creation_parameters_missing_fails(monkeypatch):
    fake = FakeGwlbClient()
    _make_module(monkeypatch, fake)
    _run_args(load_balancer_id="ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required for a new GWLB" in payload["msg"]
    assert sorted(payload["missing"]) == ["name", "subnet_id", "vpc_id"]


def test_present_name_only_still_needs_vpc_and_subnet(monkeypatch):
    fake = FakeGwlbClient()
    _make_module(monkeypatch, fake)
    _run_args(name="glb-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert sorted(payload["missing"]) == ["subnet_id", "vpc_id"]


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeGwlbClient()
    _make_module(monkeypatch, fake)
    module_args(
        _ansible_check_mode=True,
        **{k: v for k, v in _params(name="glb-new", vpc_id="vpc-2", subnet_id="subnet-2", deletion_protection=True).items() if v is not None}
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["load_balancer"] == {
        "LoadBalancerName": "glb-new",
        "VpcId": "vpc-2",
        "SubnetId": "subnet-2",
        "DeleteProtect": True,
    }
    assert not any(c[0] == "CreateGatewayLoadBalancer" for c in fake.calls)
    assert fake.items == []


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeGwlbClient([_item()])
    _make_module(monkeypatch, fake)
    _run_args(name="glb-a", vpc_id="vpc-1", subnet_id="subnet-1", deletion_protection=False)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["load_balancer"]["LoadBalancerId"] == "lb-1"
    assert not any(c[0] == "ModifyGatewayLoadBalancerAttribute" for c in fake.calls)


def test_present_name_drift_triggers_update(monkeypatch):
    fake = FakeGwlbClient([_item()])
    _make_module(monkeypatch, fake)
    _run_args(load_balancer_id="lb-1", name="renamed")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["load_balancer"]["LoadBalancerName"] == "renamed"
    update = [c for c in fake.calls if c[0] == "ModifyGatewayLoadBalancerAttribute"][0][1]
    assert update.LoadBalancerId == "lb-1"
    assert update.LoadBalancerName == "renamed"
    assert update.DeleteProtect is False  # unchanged protection still sent
    assert [c[0] for c in fake.calls].count("DescribeGatewayLoadBalancers") == 2


def test_present_protection_drift_triggers_update(monkeypatch):
    fake = FakeGwlbClient([_item()])
    _make_module(monkeypatch, fake)
    _run_args(name="glb-a", deletion_protection=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["load_balancer"]["DeleteProtect"] is True
    update = [c for c in fake.calls if c[0] == "ModifyGatewayLoadBalancerAttribute"][0][1]
    assert update.DeleteProtect is True
    assert update.LoadBalancerName == "glb-a"


def test_present_protection_disable_flows_through(monkeypatch):
    fake = FakeGwlbClient([_item(DeleteProtect=True)])
    _make_module(monkeypatch, fake)
    _run_args(name="glb-a", deletion_protection=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["load_balancer"]["DeleteProtect"] is False


def test_present_vpc_id_immutable_fails(monkeypatch):
    fake = FakeGwlbClient([_item()])
    _make_module(monkeypatch, fake)
    _run_args(name="glb-a", vpc_id="vpc-other")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["replacement_required"] is True
    assert payload["immutable_changes"] == {"VpcId": {"before": "vpc-1", "after": "vpc-other"}}
    assert not any(c[0] == "ModifyGatewayLoadBalancerAttribute" for c in fake.calls)


def test_present_subnet_id_immutable_fails(monkeypatch):
    fake = FakeGwlbClient([_item()])
    _make_module(monkeypatch, fake)
    _run_args(name="glb-a", subnet_id="subnet-other")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["immutable_changes"] == {"SubnetId": {"before": "subnet-1", "after": "subnet-other"}}


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeGwlbClient([_item()])
    _make_module(monkeypatch, fake)
    module_args(
        _ansible_check_mode=True,
        **{k: v for k, v in _params(load_balancer_id="lb-1", name="renamed").items() if v is not None}
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["load_balancer"]["LoadBalancerName"] == "glb-a"  # pre-change reported
    assert not any(c[0] == "ModifyGatewayLoadBalancerAttribute" for c in fake.calls)


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeGwlbClient([_item()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", load_balancer_id="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["load_balancer"] is None
    assert not any(c[0] == "DeleteGatewayLoadBalancer" for c in fake.calls)


def test_absent_delete_requires_protection_disabled(monkeypatch):
    fake = FakeGwlbClient([_item(DeleteProtect=True)])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", load_balancer_id="lb-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "set deletion_protection=false to authorize disabling protection before deletion" in payload["msg"]
    assert not any(c[0] == "DeleteGatewayLoadBalancer" for c in fake.calls)


def test_absent_deletes_unprotected(monkeypatch):
    fake = FakeGwlbClient([_item(), _item(LoadBalancerId="lb-2", LoadBalancerName="glb-b")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", load_balancer_id="lb-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["load_balancer"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteGatewayLoadBalancer"][0][1]
    assert delete.LoadBalancerIds == ["lb-1"]
    assert [i["LoadBalancerId"] for i in fake.items] == ["lb-2"]


def test_absent_disables_protection_before_delete(monkeypatch):
    fake = FakeGwlbClient([_item(DeleteProtect=True)])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", load_balancer_id="lb-1", deletion_protection=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["load_balancer"] is None
    assert [c[0] for c in fake.calls] == [
        "DescribeGatewayLoadBalancers",
        "ModifyGatewayLoadBalancerAttribute",
        "DeleteGatewayLoadBalancer",
    ]
    disable = fake.calls[1][1]
    assert disable.DeleteProtect is False
    assert disable.LoadBalancerName == "glb-a"
    assert fake.items == []


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeGwlbClient([_item()])
    _make_module(monkeypatch, fake)
    module_args(
        _ansible_check_mode=True,
        **{k: v for k, v in _params(state="absent", load_balancer_id="lb-1").items() if v is not None}
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["load_balancer"] is None
    assert not any(c[0] == "DeleteGatewayLoadBalancer" for c in fake.calls)
    assert len(fake.items) == 1


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(GwlbClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args(name="glb-new", vpc_id="vpc-2", subnet_id="subnet-2")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"
