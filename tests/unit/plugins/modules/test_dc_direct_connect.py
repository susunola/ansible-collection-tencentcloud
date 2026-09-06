"""Unit tests for the dc_direct_connect write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/dc_direct_connect.py`` with an in-memory fake DC client
whose write operations mutate the physical-connection store, so the
module's post-write ``find`` refetch converges immediately. Connections
are matched by ``direct_connect_id`` or by ``name``; both lookup paths,
the multiple-match guard, the nine-field creation-parameter requirement,
the immutable (access point / carrier / port type / location) guard and
check-mode dry runs are exercised.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dc_direct_connect as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

DC = {
    "DirectConnectId": "dc-8b0a1c2d",
    "DirectConnectName": "primary-circuit",
    "AccessPointId": "ap-8b0a1c2d",
    "LineOperator": "ChinaTelecom",
    "PortType": "10GBase-LR",
    "CircuitCode": "circuit-123",
    "Location": "Customer IDC A",
    "Bandwidth": 1000,
    "Vlan": None,
    "TencentAddress": "192.0.2.1/30",
    "CustomerAddress": "192.0.2.2/30",
    "CustomerName": "Example Corp",
    "CustomerContactMail": "network@example.com",
    "CustomerContactNumber": "13800000000",
    "FaultReportContactPerson": "ops",
    "FaultReportContactNumber": "13900000000",
    "FaultReportContactEmail": "ops@example.com",
    "SignLaw": True,
}


def _dc(**overrides):
    """Return a physical-connection fixture isolated from the shared constant."""
    item = copy.deepcopy(DC)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base included)."""
    params = {
        "state": "present",
        "direct_connect_id": None,
        "name": None,
        "access_point_id": None,
        "line_operator": None,
        "port_type": None,
        "circuit_code": None,
        "location": None,
        "bandwidth": None,
        "redundant_direct_connect_id": None,
        "vlan": None,
        "tencent_address": None,
        "customer_address": None,
        "customer_name": None,
        "customer_contact_mail": None,
        "customer_contact_number": None,
        "fault_contact_name": None,
        "fault_contact_number": None,
        "fault_contact_email": None,
        "sign_law": None,
        "macsec": None,
        "tags": None,
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


class FakeDcClient(object):
    """In-memory DC client that mutates a small physical-connection store."""

    def __init__(self, connections=None):
        self.connections = [copy.deepcopy(c) for c in (connections or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeDirectConnects(self, request):
        self._record("DescribeDirectConnects", request)
        ids = getattr(request, "DirectConnectIds", None)
        items = self.connections
        if ids:
            items = [c for c in items if c.get("DirectConnectId") in ids]
        return SimpleNamespace(DirectConnectSet=[FakeResource(dict(c)) for c in items])

    def CreateDirectConnect(self, request):
        self._record("CreateDirectConnect", request)
        self._next += 1
        item = {"DirectConnectId": "dc-fake-%03d" % self._next}
        for api in mod.FIELDS:
            item[api] = getattr(request, api, None)
        self.connections.append(item)
        return SimpleNamespace(DirectConnectIdSet=[item["DirectConnectId"]], RequestId="req-fake")

    def ModifyDirectConnectAttribute(self, request):
        self._record("ModifyDirectConnectAttribute", request)
        for item in self.connections:
            if item.get("DirectConnectId") == request.DirectConnectId:
                for api in mod.FIELDS:
                    value = getattr(request, api, None)
                    if value is not None:
                        item[api] = value
        return SimpleNamespace(RequestId="req-fake")

    def DeleteDirectConnect(self, request):
        self._record("DeleteDirectConnect", request)
        self.connections = [
            c for c in self.connections if c.get("DirectConnectId") != request.DirectConnectId
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(DcClient=object)),
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


def test_describe_request_with_direct_connect_id():
    request = mod.describe_request(FakeModels(), _params(direct_connect_id="dc-abc"))
    assert request.Offset == 0
    assert request.Limit == 100
    assert request.DirectConnectIds == ["dc-abc"]


def test_describe_request_without_direct_connect_id():
    request = mod.describe_request(FakeModels(), _params(name="primary-circuit"))
    assert getattr(request, "DirectConnectIds", None) is None


def test_tags_sorted_and_built():
    tags = mod._tags(FakeModels(), {"zebra": "1", "alpha": "2"})
    assert [(t.Key, t.Value) for t in tags] == [("alpha", "2"), ("zebra", "1")]


def test_tags_none_yields_empty():
    assert mod._tags(FakeModels(), None) == []


def test_fill_populates_attributes():
    p = _params(
        name="primary-circuit",
        circuit_code="circuit-99",
        vlan=100,
        tencent_address="192.0.2.1/30",
        customer_address="192.0.2.2/30",
        customer_name="Example Corp",
        customer_contact_mail="network@example.com",
        customer_contact_number="13800000000",
        fault_contact_name="ops",
        fault_contact_number="13900000000",
        fault_contact_email="ops@example.com",
        sign_law=True,
        bandwidth=2000,
    )
    request = mod._fill(FakeModels().ModifyDirectConnectAttributeRequest(), p)
    assert request.DirectConnectName == "primary-circuit"
    assert request.CircuitCode == "circuit-99"
    assert request.Vlan == 100
    assert request.TencentAddress == "192.0.2.1/30"
    assert request.CustomerName == "Example Corp"
    assert request.CustomerContactMail == "network@example.com"
    assert request.FaultReportContactPerson == "ops"
    assert request.FaultReportContactEmail == "ops@example.com"
    assert request.SignLaw is True
    assert request.Bandwidth == 2000


def test_create_request_adds_creation_fields():
    models = FakeModels()
    p = _params(
        name="primary-circuit",
        access_point_id="ap-abc",
        line_operator="ChinaTelecom",
        port_type="10GBase-LR",
        location="IDC A",
        redundant_direct_connect_id="dc-backup",
        macsec=True,
        tags={"env": "prod"},
    )
    request = mod.create_request(models, p)
    assert request.AccessPointId == "ap-abc"
    assert request.LineOperator == "ChinaTelecom"
    assert request.PortType == "10GBase-LR"
    assert request.Location == "IDC A"
    assert request.RedundantDirectConnectId == "dc-backup"
    assert request.IsMacSec is True
    assert [(t.Key, t.Value) for t in request.Tags] == [("env", "prod")]


def test_update_request_sets_id():
    request = mod.update_request(FakeModels(), _params(name="renamed"), "dc-abc")
    assert request.DirectConnectId == "dc-abc"
    assert request.DirectConnectName == "renamed"


def test_delete_request_sets_id():
    request = mod.delete_request(FakeModels(), "dc-abc")
    assert request.DirectConnectId == "dc-abc"


def test_find_matches_by_direct_connect_id(monkeypatch):
    fake = FakeDcClient([_dc()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(direct_connect_id="dc-8b0a1c2d"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["DirectConnectName"] == "primary-circuit"


def test_find_matches_by_name(monkeypatch):
    fake = FakeDcClient([_dc()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="primary-circuit"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["DirectConnectId"] == "dc-8b0a1c2d"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeDcClient()
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="missing"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeDcClient(
        [
            _dc(DirectConnectId="dc-1", DirectConnectName="dup"),
            _dc(DirectConnectId="dc-2", DirectConnectName="dup"),
        ]
    )
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="dup"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    assert "Multiple physical connections matched" in exc.value.args[0]["msg"]


def test_comparable_picks_fields():
    value = mod.comparable(_dc())
    assert value["DirectConnectName"] == "primary-circuit"
    assert value["AccessPointId"] == "ap-8b0a1c2d"
    assert value["Bandwidth"] == 1000
    assert value["SignLaw"] is True


def test_comparable_missing_fields_are_lenient():
    value = mod.comparable({})
    assert value["DirectConnectName"] is None
    assert value["SignLaw"] is None


def test_desired_uses_params_and_defaults():
    p = _params(name="primary-circuit", bandwidth=2000, customer_name="New Corp")
    target = mod.desired(p)
    assert target["DirectConnectName"] == "primary-circuit"
    assert target["Bandwidth"] == 2000
    assert target["CustomerName"] == "New Corp"
    assert target["Location"] is None


def test_desired_keeps_current_when_param_omitted():
    current = _dc(Bandwidth=2500, CircuitCode="circuit-77")
    target = mod.desired(_params(name="primary-circuit"), current)
    assert target["Bandwidth"] == 2500
    assert target["CircuitCode"] == "circuit-77"
    assert target["CustomerName"] == "Example Corp"


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
        lambda: (FakeModels(), SimpleNamespace(DcClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args(name="primary-circuit")
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


def test_present_creates_connection(monkeypatch):
    fake = FakeDcClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", name="primary-circuit", access_point_id="ap-8b0a1c2d",
                line_operator="ChinaTelecom", port_type="10GBase-LR", location="IDC A",
                bandwidth=1000, customer_name="Example Corp",
                customer_contact_mail="network@example.com", customer_contact_number="13800000000")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["direct_connect"]["DirectConnectId"] == "dc-fake-001"
    assert result["direct_connect"]["DirectConnectName"] == "primary-circuit"
    assert result["direct_connect"]["Bandwidth"] == 1000
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeDirectConnects") == 2  # find + refetch
    assert names.count("CreateDirectConnect") == 1
    assert not any("ModifyDirectConnectAttribute" == n for n in names)


def test_present_create_records_macsec_and_tags(monkeypatch):
    fake = FakeDcClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", name="primary-circuit", access_point_id="ap-8b0a1c2d",
                line_operator="ChinaTelecom", port_type="10GBase-LR", location="IDC A",
                bandwidth=1000, customer_name="Example Corp",
                customer_contact_mail="network@example.com", customer_contact_number="13800000000",
                macsec=True, redundant_direct_connect_id="dc-backup", tags={"env": "prod"})
    run(mod.run_module)
    create = [c for c in fake.calls if c[0] == "CreateDirectConnect"][0][1]
    assert create.IsMacSec is True
    assert create.RedundantDirectConnectId == "dc-backup"
    assert [(t.Key, t.Value) for t in create.Tags] == [("env", "prod")]


def test_present_missing_creation_params_fails(monkeypatch):
    fake = FakeDcClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", name="primary-circuit")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert "access_point_id" in payload["missing"]
    assert "location" in payload["missing"]
    assert "customer_contact_number" in payload["missing"]


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeDcClient([_dc()])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="primary-circuit")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["direct_connect"]["DirectConnectId"] == "dc-8b0a1c2d"
    names = [c[0] for c in fake.calls]
    assert "CreateDirectConnect" not in names
    assert "ModifyDirectConnectAttribute" not in names


def test_present_drift_triggers_update(monkeypatch):
    fake = FakeDcClient([_dc()])
    _make_module(monkeypatch, fake)
    module_args(state="present", direct_connect_id="dc-8b0a1c2d", bandwidth=2000,
                customer_name="Renamed Corp")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["direct_connect"]["Bandwidth"] == 2000
    assert result["direct_connect"]["CustomerName"] == "Renamed Corp"
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyDirectConnectAttribute") == 1
    modify = [c for c in fake.calls if c[0] == "ModifyDirectConnectAttribute"][0][1]
    assert modify.DirectConnectId == "dc-8b0a1c2d"


def test_present_immutable_access_point_change_fails(monkeypatch):
    fake = FakeDcClient([_dc()])
    _make_module(monkeypatch, fake)
    module_args(state="present", direct_connect_id="dc-8b0a1c2d", access_point_id="ap-other")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["immutable_changes"]["AccessPointId"] == {
        "before": "ap-8b0a1c2d",
        "after": "ap-other",
    }
    assert not any("ModifyDirectConnectAttribute" == c[0] for c in fake.calls)


def test_present_multiple_matches_fails(monkeypatch):
    fake = FakeDcClient(
        [
            _dc(DirectConnectId="dc-1", DirectConnectName="dup"),
            _dc(DirectConnectId="dc-2", DirectConnectName="dup"),
        ]
    )
    _make_module(monkeypatch, fake)
    module_args(state="present", name="dup")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple physical connections matched" in exc.value.args[0]["msg"]


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeDcClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="present", name="primary-circuit",
                access_point_id="ap-8b0a1c2d", line_operator="ChinaTelecom",
                port_type="10GBase-LR", location="IDC A", bandwidth=1000,
                customer_name="Example Corp", customer_contact_mail="network@example.com",
                customer_contact_number="13800000000")
    result = run(mod.run_module)
    assert result["changed"] is True
    # Check mode reports the desired target, not a real resource.
    assert result["direct_connect"]["DirectConnectName"] == "primary-circuit"
    assert "Bandwidth" in result["direct_connect"]
    assert not any("CreateDirectConnect" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeDcClient([_dc()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="present", direct_connect_id="dc-8b0a1c2d",
                bandwidth=2000)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["direct_connect"]["Bandwidth"] == 2000  # desired target
    assert not any("ModifyDirectConnectAttribute" == c[0] for c in fake.calls)
    assert fake.connections[0]["Bandwidth"] == 1000  # store untouched


def test_absent_removes_connection(monkeypatch):
    fake = FakeDcClient([_dc()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="primary-circuit")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["direct_connect"] is None
    names = [c[0] for c in fake.calls]
    assert names.count("DeleteDirectConnect") == 1
    assert fake.connections == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeDcClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="missing")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["direct_connect"] is None
    assert not any("DeleteDirectConnect" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDcClient([_dc()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", name="primary-circuit")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["direct_connect"] is None
    assert not any("DeleteDirectConnect" == c[0] for c in fake.calls)
    assert len(fake.connections) == 1
