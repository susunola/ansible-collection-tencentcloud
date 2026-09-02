"""Unit tests for the alb_load_balancer write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/alb_load_balancer.py`` with an in-memory fake ALB client
whose write operations mutate the load-balancer store, so the module's
post-write ``find`` refetch converges immediately. ALBs are matched by
``load_balancer_id`` or by ``name``; the detail lookup (nested
``LoadBalancerDetail``), address-type conversion, deletion-protection gating
(enable on create/update, mandatory disable before delete), the immutable
(VpcId, AddressIpVersion) guard and check-mode dry runs are exercised.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import alb_load_balancer as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ALB = {
    "LoadBalancerId": "alb-8b0a1c2d",
    "LoadBalancerName": "public-app",
    "AddressType": "Internet",
    "VpcId": "vpc-8b0a1c2d",
    "AddressIpVersion": "IPv4",
    "DeletionProtection": {"DeletionProtectionEnabled": False, "Reason": "Managed by Ansible"},
}


def _alb(**overrides):
    """Return an ALB fixture isolated from the shared constant."""
    item = copy.deepcopy(ALB)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base included)."""
    params = {
        "state": "present",
        "load_balancer_id": None,
        "name": None,
        "address_type": None,
        "vpc_id": None,
        "zone_mappings": None,
        "ip_version": "IPv4",
        "charge_type": "POSTPAID_BY_HOUR",
        "bandwidth_package_id": None,
        "internet_address_type": "EIP",
        "deletion_protection": None,
        "deletion_protection_reason": "Managed by Ansible",
        "tags": None,
        "client_token": None,
        "retries": 5,
        "waiter_delay": 5,
        "waiter_timeout": 120,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    args = dict(_params())
    args.update(extra)
    return module_args(**args)


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


def _plain(value):
    """Convert a fake SDK model back to plain data for the store."""
    if value is None:
        return None
    if hasattr(value, "_value"):  # _JsonModel round-trippable payload
        return value._value
    if hasattr(value, "__dict__"):  # TagInfo / FakeRequest attribute bag
        return {k: _plain(v) for k, v in vars(value).items() if not k.startswith("_")}
    return value


class FakeAlbClient(object):
    """In-memory ALB client that mutates a small load-balancer store."""

    def __init__(self, albs=None):
        self.albs = [copy.deepcopy(a) for a in (albs or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeLoadBalancers(self, request):
        self._record("DescribeLoadBalancers", request)
        return SimpleNamespace(LoadBalancers=[FakeResource(dict(a)) for a in self.albs])

    def DescribeLoadBalancerDetail(self, request):
        self._record("DescribeLoadBalancerDetail", request)
        for item in self.albs:
            if item.get("LoadBalancerId") == request.LoadBalancerId:
                return SimpleNamespace(LoadBalancerDetail=FakeResource(dict(item)))
        return SimpleNamespace(LoadBalancerDetail=FakeResource({}))

    def CreateLoadBalancer(self, request):
        self._record("CreateLoadBalancer", request)
        self._next += 1
        item = {
            "LoadBalancerId": "alb-fake-%03d" % self._next,
            "LoadBalancerName": request.LoadBalancerName,
            "AddressType": request.AddressType,
            "VpcId": request.VpcId,
            "AddressIpVersion": request.AddressIpVersion,
            "DeletionProtection": {
                "DeletionProtectionEnabled": bool(request.DeleteProtection.DeletionProtectionEnabled),
                "Reason": request.DeleteProtection.Reason,
            },
            "ZoneMappings": _plain(request.ZoneMappings),
        }
        self.albs.append(item)
        return SimpleNamespace(LoadBalancerId=item["LoadBalancerId"], RequestId="req-fake")

    def ModifyLoadBalancerAttributes(self, request):
        self._record("ModifyLoadBalancerAttributes", request)
        for item in self.albs:
            if item.get("LoadBalancerId") == request.LoadBalancerId:
                if getattr(request, "LoadBalancerName", None) is not None:
                    item["LoadBalancerName"] = request.LoadBalancerName
                if getattr(request, "DeletionProtection", None) is not None:
                    item["DeletionProtection"] = {
                        "DeletionProtectionEnabled": bool(request.DeletionProtection),
                        "Reason": "Managed by Ansible",
                    }
        return SimpleNamespace(RequestId="req-fake")

    def ModifyLoadBalancerAddressType(self, request):
        self._record("ModifyLoadBalancerAddressType", request)
        for item in self.albs:
            if item.get("LoadBalancerId") == request.LoadBalancerId:
                item["AddressType"] = request.AddressType
                if getattr(request, "ZoneMappings", None) is not None:
                    item["ZoneMappings"] = _plain(request.ZoneMappings)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteLoadBalancers(self, request):
        self._record("DeleteLoadBalancers", request)
        ids = list(request.LoadBalancerIds or [])
        self.albs = [a for a in self.albs if a.get("LoadBalancerId") not in ids]
        return SimpleNamespace(RequestId="req-fake")


class _JsonModel(object):
    """Stand-in for SDK payload models built via json round-trip."""

    def __init__(self):
        self._value = None

    def from_json_string(self, text):
        self._value = json.loads(text)

    def to_json_string(self):
        return json.dumps(self._value)


class FakeAlbModels(FakeModels):
    """FakeModels whose ZoneMappingsItem resolves to a round-trippable class."""

    def __getattr__(self, name):
        if name == "ZoneMappingsItem":
            return _JsonModel
        return super(FakeAlbModels, self).__getattr__(name)


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeAlbModels(), SimpleNamespace(AlbClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_model_none_returns_none():
    assert mod._model(FakeAlbModels().ZoneMappingsItem, None) is None


def test_model_round_trips_payload():
    payload = {"ZoneId": "ap-guangzhou-3", "SubnetId": "subnet-x"}
    obj = mod._model(FakeAlbModels().ZoneMappingsItem, payload)
    assert obj.to_json_string() == json.dumps(payload)


def test_list_request_fields():
    request = mod.list_request(FakeAlbModels())
    assert request.MaxResults == 100


def test_describe_request_fields():
    request = mod.describe_request(FakeAlbModels(), "alb-abc")
    assert request.LoadBalancerId == "alb-abc"


def test_tags_sorted_and_built():
    tags = mod._tags(FakeAlbModels(), {"zebra": "1", "alpha": "2"})
    assert [(t.TagKey, t.TagValue) for t in tags] == [("alpha", "2"), ("zebra", "1")]


def test_tags_none_yields_empty():
    assert mod._tags(FakeAlbModels(), None) == []


def test_create_request_populates_creation_payload():
    models = FakeAlbModels()
    p = _params(
        name="public-app",
        address_type="Internet",
        vpc_id="vpc-8b0a1c2d",
        zone_mappings=[{"ZoneId": "ap-guangzhou-3", "SubnetId": "subnet-x"}],
        ip_version="IPv6",
        charge_type="PREPAID",
        bandwidth_package_id="bwp-1",
        internet_address_type="AntiDDoSEIP",
        deletion_protection=True,
        tags={"env": "prod"},
        client_token="tok-1",
    )
    request = mod.create_request(models, p)
    assert request.AddressType == "Internet"
    assert request.VpcId == "vpc-8b0a1c2d"
    assert request.AddressIpVersion == "IPv6"
    assert request.LoadBalancerName == "public-app"
    assert request.InternetAddressType == "AntiDDoSEIP"
    assert request.ClientToken == "tok-1"
    assert request.ZoneMappings[0].to_json_string() == json.dumps({"ZoneId": "ap-guangzhou-3", "SubnetId": "subnet-x"})
    assert request.LoadBalancerBillingConfig.ChargeType == "PREPAID"
    assert request.LoadBalancerBillingConfig.BandwidthPackageId == "bwp-1"
    assert request.DeleteProtection.DeletionProtectionEnabled is True
    assert request.DeleteProtection.Reason == "Managed by Ansible"
    assert [(t.TagKey, t.TagValue) for t in request.Tags] == [("env", "prod")]


def test_create_request_protection_defaults_false():
    request = mod.create_request(FakeAlbModels(), _params(name="a", address_type="Internet",
                                                          vpc_id="vpc-1", zone_mappings=[{}]))
    assert request.DeleteProtection.DeletionProtectionEnabled is False


def test_update_request_fields():
    request = mod.update_request(FakeAlbModels(), _params(client_token="tok-u"), "alb-abc", "renamed", True)
    assert request.LoadBalancerId == "alb-abc"
    assert request.LoadBalancerName == "renamed"
    assert request.DeletionProtection is True
    assert request.ClientToken == "tok-u"


def test_address_request_fields():
    request = mod.address_request(FakeAlbModels(), _params(bandwidth_package_id="bwp-9"), "alb-abc", "Intranet")
    assert request.LoadBalancerId == "alb-abc"
    assert request.AddressType == "Intranet"
    assert request.BandwidthPackageId == "bwp-9"
    assert request.ZoneMappings == []


def test_address_request_with_zone_mappings():
    request = mod.address_request(
        FakeAlbModels(), _params(zone_mappings=[{"ZoneId": "ap-guangzhou-3", "SubnetId": "subnet-x"}]), "alb-abc", "Intranet"
    )
    assert len(request.ZoneMappings) == 1


def test_delete_request_fields():
    request = mod.delete_request(FakeAlbModels(), _params(client_token="tok-d"), "alb-abc")
    assert request.LoadBalancerIds == ["alb-abc"]
    assert request.ClientToken == "tok-d"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeAlbClient()
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="missing"))
    assert mod.find(module, fake, FakeAlbModels(), module.params) is None


def test_find_matches_by_load_balancer_id(monkeypatch):
    fake = FakeAlbClient([_alb()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(load_balancer_id="alb-8b0a1c2d"))
    value = mod.find(module, fake, FakeAlbModels(), module.params)
    assert value["LoadBalancerName"] == "public-app"


def test_find_matches_by_name(monkeypatch):
    fake = FakeAlbClient([_alb()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="public-app"))
    value = mod.find(module, fake, FakeAlbModels(), module.params)
    assert value["LoadBalancerId"] == "alb-8b0a1c2d"


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeAlbClient(
        [
            _alb(LoadBalancerId="alb-1", LoadBalancerName="dup"),
            _alb(LoadBalancerId="alb-2", LoadBalancerName="dup"),
        ]
    )
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="dup"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeAlbModels(), module.params)
    assert "Multiple ALBs matched" in exc.value.args[0]["msg"]


def test_protected_reads_nested_enabled_flag():
    assert mod._protected(_alb(DeletionProtection={"DeletionProtectionEnabled": True})) is True
    assert mod._protected(_alb()) is False
    assert mod._protected({}) is False


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    module_args()
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeAlbModels(), SimpleNamespace(AlbClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    # address_type must be valid: it has choices and no default, so an explicit
    # None (as pre-filled by _params) would fail Ansible validation before the
    # SDK call is ever made.
    _run_args(name="public-app", address_type="Internet")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


def test_present_creates_load_balancer(monkeypatch):
    fake = FakeAlbClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", name="public-app", address_type="Internet", vpc_id="vpc-8b0a1c2d",
                zone_mappings=[{"ZoneId": "ap-guangzhou-3", "SubnetId": "subnet-x"}],
                deletion_protection=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["load_balancer"]["LoadBalancerId"] == "alb-fake-001"
    assert result["load_balancer"]["LoadBalancerName"] == "public-app"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeLoadBalancers") == 2  # find + refetch
    assert "DescribeLoadBalancerDetail" in names
    assert names.count("CreateLoadBalancer") == 1
    assert "ModifyLoadBalancerAttributes" not in names


def test_present_missing_creation_params_fails(monkeypatch):
    fake = FakeAlbClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", name="public-app")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert sorted(payload["missing"]) == ["address_type", "vpc_id", "zone_mappings"]


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeAlbClient([_alb()])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="public-app")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["load_balancer"]["LoadBalancerId"] == "alb-8b0a1c2d"
    names = [c[0] for c in fake.calls]
    assert "CreateLoadBalancer" not in names
    assert "ModifyLoadBalancerAttributes" not in names
    assert "ModifyLoadBalancerAddressType" not in names


def test_present_name_drift_triggers_update(monkeypatch):
    fake = FakeAlbClient([_alb()])
    _make_module(monkeypatch, fake)
    module_args(state="present", load_balancer_id="alb-8b0a1c2d", name="public-app-v2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["load_balancer"]["LoadBalancerName"] == "public-app-v2"
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyLoadBalancerAttributes") == 1
    assert "ModifyLoadBalancerAddressType" not in names


def test_present_protection_enable_triggers_update(monkeypatch):
    fake = FakeAlbClient([_alb()])
    _make_module(monkeypatch, fake)
    module_args(state="present", load_balancer_id="alb-8b0a1c2d", name="public-app",
                deletion_protection=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["load_balancer"]["DeletionProtection"]["DeletionProtectionEnabled"] is True
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyLoadBalancerAttributes") == 1
    update = [c for c in fake.calls if c[0] == "ModifyLoadBalancerAttributes"][0][1]
    assert update.DeletionProtection is True


def test_present_address_type_conversion(monkeypatch):
    fake = FakeAlbClient([_alb()])
    _make_module(monkeypatch, fake)
    module_args(state="present", load_balancer_id="alb-8b0a1c2d", name="public-app",
                address_type="Intranet")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["load_balancer"]["AddressType"] == "Intranet"
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyLoadBalancerAddressType") == 1
    convert = [c for c in fake.calls if c[0] == "ModifyLoadBalancerAddressType"][0][1]
    assert convert.AddressType == "Intranet"
    # Name and protection unchanged -> no attribute write needed.
    assert "ModifyLoadBalancerAttributes" not in names


def test_present_immutable_vpc_change_fails(monkeypatch):
    fake = FakeAlbClient([_alb()])
    _make_module(monkeypatch, fake)
    module_args(state="present", load_balancer_id="alb-8b0a1c2d", name="public-app",
                vpc_id="vpc-other")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["immutable_changes"]["VpcId"] == {"before": "vpc-8b0a1c2d", "after": "vpc-other"}
    assert not any(n.startswith("Modify") for n, _ in fake.calls)


def test_present_multiple_matches_fails(monkeypatch):
    fake = FakeAlbClient(
        [
            _alb(LoadBalancerId="alb-1", LoadBalancerName="dup"),
            _alb(LoadBalancerId="alb-2", LoadBalancerName="dup"),
        ]
    )
    _make_module(monkeypatch, fake)
    module_args(state="present", name="dup")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple ALBs matched" in exc.value.args[0]["msg"]


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeAlbClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="present", name="public-app", address_type="Internet",
                vpc_id="vpc-8b0a1c2d",
                zone_mappings=[{"ZoneId": "ap-guangzhou-3", "SubnetId": "subnet-x"}])
    result = run(mod.run_module)
    assert result["changed"] is True
    # Check mode reports the desired target, not a real resource.
    assert result["load_balancer"]["LoadBalancerName"] == "public-app"
    assert result["load_balancer"]["DeletionProtection"] is False
    assert not any("CreateLoadBalancer" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeAlbClient([_alb()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="present", load_balancer_id="alb-8b0a1c2d",
                name="public-app", address_type="Intranet")
    result = run(mod.run_module)
    assert result["changed"] is True
    # No write happened, so the reported ALB is the pre-change state.
    assert result["load_balancer"]["AddressType"] == "Internet"
    assert not any(n.startswith("Modify") for n, _ in fake.calls)


def test_absent_removes_unprotected(monkeypatch):
    fake = FakeAlbClient([_alb()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="public-app")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["load_balancer"] is None
    names = [c[0] for c in fake.calls]
    assert names.count("DeleteLoadBalancers") == 1
    assert "ModifyLoadBalancerAttributes" not in names  # no protection to lift
    assert fake.albs == []


def test_absent_protected_requires_opt_out(monkeypatch):
    fake = FakeAlbClient([_alb(DeletionProtection={"DeletionProtectionEnabled": True})])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="public-app")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "set deletion_protection=false" in exc.value.args[0]["msg"]
    assert not any("DeleteLoadBalancers" == c[0] for c in fake.calls)


def test_absent_protected_disables_then_deletes(monkeypatch):
    fake = FakeAlbClient([_alb(DeletionProtection={"DeletionProtectionEnabled": True})])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="public-app", deletion_protection=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["load_balancer"] is None
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyLoadBalancerAttributes") == 1
    assert names.count("DeleteLoadBalancers") == 1
    disable = [c for c in fake.calls if c[0] == "ModifyLoadBalancerAttributes"][0][1]
    assert disable.DeletionProtection is False
    assert fake.albs == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeAlbClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="missing")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["load_balancer"] is None
    assert not any("DeleteLoadBalancers" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeAlbClient([_alb()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", name="public-app")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["load_balancer"] is None
    assert not any(n.startswith("Delete") for n, _ in fake.calls)
    assert len(fake.albs) == 1
