"""Unit tests for the teo_acceleration_domain write module (helpers + run_module).

Covers the create / drift-update / enable-disable / delete flows of
``plugins/modules/teo_acceleration_domain.py`` with an in-memory fake EdgeOne
client whose write operations mutate the domain store, so the module's
post-write ``find_domain`` refetch converges immediately. Domains are matched
by ``DomainName`` across the paged DescribeAccelerationDomains list
(Limit 200). Creation and in-place updates go through
Create/ModifyAccelerationDomain; on/offline transitions go through a
separate ModifyAccelerationDomainStatuses call.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import teo_acceleration_domain as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

DOMAIN = {
    "ZoneId": "zone-1",
    "DomainName": "app.example.com",
    "OriginDetail": {"OriginType": "IP_DOMAIN", "Origin": "192.0.2.10", "HostHeader": ""},
    "OriginProtocol": "FOLLOW",
    "HttpOriginPort": 80,
    "HttpsOriginPort": 443,
    "IPv6Status": "follow",
    "DomainStatus": "online",
}


def _domain(**overrides):
    """API-shaped acceleration-domain dict isolated from the shared constant."""
    item = copy.deepcopy(DOMAIN)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec."""
    params = {
        "state": "present",
        "zone_id": "zone-1",
        "domain_name": "app.example.com",
        "origin_type": "IP_DOMAIN",
        "origin": "192.0.2.10",
        "host_header": None,
        "origin_protocol": "FOLLOW",
        "http_origin_port": 80,
        "https_origin_port": 443,
        "ipv6_status": "follow",
        "enabled": True,
        "force": False,
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


class FakeTeoClient(object):
    """In-memory TeoClient stand-in.

    Stores API-shaped acceleration-domain dicts. DescribeAccelerationDomains
    pages over the store honouring Offset/Limit so find_domain pagination is
    exercised; write operations mutate the store so post-write refetches
    converge.
    """

    def __init__(self, domains=None):
        self.domains = [copy.deepcopy(d) for d in (domains or [])]
        self.calls = []
        self._next_id = 30000

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _origin_info(self, request):
        info = request.OriginInfo
        origin = {"OriginType": info.OriginType, "Origin": info.Origin}
        if hasattr(info, "HostHeader"):
            origin["HostHeader"] = info.HostHeader
        return origin

    def DescribeAccelerationDomains(self, request):
        self._record("DescribeAccelerationDomains", request)
        page = self.domains[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            AccelerationDomains=[FakeResource(dict(d)) for d in page],
            TotalCount=len(self.domains),
            RequestId="req-fake",
        )

    def CreateAccelerationDomain(self, request):
        self._record("CreateAccelerationDomain", request)
        entry = {
            "ZoneId": request.ZoneId,
            "DomainName": request.DomainName,
            "OriginDetail": self._origin_info(request),
            "OriginProtocol": request.OriginProtocol,
            "HttpOriginPort": request.HttpOriginPort,
            "HttpsOriginPort": request.HttpsOriginPort,
            "IPv6Status": request.IPv6Status,
            "DomainStatus": "online",
        }
        self.domains.append(entry)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAccelerationDomain(self, request):
        self._record("ModifyAccelerationDomain", request)
        for stored in self.domains:
            if stored.get("DomainName") != request.DomainName:
                continue
            stored["OriginDetail"] = self._origin_info(request)
            stored["OriginProtocol"] = request.OriginProtocol
            stored["HttpOriginPort"] = request.HttpOriginPort
            stored["HttpsOriginPort"] = request.HttpsOriginPort
            stored["IPv6Status"] = request.IPv6Status
        return SimpleNamespace(RequestId="req-fake")

    def ModifyAccelerationDomainStatuses(self, request):
        self._record("ModifyAccelerationDomainStatuses", request)
        for stored in self.domains:
            if stored.get("DomainName") in list(request.DomainNames or []):
                stored["DomainStatus"] = request.Status
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAccelerationDomains(self, request):
        self._record("DeleteAccelerationDomains", request)
        names = list(request.DomainNames or [])
        self.domains = [d for d in self.domains if d.get("DomainName") not in names]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TeoClient=object)),
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
# request-builder / mapping helper tests
# ---------------------------------------------------------------------------


