"""Unit tests for the tke_cluster_endpoint write module (run_module flows).

Drives ``run_module()`` against an in-memory fake TKE client whose
create / delete operations mutate an endpoint store so post-write
describes converge immediately.

Endpoints are existence-managed: present creates whichever network scope
(public/private) is missing, absent deletes the matching one. Configured
domain/SG/subnet values only shape the create request; no drift
reconciliation happens on an existing endpoint.

Scenario matrix:

* present/absent on a matching endpoint are idempotent
* present creates public and private endpoints (request field checks)
* absent deletes the matching endpoint (check-mode dry run included)
* the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tke_cluster_endpoint as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CLUSTER_ID = "cls-1234"


class FakeTkeClient(object):
    """In-memory TKE client holding public/private endpoint describe state."""

    def __init__(self, external=None, internal=None):
        self.external = copy.deepcopy(external)  # None or {Endpoint, Domain, SecurityGroup}
        self.internal = copy.deepcopy(internal)  # None or {Endpoint, Domain, SecurityGroup, SubnetId}
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeClusterEndpoints(self, request):
        self._record("DescribeClusterEndpoints", request)
        ext = self.external or {}
        internal = self.internal or {}
        return SimpleNamespace(
            ClusterExternalEndpoint=ext.get("Endpoint"),
            ClusterExternalDomain=ext.get("Domain"),
            SecurityGroup=ext.get("SecurityGroup"),
            ClusterIntranetEndpoint=internal.get("Endpoint"),
            ClusterIntranetDomain=internal.get("Domain"),
            IntranetSecurityGroup=internal.get("SecurityGroup"),
            ClusterIntranetSubnetId=internal.get("SubnetId"),
        )

    def CreateClusterEndpoint(self, request):
        self._record("CreateClusterEndpoint", request)
        public = bool(getattr(request, "IsExtranet", False))
        if public:
            self.external = {
                "Endpoint": "https://cls-ext.example.com",
                "Domain": getattr(request, "Domain", None),
                "SecurityGroup": getattr(request, "SecurityGroup", None),
            }
        else:
            self.internal = {
                "Endpoint": "https://10.0.0.10",
                "Domain": getattr(request, "Domain", None),
                "SecurityGroup": getattr(request, "SecurityGroup", None),
                "SubnetId": getattr(request, "SubnetId", None),
            }
        return SimpleNamespace(RequestId="req-fake")

    def DeleteClusterEndpoint(self, request):
        self._record("DeleteClusterEndpoint", request)
        if bool(getattr(request, "IsExtranet", False)):
            self.external = None
        else:
            self.internal = None
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TkeClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _args(access="private", **overrides):
    params = {"state": "present", "cluster_id": CLUSTER_ID, "access": access}
    params.update(overrides)
    return module_args(**params)


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_existing_endpoint_is_idempotent(monkeypatch):
    fake = FakeTkeClient(internal={"Endpoint": "https://10.0.0.10", "Domain": None, "SecurityGroup": None, "SubnetId": "subnet-1"})
    _make_module(monkeypatch, fake)
    _args(access="private", subnet_id="subnet-1")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["endpoint"]["Access"] == "private"
    assert result["endpoint"]["Endpoint"] == "https://10.0.0.10"
    assert result["endpoint"]["ClusterId"] == CLUSTER_ID
    assert [c for c, unused in fake.calls] == ["DescribeClusterEndpoints"]


def test_present_existing_endpoint_ignores_create_fields(monkeypatch):
    # No drift reconciliation: an existing endpoint stays put even when the
    # requested subnet/domain differ.
    fake = FakeTkeClient(internal={"Endpoint": "https://10.0.0.10", "Domain": None, "SecurityGroup": None, "SubnetId": "subnet-1"})
    _make_module(monkeypatch, fake)
    _args(access="private", subnet_id="subnet-other", domain="custom.example.com")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["endpoint"]["Endpoint"] == "https://10.0.0.10"


def test_create_private_endpoint(monkeypatch):
    fake = FakeTkeClient()
    _make_module(monkeypatch, fake)
    _args(access="private", subnet_id="subnet-1", security_group_id="sg-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["endpoint"]["Endpoint"] == "https://10.0.0.10"
    assert result["endpoint"]["Access"] == "private"
    ops = [c for c, unused in fake.calls]
    assert "CreateClusterEndpoint" in ops
    create_call = [r for c, r in fake.calls if c == "CreateClusterEndpoint"][0]
    assert create_call.IsExtranet is False
    assert create_call.SubnetId == "subnet-1"
    assert create_call.SecurityGroup == "sg-1"


def test_create_public_endpoint_serializes_extensive_parameters(monkeypatch):
    fake = FakeTkeClient()
    _make_module(monkeypatch, fake)
    _args(access="public", domain="api.example.com", extensive_parameters={"InternetMaxBandwidthOut": 5, "Zone": "ap-guangzhou-2"})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["endpoint"]["Access"] == "public"
    assert result["endpoint"]["Endpoint"] == "https://cls-ext.example.com"
    create_call = [r for c, r in fake.calls if c == "CreateClusterEndpoint"][0]
    assert create_call.IsExtranet is True
    assert create_call.Domain == "api.example.com"
    assert create_call.ExtensiveParameters == json.dumps({"InternetMaxBandwidthOut": 5, "Zone": "ap-guangzhou-2"}, sort_keys=True, separators=(",", ":"))


def test_create_with_existing_other_access(monkeypatch):
    # A private endpoint already exists; requesting public creates only public.
    fake = FakeTkeClient(internal={"Endpoint": "https://10.0.0.10", "Domain": None, "SecurityGroup": None, "SubnetId": "subnet-1"})
    _make_module(monkeypatch, fake)
    _args(access="public")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["endpoint"]["Access"] == "public"
    assert fake.internal is not None  # untouched
    ops = [c for c, unused in fake.calls]
    assert ops.count("CreateClusterEndpoint") == 1


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient()
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, access="public")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["endpoint"] is None
    assert fake.external is None
    assert "CreateClusterEndpoint" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_endpoint_is_idempotent(monkeypatch):
    fake = FakeTkeClient()
    _make_module(monkeypatch, fake)
    _args(state="absent", access="public")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["endpoint"] is None
    assert [c for c, unused in fake.calls] == ["DescribeClusterEndpoints"]


def test_absent_deletes_matching_endpoint_only(monkeypatch):
    fake = FakeTkeClient(
        external={"Endpoint": "https://cls-ext.example.com", "Domain": None, "SecurityGroup": None},
        internal={"Endpoint": "https://10.0.0.10", "Domain": None, "SecurityGroup": None, "SubnetId": "subnet-1"},
    )
    _make_module(monkeypatch, fake)
    _args(state="absent", access="public")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["endpoint"] is None
    assert fake.external is None
    assert fake.internal is not None
    delete_call = [r for c, r in fake.calls if c == "DeleteClusterEndpoint"][0]
    assert delete_call.IsExtranet is True


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTkeClient(internal={"Endpoint": "https://10.0.0.10", "Domain": None, "SecurityGroup": None, "SubnetId": "subnet-1"})
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent", access="private")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["endpoint"]["Endpoint"] == "https://10.0.0.10"  # preview reports the live endpoint
    assert fake.internal is not None
    assert "DeleteClusterEndpoint" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeClusterEndpoints(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args(access="public")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
