"""Unit tests for the waf_host write module (run_module flows).

Drives ``run_module()`` against an in-memory fake WAF client whose create /
modify / delete operations mutate a protected-host store so post-write
describes converge immediately.

The module manages one protected host per ``(instance_id, domain)``.
``host`` is an opaque SDK-shaped ``HostRecord`` dict whose exact key set is
compared for drift; ``tags`` apply at creation only and are ignored for
updates. A describe that raises ``ResourceNotFound`` reads as absent.

Scenario matrix:

* absent on a missing host is idempotent (empty describe and not-found)
* absent with a live host deletes it (check-mode dry run included)
* present requires the host dict and creates when missing (tags applied)
* no-op when the host already matches and drift triggers a modify
* check-mode dry run and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import waf_host as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "waf_2abcdef"
DOMAIN = "api.example.com"

HOST_RECORD = {
    "DomainId": "host-1001",
    "Domain": DOMAIN,
    "Edition": "clb-waf",
    "Region": "ap-guangzhou",
    "LoadBalancerSet": [],
    "FlowMode": 1,
}

HOST_PARAMS = {
    "Edition": "clb-waf",
    "Region": "ap-guangzhou",
    "LoadBalancerSet": [],
    "FlowMode": 1,
}


class ResourceNotFound(Exception):
    def get_code(self):
        return "ResourceNotFound.Host"


class FakeWafClient(object):
    """In-memory WAF client holding a protected-host store."""

    def __init__(self, hosts=None, describe_not_found=False):
        self.hosts = [copy.deepcopy(t) for t in (hosts or [])]
        self.describe_not_found = describe_not_found
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_domain(self, domain):
        for host in self.hosts:
            if host.get("Domain") == domain:
                return host
        return None

    def DescribeHost(self, request):
        self._record("DescribeHost", request)
        if self.describe_not_found:
            raise ResourceNotFound("host does not exist")
        host = self._by_domain(getattr(request, "Domain", None))
        return SimpleNamespace(Host=FakeResource(copy.deepcopy(host)) if host else None)

    def CreateHost(self, request):
        self._record("CreateHost", request)
        self.describe_not_found = False
        host = dict(vars(getattr(request, "Host", None)) or {})
        self._next += 1
        host.setdefault("DomainId", "host-%d" % (2000 + self._next))
        host["Domain"] = getattr(request.Host, "Domain", DOMAIN)
        self.hosts = [h for h in self.hosts if h.get("Domain") != host["Domain"]]
        self.hosts.append(host)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyHost(self, request):
        self._record("ModifyHost", request)
        self.describe_not_found = False
        host = dict(vars(getattr(request, "Host", None)) or {})
        target = self._by_domain(getattr(request.Host, "Domain", None))
        if target is not None:
            target.update(host)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteHost(self, request):
        self._record("DeleteHost", request)
        for item in getattr(request, "HostsDel", None) or []:
            domain = getattr(item, "Domain", None)
            domain_id = getattr(item, "DomainId", None)
            self.hosts = [
                h
                for h in self.hosts
                if not ((domain and h.get("Domain") == domain) or (domain_id and h.get("DomainId") == domain_id))
            ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(WafClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _present_args(**overrides):
    params = {
        "state": "present",
        "instance_id": INSTANCE_ID,
        "domain": DOMAIN,
        "host": copy.deepcopy(HOST_PARAMS),
        "tags": {"team": "security"},
    }
    params.update(overrides)
    return module_args(**params)


def _absent_args(**overrides):
    params = {"state": "absent", "instance_id": INSTANCE_ID, "domain": DOMAIN}
    params.update(overrides)
    return module_args(**params)


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_host_is_idempotent(monkeypatch):
    fake = FakeWafClient(hosts=[])
    _make_module(monkeypatch, fake)
    _absent_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["waf_host"] is None
    assert [c for c, unused in fake.calls] == ["DescribeHost"]


def test_absent_missing_host_is_idempotent_on_not_found(monkeypatch):
    fake = FakeWafClient(hosts=[copy.deepcopy(HOST_RECORD)], describe_not_found=True)
    _make_module(monkeypatch, fake)
    _absent_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["waf_host"] is None


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeWafClient(hosts=[HOST_RECORD])
    _make_module(monkeypatch, fake)
    _absent_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["waf_host"]["DomainId"] == "host-1001"
    assert len(fake.hosts) == 1
    assert "DeleteHost" not in [c for c, unused in fake.calls]


def test_absent_deletes_host(monkeypatch):
    fake = FakeWafClient(hosts=[HOST_RECORD])
    _make_module(monkeypatch, fake)
    _absent_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["waf_host"] is None
    assert fake.hosts == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteHost" in ops
    delete_call = [r for c, r in fake.calls if c == "DeleteHost"][0]
    assert delete_call.HostsDel[0].Domain == DOMAIN
    assert delete_call.HostsDel[0].DomainId == "host-1001"
    assert delete_call.HostsDel[0].InstanceID == INSTANCE_ID


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_requires_host(monkeypatch):
    fake = FakeWafClient(hosts=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", instance_id=INSTANCE_ID, domain=DOMAIN)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "host" in exc.value.args[0]["msg"]


def test_create_host(monkeypatch):
    fake = FakeWafClient(hosts=[])
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["waf_host"]["Domain"] == DOMAIN
    assert result["waf_host"]["DomainId"] == "host-2001"
    assert result["waf_host"]["FlowMode"] == 1
    assert len(fake.hosts) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeHost"
    assert "CreateHost" in ops
    assert ops[-1] == "DescribeHost"
    create_call = [r for c, r in fake.calls if c == "CreateHost"][0]
    assert create_call.InstanceID == INSTANCE_ID
    assert dict(vars(create_call.Host))["Edition"] == "clb-waf"
    tags = sorted((getattr(t, "TagKey", None), getattr(t, "TagValue", None)) for t in create_call.Tags)
    assert tags == [("team", "security")]


def test_create_on_not_found_describe(monkeypatch):
    # A ResourceNotFound describe reads as absent, so present creates.
    fake = FakeWafClient(hosts=[], describe_not_found=True)
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["waf_host"]["Domain"] == DOMAIN
    assert "CreateHost" in [c for c, unused in fake.calls]


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeWafClient(hosts=[])
    _make_module(monkeypatch, fake)
    _present_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["waf_host"] is None
    assert fake.hosts == []
    assert "CreateHost" not in [c for c, unused in fake.calls]


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeWafClient(hosts=[HOST_RECORD])
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["waf_host"]["DomainId"] == "host-1001"
    assert "ModifyHost" not in [c for c, unused in fake.calls]


def test_tags_are_ignored_on_existing_host(monkeypatch):
    # tags only apply at creation, so a changed tag map on a live host is
    # not drift.
    fake = FakeWafClient(hosts=[HOST_RECORD])
    _make_module(monkeypatch, fake)
    _present_args(tags={"team": "other"})
    result = run(mod.run_module)
    assert result["changed"] is False


def test_flow_mode_drift_updates(monkeypatch):
    fake = FakeWafClient(hosts=[HOST_RECORD])
    _make_module(monkeypatch, fake)
    drifted = dict(HOST_PARAMS, FlowMode=2)
    _present_args(host=drifted)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["waf_host"]["FlowMode"] == 2
    ops = [c for c, unused in fake.calls]
    assert "ModifyHost" in ops
    modify_call = [r for c, r in fake.calls if c == "ModifyHost"][0]
    assert modify_call.InstanceID == INSTANCE_ID
    assert dict(vars(modify_call.Host))["FlowMode"] == 2
    assert dict(vars(modify_call.Host))["DomainId"] == "host-1001"


def test_update_by_domain_id(monkeypatch):
    # With domain_id supplied up front the target carries DomainId too; a
    # domain field drift still triggers the modify.
    fake = FakeWafClient(hosts=[HOST_RECORD])
    _make_module(monkeypatch, fake)
    drifted = dict(HOST_PARAMS, FlowMode=3)
    _present_args(domain_id="host-1001", host=drifted)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["waf_host"]["FlowMode"] == 3
    modify_call = [r for c, r in fake.calls if c == "ModifyHost"][0]
    assert dict(vars(modify_call.Host))["DomainId"] == "host-1001"


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeHost(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _present_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