def test_describe_request_fields():
    request = mod.describe_request(FakeModels(), _params(), offset=5)
    assert request.ZoneId == "zone-1"
    assert request.Offset == 5
    assert request.Limit == 200
    assert request.Filters[0].Name == "domain-name"
    assert request.Filters[0].Values == ["app.example.com"]


def test_origin_info_ip_domain_no_host_header():
    item = mod._origin_info(FakeModels(), _params())
    assert item.OriginType == "IP_DOMAIN"
    assert item.Origin == "192.0.2.10"
    assert not hasattr(item, "HostHeader")
    assert not hasattr(item, "PrivateAccess")


def test_origin_info_ip_domain_with_host_header():
    item = mod._origin_info(FakeModels(), _params(host_header="origin.example.com"))
    assert item.HostHeader == "origin.example.com"


def test_origin_info_cos_sets_private_access_off():
    item = mod._origin_info(FakeModels(), _params(origin_type="COS", origin="bucket-1.cos.cn"))
    assert item.OriginType == "COS"
    assert item.PrivateAccess == "off"
    assert not hasattr(item, "HostHeader")


def test_create_request_fields():
    request = mod.create_request(FakeModels(), _params())
    assert request.ZoneId == "zone-1"
    assert request.DomainName == "app.example.com"
    assert request.OriginInfo.Origin == "192.0.2.10"
    assert request.OriginProtocol == "FOLLOW"
    assert request.HttpOriginPort == 80
    assert request.HttpsOriginPort == 443
    assert request.IPv6Status == "follow"


def test_update_request_fields():
    request = mod.update_request(FakeModels(), _params(origin_protocol="HTTPS"))
    assert request.DomainName == "app.example.com"
    assert request.OriginProtocol == "HTTPS"
    assert request.OriginInfo.Origin == "192.0.2.10"


def test_status_request_online_and_offline():
    online = mod.status_request(FakeModels(), _params(enabled=True))
    assert online.DomainNames == ["app.example.com"]
    assert online.Status == "online"
    assert online.Force is False
    offline = mod.status_request(FakeModels(), _params(enabled=False, force=True))
    assert offline.Status == "offline"
    assert offline.Force is True


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params(force=True))
    assert request.ZoneId == "zone-1"
    assert request.DomainNames == ["app.example.com"]
    assert request.Force is True


def test_desired_mapping():
    value = mod.desired(_params())
    assert value == {
        "OriginType": "IP_DOMAIN",
        "Origin": "192.0.2.10",
        "HostHeader": "",
        "OriginProtocol": "FOLLOW",
        "HttpOriginPort": 80,
        "HttpsOriginPort": 443,
        "IPv6Status": "follow",
        "DomainStatus": "online",
    }


def test_desired_offline_when_disabled():
    value = mod.desired(_params(enabled=False))
    assert value["DomainStatus"] == "offline"


def test_current_values_reads_origin_detail():
    value = mod.current_values(_domain(OriginDetail={"OriginType": "COS", "Origin": "b.cos.cn"}))
    assert value["OriginType"] == "COS"
    assert value["Origin"] == "b.cos.cn"
    assert value["HostHeader"] == ""


def test_current_values_tolerates_missing_origin_detail():
    value = mod.current_values(_domain(OriginDetail=None))
    assert value["OriginType"] is None
    assert value["HostHeader"] == ""


# ---------------------------------------------------------------------------
# find_domain tests
# ---------------------------------------------------------------------------


