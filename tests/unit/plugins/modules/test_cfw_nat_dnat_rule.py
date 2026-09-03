"""Unit tests for the cfw_nat_dnat_rule write module (helpers + run_module).

Creates, updates and deletes Cloud Firewall NAT DNAT forwarding rules. A
rule is identified by firewall_instance_id + protocol + public_ip +
public_port; find_rule walks the offset-paginated DescribeNatFwDnatRule
response (Total-driven) and fails on multiple matches for one public
endpoint. private_ip/private_port are validated as required before any
SDK work when state=present. Updates rewrite the matched rule through
SetNatFwDnatRule (origin vs new rule); deletes address the current rule.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cfw_nat_dnat_rule as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeResource,
    module_args,
    run,
)


class _Model(object):
    """Model stub with attribute assignment plus a real _deserialize."""

    def _deserialize(self, data):
        for key, value in data.items():
            setattr(self, key, value)
        return self


class FakeModels(object):
    """Stand-in for the SDK models module: fresh _Model subclass per name."""

    def __getattr__(self, name):
        return type(name, (_Model,), {})


class _SdkError(Exception):
    """Stand-in for TencentCloudSDKException carrying a code/request id."""

    def __init__(self, code, message="", request_id=None):
        super(_SdkError, self).__init__(message)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def _rule(**overrides):
    """API-shaped rule dict; fresh copy per call."""
    item = {
        "FwInsId": "cfwnat-abc",
        "IpProtocol": "TCP",
        "PublicIpAddress": "203.0.113.10",
        "PublicPort": 443,
        "PrivateIpAddress": "10.0.1.10",
        "PrivatePort": 8443,
        "Description": "app https",
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "firewall_instance_id": "cfwnat-abc",
        "mode": 0,
        "protocol": "TCP",
        "public_ip": "203.0.113.10",
        "public_port": 443,
        "private_ip": "10.0.1.10",
        "private_port": 8443,
        "description": "app https",
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    params = _params(**extra)
    args = {k: v for k, v in params.items() if v is not None}
    for key, value in extra.items():
        if key.startswith("_"):
            args[key] = value
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


def _as_request_rule(rule):
    """Copy a rule dict onto a model instance the way the module builds
    requests from current/params state."""
    item = FakeModels().CfwNatDnatRule()
    for key in ("IpProtocol", "PublicIpAddress", "PublicPort", "PrivateIpAddress", "PrivatePort", "Description"):
        item._deserialize({key: rule.get(key)})
    return item


class FakeCfwClient(object):
    """In-memory CfwClient stand-in storing rule dicts.

    DescribeNatFwDnatRule returns ``Data`` sliced by the request Offset
    with an optional page cap (Total is always the full count); the
    create/set/delete write operations all carry the rule payload inside
    DnatRules / OriginDnat+NewDnat model objects, which the fake reads
    back through the same six attribute names.
    """

    def __init__(self, rules=None, page_size=None):
        self.rules = [dict(r) for r in (rules or [])]
        self.page_size = page_size
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _key(self, rule):
        return (rule.get("FwInsId"), rule.get("IpProtocol"), rule.get("PublicIpAddress"), rule.get("PublicPort"))

    def _match(self, payload, fw_ins_id):
        wanted = {
            "FwInsId": fw_ins_id,
            "IpProtocol": getattr(payload, "IpProtocol", None),
            "PublicIpAddress": getattr(payload, "PublicIpAddress", None),
            "PublicPort": getattr(payload, "PublicPort", None),
        }
        for stored in self.rules:
            if all(stored.get(k) == v for k, v in wanted.items()):
                return stored
        return None

    def DescribeNatFwDnatRule(self, request):
        self._record("DescribeNatFwDnatRule", request)
        offset = getattr(request, "Offset", 0) or 0
        limit = self.page_size or (getattr(request, "Limit", 100) or 100)
        window = self.rules[offset : offset + limit]
        return SimpleNamespace(
            Data=[FakeResource(dict(r)) for r in window],
            Total=len(self.rules),
            RequestId="req-fake",
        )

    def CreateNatFwDnatRule(self, request):
        self._record("CreateNatFwDnatRule", request)
        for payload in request.DnatRules or []:
            stored = _rule(
                FwInsId=request.CfwInstance,
                IpProtocol=payload.IpProtocol,
                PublicIpAddress=payload.PublicIpAddress,
                PublicPort=payload.PublicPort,
                PrivateIpAddress=getattr(payload, "PrivateIpAddress", None),
                PrivatePort=getattr(payload, "PrivatePort", None),
                Description=getattr(payload, "Description", ""),
            )
            self.rules.append(stored)
        return SimpleNamespace(RequestId="req-fake")

    def SetNatFwDnatRule(self, request):
        self._record("SetNatFwDnatRule", request)
        current = self._match(request.OriginDnat, request.CfwInstance)
        if current is not None:
            current["PrivateIpAddress"] = request.NewDnat.PrivateIpAddress
            current["PrivatePort"] = request.NewDnat.PrivatePort
            current["Description"] = request.NewDnat.Description
        return SimpleNamespace(RequestId="req-fake")

    def DeleteNatFwDnatRule(self, request):
        self._record("DeleteNatFwDnatRule", request)
        for payload in request.DnatRules or []:
            current = self._match(payload, request.CfwInstance)
            if current is not None:
                self.rules.remove(current)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(CfwClient=object)),
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
            raise _SdkError("AuthFailure", "auth rejected", request_id="req-err")

        return boom


# ---------------------------------------------------------------------------
# request-builder / helper tests
# ---------------------------------------------------------------------------


def test_describe_request_sets_offset_and_limit():
    request = mod.describe_request(FakeModels(), offset=10)
    assert request.Offset == 10
    assert request.Limit == 100


def test_dnat_rule_carries_all_fields():
    item = mod.dnat_rule(FakeModels(), _params())
    assert item.IpProtocol == "TCP"
    assert item.PublicIpAddress == "203.0.113.10"
    assert item.PublicPort == 443
    assert item.PrivateIpAddress == "10.0.1.10"
    assert item.PrivatePort == 8443
    assert item.Description == "app https"


def test_create_request_wraps_single_rule():
    request = mod.create_request(FakeModels(), _params(mode=1))
    assert request.Mode == 1
    assert request.CfwInstance == "cfwnat-abc"
    assert len(request.DnatRules) == 1
    assert request.DnatRules[0].PublicIpAddress == "203.0.113.10"


def test_update_request_builds_origin_and_new_rules():
    request = mod.update_request(FakeModels(), _params(description="renamed"), _rule())
    assert request.Mode == 0
    assert request.OperationType == "modify"
    assert request.CfwInstance == "cfwnat-abc"
    assert request.OriginDnat.IpProtocol == "TCP"
    assert request.OriginDnat.PublicPort == 443
    assert request.OriginDnat.Description == "app https"
    assert request.NewDnat.Description == "renamed"
    assert request.NewDnat.PrivateIpAddress == "10.0.1.10"


def test_delete_request_carries_current_rule():
    request = mod.delete_request(FakeModels(), _params(), _rule())
    assert request.Mode == 0
    assert request.CfwInstance == "cfwnat-abc"
    assert len(request.DnatRules) == 1
    assert request.DnatRules[0].PublicIpAddress == "203.0.113.10"
    assert request.DnatRules[0].PrivatePort == 8443


def test_find_rule_matches_identity(monkeypatch):
    fake = FakeCfwClient([_rule(), _rule(PublicIpAddress="203.0.113.20", Description="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find_rule(module, fake, FakeModels(), module.params)
    assert value["PublicIpAddress"] == "203.0.113.10"
    assert value["Description"] == "app https"


def test_find_rule_ignores_other_firewall(monkeypatch):
    fake = FakeCfwClient([_rule(FwInsId="cfwnat-other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    assert mod.find_rule(module, fake, FakeModels(), module.params) is None


def test_find_rule_no_match_returns_none(monkeypatch):
    fake = FakeCfwClient([_rule(PublicPort=8443)])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    assert mod.find_rule(module, fake, FakeModels(), module.params) is None


def test_find_rule_multiple_matches_fails(monkeypatch):
    fake = FakeCfwClient([_rule(), _rule(PrivateIpAddress="10.0.1.99")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find_rule(module, fake, FakeModels(), module.params)
    assert "Multiple NAT DNAT rules matched" in exc.value.args[0]["msg"]


def test_find_rule_paginates_to_second_page(monkeypatch):
    # The match lives on page 2 (page size 1).
    fake = FakeCfwClient(
        [_rule(PublicIpAddress="203.0.113.1"), _rule(PublicIpAddress="203.0.113.10")],
        page_size=1,
    )
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find_rule(module, fake, FakeModels(), module.params)
    assert value["PublicIpAddress"] == "203.0.113.10"
    assert [c[0] for c in fake.calls] == ["DescribeNatFwDnatRule", "DescribeNatFwDnatRule"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_present_requires_private_ip():
    _run_args(private_ip=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "private_ip and private_port are required" in exc.value.args[0]["msg"]


def test_present_requires_private_port():
    _run_args(private_port=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "private_ip and private_port are required" in exc.value.args[0]["msg"]


def test_present_noop_when_rule_exists(monkeypatch):
    fake = FakeCfwClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"]["PublicIpAddress"] == "203.0.113.10"
    assert [c[0] for c in fake.calls] == ["DescribeNatFwDnatRule"]


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeCfwClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None
    assert [c[0] for c in fake.calls] == ["DescribeNatFwDnatRule"]


def test_present_create_creates_and_confirms(monkeypatch):
    fake = FakeCfwClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["PrivateIpAddress"] == "10.0.1.10"
    assert [c[0] for c in fake.calls] == [
        "DescribeNatFwDnatRule",
        "CreateNatFwDnatRule",
        "DescribeNatFwDnatRule",
    ]
    assert fake.calls[1][1].DnatRules[0].PublicPort == 443


def test_present_private_target_drift_triggers_update(monkeypatch):
    fake = FakeCfwClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(private_ip="10.0.1.99", private_port=9000)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["PrivateIpAddress"] == "10.0.1.99"
    assert result["rule"]["PrivatePort"] == 9000
    assert [c[0] for c in fake.calls] == [
        "DescribeNatFwDnatRule",
        "SetNatFwDnatRule",
        "DescribeNatFwDnatRule",
    ]
    assert fake.calls[1][1].OperationType == "modify"
    assert fake.calls[1][1].NewDnat.PrivateIpAddress == "10.0.1.99"


def test_present_description_drift_triggers_update(monkeypatch):
    fake = FakeCfwClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(description="renamed")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Description"] == "renamed"


def test_present_check_mode_update_reports_current(monkeypatch):
    fake = FakeCfwClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(description="renamed", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["Description"] == "app https"
    assert [c[0] for c in fake.calls] == ["DescribeNatFwDnatRule"]


def test_absent_noop_when_rule_missing(monkeypatch):
    fake = FakeCfwClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["rule"] is None
    assert [c[0] for c in fake.calls] == ["DescribeNatFwDnatRule"]


def test_absent_check_mode_delete_reports_current(monkeypatch):
    fake = FakeCfwClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"]["PublicIpAddress"] == "203.0.113.10"
    assert [c[0] for c in fake.calls] == ["DescribeNatFwDnatRule"]


def test_absent_deletes_rule(monkeypatch):
    fake = FakeCfwClient([_rule()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["rule"] is None
    assert [c[0] for c in fake.calls] == [
        "DescribeNatFwDnatRule",
        "DeleteNatFwDnatRule",
    ]
    assert fake.calls[1][1].DnatRules[0].PublicPort == 443
    assert fake.rules == []


def test_sdk_failure_reports_error_payload(monkeypatch):
    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "auth rejected"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"