def test_find_domain_no_match_returns_none(monkeypatch):
    fake = FakeTeoClient([_domain(DomainName="other.example.com")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(domain_name="ghost.example.com"))
    assert mod.find_domain(module, fake, FakeModels(), module.params) is None


def test_find_domain_by_name(monkeypatch):
    fake = FakeTeoClient([_domain(DomainName="other.example.com"), _domain()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find_domain(module, fake, FakeModels(), module.params)
    assert value["DomainName"] == "app.example.com"
    assert value["OriginDetail"]["Origin"] == "192.0.2.10"


def test_find_domain_multiple_matches_fails(monkeypatch):
    fake = FakeTeoClient([_domain(), _domain(OriginDetail={"OriginType": "COS", "Origin": "b.cos.cn"})])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find_domain(module, fake, FakeModels(), module.params)
    assert "Multiple EdgeOne acceleration domains matched" in exc.value.args[0]["msg"]


def test_find_domain_paginates_past_200(monkeypatch):
    domains = [_domain(DomainName="bulk-%04d.example.com" % i) for i in range(201)]
    domains.append(_domain())
    fake = FakeTeoClient(domains)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find_domain(module, fake, FakeModels(), module.params)
    assert value["DomainName"] == "app.example.com"
    list_calls = [c for c in fake.calls if c[0] == "DescribeAccelerationDomains"]
    assert len(list_calls) == 2  # pages of 200
    assert [c[1].Offset for c in list_calls] == [0, 200]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_present_requires_origin():
    _run_args(origin=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "origin is required when state=present" in exc.value.args[0]["msg"]


def test_host_header_only_for_ip_domain_origins():
    _run_args(origin_type="COS", origin="b.cos.cn", host_header="h.example.com")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "host_header is only supported for IP_DOMAIN origins" in exc.value.args[0]["msg"]


def test_origin_ports_out_of_range_fails():
    _run_args(http_origin_port=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "origin ports must be between 1 and 65535" in exc.value.args[0]["msg"]


def test_present_creates_domain(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    domain = result["acceleration_domain"]
    assert domain["DomainName"] == "app.example.com"
    assert domain["DomainStatus"] == "online"
    names = [c[0] for c in fake.calls]
    assert names.count("CreateAccelerationDomain") == 1
    assert "ModifyAccelerationDomainStatuses" not in names  # already online


def test_present_creates_then_offlines_when_disabled(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acceleration_domain"]["DomainStatus"] == "offline"
    names = [c[0] for c in fake.calls]
    assert names.count("CreateAccelerationDomain") == 1
    assert names.count("ModifyAccelerationDomainStatuses") == 1


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeTeoClient([_domain()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["acceleration_domain"]["DomainName"] == "app.example.com"
    names = [c[0] for c in fake.calls]
    assert "ModifyAccelerationDomain" not in names
    assert "CreateAccelerationDomain" not in names


def test_present_origin_drift_triggers_update(monkeypatch):
    fake = FakeTeoClient([_domain()])
    _make_module(monkeypatch, fake)
    _run_args(origin="192.0.2.99")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acceleration_domain"]["OriginDetail"]["Origin"] == "192.0.2.99"
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyAccelerationDomain") == 1
    assert "ModifyAccelerationDomainStatuses" not in names


def test_present_disable_drift_only_calls_status(monkeypatch):
    fake = FakeTeoClient([_domain()])
    _make_module(monkeypatch, fake)
    _run_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acceleration_domain"]["DomainStatus"] == "offline"
    names = [c[0] for c in fake.calls]
    assert "ModifyAccelerationDomain" not in names  # config unchanged
    assert names.count("ModifyAccelerationDomainStatuses") == 1


def test_present_origin_and_status_drift(monkeypatch):
    fake = FakeTeoClient([_domain()])
    _make_module(monkeypatch, fake)
    _run_args(origin="192.0.2.99", enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acceleration_domain"]["OriginDetail"]["Origin"] == "192.0.2.99"
    assert result["acceleration_domain"]["DomainStatus"] == "offline"
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyAccelerationDomain") == 1
    assert names.count("ModifyAccelerationDomainStatuses") == 1


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TeoClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params())
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acceleration_domain"] is None
    assert not any("CreateAccelerationDomain" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeTeoClient([_domain()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(origin="192.0.2.99"))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acceleration_domain"]["OriginDetail"]["Origin"] == "192.0.2.10"  # pre-change
    assert not any("ModifyAccelerationDomain" == c[0] for c in fake.calls)


def test_absent_removes_domain(monkeypatch):
    fake = FakeTeoClient([_domain()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acceleration_domain"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteAccelerationDomains"][0][1]
    assert delete.DomainNames == ["app.example.com"]
    assert fake.domains == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeTeoClient([_domain()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", domain_name="ghost.example.com")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["acceleration_domain"] is None
    assert not any("DeleteAccelerationDomains" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTeoClient([_domain()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **_params(state="absent"))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["acceleration_domain"] is not None  # pre-change state
    assert not any("DeleteAccelerationDomains" == c[0] for c in fake.calls)
    assert len(fake.domains) == 1
