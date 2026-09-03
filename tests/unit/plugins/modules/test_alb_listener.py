"""Unit tests for the alb_listener write module (helpers + run_module).

Covers the create / drift-update / delete flows of
``plugins/modules/alb_listener.py`` with an in-memory fake ALB client whose
write operations mutate the listener store, so the module's post-write
``find`` refetch converges immediately. Listeners are matched by
``listener_id`` or by the (port, protocol) pair; both lookup paths are
exercised along with the multiple-match guard, the immutable
port/protocol check, the creation-parameter requirement and check-mode
dry runs.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import alb_listener as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

LISTENER = {
    "ListenerId": "lbl-8b0a1c2d",
    "LoadBalancerId": "alb-8b0a1c2d",
    "ListenerName": "https-prod",
    "ListenerPort": 443,
    "ListenerProtocol": "HTTPS",
    "DefaultActions": [
        {
            "Type": "ForwardGroup",
            "TargetGroupConfig": {
                "TargetGroups": [{"TargetGroupId": "alb-tg-8b0a1c2d", "Weight": 100}]
            },
        }
    ],
    "CertificateIds": [],
    "CaEnabled": False,
    "CaCertificateIds": [],
    "SecurityPolicyId": None,
    "GzipEnabled": True,
    "Http2Enabled": None,
    "IdleTimeout": 15,
    "RequestTimeout": 60,
    "XForwardedForConfig": None,
    "Tags": [],
}


def _listener(**overrides):
    """Return a listener fixture isolated from the shared constant."""
    item = copy.deepcopy(LISTENER)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base included).

    NOTE: ``protocol`` carries choices but no default. Ansible only validates
    choices for keys the user explicitly passed, so omitted (absent) keys are
    safe but an explicit ``None`` is rejected. Tests therefore never pre-fill
    ``protocol``; pass a concrete value (``"HTTP"``/``"HTTPS"``/``"QUIC"``)
    when a scenario needs it.
    """
    params = {
        "state": "present",
        "load_balancer_id": "alb-8b0a1c2d",
        "listener_id": None,
        "name": None,
        "port": None,
        "default_actions": None,
        "certificate_ids": None,
        "ca_enabled": False,
        "ca_certificate_ids": None,
        "security_policy_id": None,
        "gzip_enabled": True,
        "http2_enabled": None,
        "idle_timeout": 15,
        "request_timeout": 60,
        "x_forwarded_for": None,
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


def _plain(value):
    """Convert a fake SDK model back to plain data for the store."""
    if value is None:
        return None
    if hasattr(value, "_value"):  # _JsonModel round-trippable payload
        return value._value
    if hasattr(value, "to_json_string"):
        return json.loads(value.to_json_string())
    if hasattr(value, "__dict__"):  # TagInfo / FakeRequest attribute bag
        return {k: _plain(v) for k, v in vars(value).items() if not k.startswith("_")}
    return value


def _plain_list(values):
    return [_plain(v) for v in (values or [])]


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


class FakeAlbClient(object):
    """In-memory ALB client that mutates a small listener store."""

    def __init__(self, listeners=None):
        self.listeners = [copy.deepcopy(t) for t in (listeners or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeListeners(self, request):
        self._record("DescribeListeners", request)
        return SimpleNamespace(Listeners=[FakeResource(dict(t)) for t in self.listeners])

    def DescribeListenerDetail(self, request):
        self._record("DescribeListenerDetail", request)
        for item in self.listeners:
            if item.get("ListenerId") == request.ListenerId:
                return FakeResource(dict(item, RequestId="req-fake"))
        return FakeResource({"RequestId": "req-fake"})

    def CreateListener(self, request):
        self._record("CreateListener", request)
        self._next += 1
        item = {
            "ListenerId": "lbl-fake-%03d" % self._next,
            "LoadBalancerId": request.LoadBalancerId,
            "ListenerName": request.ListenerName,
            "ListenerPort": request.ListenerPort,
            "ListenerProtocol": request.ListenerProtocol,
            "DefaultActions": _plain_list(request.DefaultActions),
            "CertificateIds": list(request.CertificateIds or []),
            "CaEnabled": request.CaEnabled,
            "CaCertificateIds": list(request.CaCertificateIds or []),
            "SecurityPolicyId": _plain(request.SecurityPolicyId),
            "GzipEnabled": request.GzipEnabled,
            "Http2Enabled": _plain(request.Http2Enabled),
            "IdleTimeout": request.IdleTimeout,
            "RequestTimeout": request.RequestTimeout,
            "XForwardedForConfig": _plain(request.XForwardedForConfig),
            "Tags": _plain_list(request.Tags),
        }
        self.listeners.append(item)
        return SimpleNamespace(ListenerId=item["ListenerId"], RequestId="req-fake")

    def ModifyListenerAttributes(self, request):
        self._record("ModifyListenerAttributes", request)
        for item in self.listeners:
            if item.get("ListenerId") == request.ListenerId:
                if getattr(request, "ListenerName", None) is not None:
                    item["ListenerName"] = request.ListenerName
                if getattr(request, "DefaultActions", None) is not None:
                    item["DefaultActions"] = _plain_list(request.DefaultActions)
                if getattr(request, "CertificateIds", None) is not None:
                    item["CertificateIds"] = list(request.CertificateIds)
                if getattr(request, "CaEnabled", None) is not None:
                    item["CaEnabled"] = request.CaEnabled
                if getattr(request, "CaCertificateIds", None) is not None:
                    item["CaCertificateIds"] = list(request.CaCertificateIds)
                if getattr(request, "SecurityPolicyId", None) is not None:
                    item["SecurityPolicyId"] = request.SecurityPolicyId
                if getattr(request, "GzipEnabled", None) is not None:
                    item["GzipEnabled"] = request.GzipEnabled
                if getattr(request, "Http2Enabled", None) is not None:
                    item["Http2Enabled"] = request.Http2Enabled
                if getattr(request, "IdleTimeout", None) is not None:
                    item["IdleTimeout"] = request.IdleTimeout
                if getattr(request, "RequestTimeout", None) is not None:
                    item["RequestTimeout"] = request.RequestTimeout
                if getattr(request, "XForwardedForConfig", None) is not None:
                    item["XForwardedForConfig"] = _plain(request.XForwardedForConfig)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteListener(self, request):
        self._record("DeleteListener", request)
        ids = list(request.ListenerIds or [])
        self.listeners = [t for t in self.listeners if t.get("ListenerId") not in ids]
        return SimpleNamespace(RequestId="req-fake")


class _JsonModel(object):
    """Stand-in for SDK payload models built via json round-trip.

    ``_model()`` builds ``cls()`` then calls ``from_json_string``, so the
    fake models used for DefaultAction / XForwardedForConfig must implement
    it (FakeModels' dynamic classes only support free attribute assignment).
    """

    def __init__(self):
        self._value = None

    def from_json_string(self, text):
        self._value = json.loads(text)

    def to_json_string(self):
        return json.dumps(self._value)


class FakeAlbModels(FakeModels):
    """FakeModels whose payload models resolve to round-trippable classes."""

    _json_models = ("DefaultAction", "XForwardedForConfig")

    def __getattr__(self, name):
        if name in self._json_models:
            return _JsonModel
        return super(FakeAlbModels, self).__getattr__(name)


def _make_module(monkeypatch, fake, params=None):
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
    assert mod._model(FakeAlbModels().DefaultAction, None) is None


def test_model_round_trips_payload():
    payload = {"Type": "ForwardGroup", "Value": "x"}
    obj = mod._model(FakeAlbModels().DefaultAction, payload)
    assert obj.to_json_string() == json.dumps(payload)


def test_tags_sorted_and_built():
    tags = mod._tags(FakeAlbModels(), {"zebra": "1", "alpha": "2"})
    assert [(t.TagKey, t.TagValue) for t in tags] == [("alpha", "2"), ("zebra", "1")]


def test_tags_none_yields_empty():
    assert mod._tags(FakeAlbModels(), None) == []


def test_list_request_with_listener_id():
    request = mod.list_request(FakeAlbModels(), _params(listener_id="lbl-abc"))
    assert request.LoadBalancerId == "alb-8b0a1c2d"
    assert request.MaxResults == 100
    assert request.ListenerIds == ["lbl-abc"]


def test_list_request_without_listener_id():
    request = mod.list_request(FakeAlbModels(), _params(port=443, protocol="HTTPS"))
    assert request.LoadBalancerId == "alb-8b0a1c2d"
    assert getattr(request, "ListenerIds", None) is None


def test_describe_request_fields():
    request = mod.describe_request(FakeAlbModels(), _params(), "lbl-abc")
    assert request.LoadBalancerId == "alb-8b0a1c2d"
    assert request.ListenerId == "lbl-abc"


def test_fill_populates_attributes():
    models = FakeAlbModels()
    p = _params(
        name="https-prod",
        default_actions=[{"Type": "ForwardGroup", "Value": "x"}],
        certificate_ids=["cert-1", "cert-2"],
        ca_enabled=True,
        ca_certificate_ids=["cert-ca"],
        security_policy_id="sp-1",
        gzip_enabled=False,
        http2_enabled=True,
        idle_timeout=30,
        request_timeout=90,
        x_forwarded_for={"Type": "Mode", "Value": "FALSE"},
        client_token="tok-1",
    )
    request = mod._fill(models.CreateListenerRequest(), models, p)
    assert request.ListenerName == "https-prod"
    assert request.CertificateIds == ["cert-1", "cert-2"]
    assert request.CaEnabled is True
    assert request.CaCertificateIds == ["cert-ca"]
    assert request.GzipEnabled is False
    assert request.Http2Enabled is True
    assert request.IdleTimeout == 30
    assert request.RequestTimeout == 90
    assert request.SecurityPolicyId == "sp-1"
    assert request.ClientToken == "tok-1"
    assert request.DefaultActions[0].to_json_string() == json.dumps({"Type": "ForwardGroup", "Value": "x"})
    assert request.XForwardedForConfig.to_json_string() == json.dumps({"Type": "Mode", "Value": "FALSE"})


def test_fill_defaults_with_omitted_optional_fields():
    models = FakeAlbModels()
    request = mod._fill(models.CreateListenerRequest(), models, _params())
    assert request.CaEnabled is False
    assert request.GzipEnabled is True
    assert request.IdleTimeout == 15
    assert request.RequestTimeout == 60
    assert request.DefaultActions == []
    assert request.XForwardedForConfig is None
    assert request.ClientToken is None


def test_create_request_adds_port_protocol_tags():
    models = FakeAlbModels()
    p = _params(port=443, protocol="HTTPS", tags={"b": "2", "a": "1"})
    request = mod.create_request(models, p)
    assert request.ListenerPort == 443
    assert request.ListenerProtocol == "HTTPS"
    assert request.LoadBalancerId == "alb-8b0a1c2d"
    assert [(t.TagKey, t.TagValue) for t in request.Tags] == [("a", "1"), ("b", "2")]


def test_update_request_adds_ids():
    models = FakeAlbModels()
    request = mod.update_request(models, _params(), "lbl-abc")
    assert request.ListenerId == "lbl-abc"
    assert request.LoadBalancerId == "alb-8b0a1c2d"


def test_delete_request_fields():
    request = mod.delete_request(FakeAlbModels(), _params(client_token="tok-d"), "lbl-abc")
    assert request.LoadBalancerId == "alb-8b0a1c2d"
    assert request.ListenerIds == ["lbl-abc"]
    assert request.ClientToken == "tok-d"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeAlbClient()
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(port=8080, protocol="HTTP"))
    assert mod.find(module, fake, FakeAlbModels(), module.params) is None


def test_find_matches_by_listener_id(monkeypatch):
    fake = FakeAlbClient([_listener()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(listener_id="lbl-8b0a1c2d"))
    value = mod.find(module, fake, FakeAlbModels(), module.params)
    assert value["ListenerName"] == "https-prod"
    assert "RequestId" not in value  # detail envelope is popped


def test_find_matches_by_port_and_protocol(monkeypatch):
    fake = FakeAlbClient([_listener()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(port=443, protocol="HTTPS"))
    value = mod.find(module, fake, FakeAlbModels(), module.params)
    assert value["ListenerId"] == "lbl-8b0a1c2d"


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeAlbClient(
        [
            _listener(ListenerId="lbl-1", ListenerName="a"),
            _listener(ListenerId="lbl-2", ListenerName="b"),
        ]
    )
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(port=443, protocol="HTTPS"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeAlbModels(), module.params)
    assert "Multiple ALB listeners matched" in exc.value.args[0]["msg"]


def test_comparable_picks_and_normalizes_fields():
    value = mod.comparable(_listener(CertificateIds=["cert-2", "cert-1"], CaEnabled=0))
    assert value["ListenerName"] == "https-prod"
    assert value["ListenerPort"] == 443
    assert value["CertificateIds"] == ["cert-1", "cert-2"]
    assert value["CaCertificateIds"] == []
    assert value["CaEnabled"] is False
    assert value["GzipEnabled"] is True
    assert value["DefaultActions"][0]["Type"] == "ForwardGroup"


def test_comparable_missing_fields_are_lenient():
    value = mod.comparable({})
    assert value["CertificateIds"] == []
    assert value["CaEnabled"] is False
    assert value["GzipEnabled"] is False
    assert value["DefaultActions"] == []


def test_desired_new_resource_uses_params_and_defaults():
    p = _params(
        name="https-prod",
        port=443,
        protocol="HTTPS",
        default_actions=[{"Type": "ForwardGroup", "Value": "x"}],
        certificate_ids=["cert-2", "cert-1"],
        http2_enabled=True,
        security_policy_id="sp-1",
        x_forwarded_for={"Type": "Mode", "Value": "FALSE"},
    )
    target = mod.desired(p)
    assert target["ListenerName"] == "https-prod"
    assert target["ListenerPort"] == 443
    assert target["ListenerProtocol"] == "HTTPS"
    assert target["CertificateIds"] == ["cert-1", "cert-2"]
    assert target["CaEnabled"] is False
    assert target["GzipEnabled"] is True
    assert target["IdleTimeout"] == 15
    assert target["RequestTimeout"] == 60
    assert target["Http2Enabled"] is True
    assert target["XForwardedForConfig"] == {"Type": "Mode", "Value": "FALSE"}


def test_desired_keeps_current_when_param_omitted():
    # desired() receives the RAW find() dict and comparable()s it internally;
    # passing a pre-comparabled dict would double-process nested resources.
    current = _listener(
        ListenerName="https-prod",
        CertificateIds=["cert-1"],
        CaCertificateIds=["cert-ca"],
        SecurityPolicyId="sp-1",
        Http2Enabled=True,
        XForwardedForConfig={"Type": "Mode", "Value": "FALSE"},
    )
    target = mod.desired(_params(name="https-prod"), current)
    assert target["ListenerName"] == "https-prod"
    assert target["CertificateIds"] == ["cert-1"]  # inherited when omitted
    assert target["CaCertificateIds"] == ["cert-ca"]
    assert target["SecurityPolicyId"] == "sp-1"
    assert target["Http2Enabled"] is True
    assert target["XForwardedForConfig"] == {"Type": "Mode", "Value": "FALSE"}


def test_desired_explicit_params_override_current():
    current = _listener(ListenerName="https-prod", CertificateIds=["cert-1"])
    target = mod.desired(_params(name="https-v2", certificate_ids=["cert-9"]), current)
    assert target["ListenerName"] == "https-v2"
    assert target["CertificateIds"] == ["cert-9"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_load_balancer_enforced(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    module_args()
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_required_one_of_listener_id_or_port_enforced(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    # The harness pre-fills every parameter with None and ansible-core counts
    # a present-but-None value as provided, so required_one_of does not fire;
    # route the SDK calls at a failing fake client instead of the network.
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
    _run_args(load_balancer_id="alb-8b0a1c2d")
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_ca_enabled_requires_ca_certificate_ids(monkeypatch):
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
    _run_args(load_balancer_id="alb-8b0a1c2d", listener_id="lbl-8b0a1c2d", ca_enabled=True)
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
    _run_args(listener_id="lbl-8b0a1c2d")
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


def test_present_creates_listener(monkeypatch):
    fake = FakeAlbClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", load_balancer_id="alb-8b0a1c2d", name="https-prod",
                port=443, protocol="HTTPS",
                default_actions=[{"Type": "ForwardGroup", "Value": "x"}])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["listener"]["ListenerId"] == "lbl-fake-001"
    assert result["listener"]["ListenerName"] == "https-prod"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeListeners") == 2  # initial find + refetch
    assert "DescribeListenerDetail" in names
    assert names.count("CreateListener") == 1
    assert not any("ModifyListenerAttributes" == n for n in names)


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeAlbClient([_listener()])
    _make_module(monkeypatch, fake)
    module_args(state="present", load_balancer_id="alb-8b0a1c2d", listener_id="lbl-8b0a1c2d",
                name="https-prod", port=443, protocol="HTTPS",
                default_actions=[{"Type": "ForwardGroup",
                                  "TargetGroupConfig": {"TargetGroups": [{"TargetGroupId": "alb-tg-8b0a1c2d", "Weight": 100}]}}])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["listener"]["ListenerId"] == "lbl-8b0a1c2d"
    names = [c[0] for c in fake.calls]
    assert "CreateListener" not in names
    assert "ModifyListenerAttributes" not in names


def test_present_drift_triggers_update(monkeypatch):
    fake = FakeAlbClient([_listener()])
    _make_module(monkeypatch, fake)
    module_args(state="present", load_balancer_id="alb-8b0a1c2d", listener_id="lbl-8b0a1c2d",
                name="https-v2", port=443, protocol="HTTPS",
                default_actions=[{"Type": "ForwardGroup",
                                  "TargetGroupConfig": {"TargetGroups": [{"TargetGroupId": "alb-tg-8b0a1c2d", "Weight": 100}]}}])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["listener"]["ListenerName"] == "https-v2"
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyListenerAttributes") == 1
    assert "CreateListener" not in names


def test_present_missing_creation_params_fails(monkeypatch):
    fake = FakeAlbClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", load_balancer_id="alb-8b0a1c2d", port=443, protocol="HTTPS")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert sorted(payload["missing"]) == ["default_actions", "name"]


def test_present_multiple_matches_fails(monkeypatch):
    fake = FakeAlbClient(
        [
            _listener(ListenerId="lbl-1", ListenerName="a"),
            _listener(ListenerId="lbl-2", ListenerName="b"),
        ]
    )
    _make_module(monkeypatch, fake)
    module_args(state="present", load_balancer_id="alb-8b0a1c2d", port=443, protocol="HTTPS",
                name="a", default_actions=[{"Type": "ForwardGroup", "Value": "x"}])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple ALB listeners matched" in exc.value.args[0]["msg"]


def test_present_immutable_port_change_fails(monkeypatch):
    fake = FakeAlbClient([_listener()])
    _make_module(monkeypatch, fake)
    module_args(state="present", load_balancer_id="alb-8b0a1c2d", listener_id="lbl-8b0a1c2d",
                name="https-prod", port=8443, protocol="HTTPS",
                default_actions=[{"Type": "ForwardGroup",
                                  "TargetGroupConfig": {"TargetGroups": [{"TargetGroupId": "alb-tg-8b0a1c2d", "Weight": 100}]}}])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["immutable_changes"]["ListenerPort"] == {"before": 443, "after": 8443}
    assert any("ModifyListenerAttributes" == c[0] for c in fake.calls) is False


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeAlbClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="present", load_balancer_id="alb-8b0a1c2d",
                name="https-prod", port=443, protocol="HTTPS",
                default_actions=[{"Type": "ForwardGroup", "Value": "x"}])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["listener"]["ListenerName"] == "https-prod"  # target payload
    names = [c[0] for c in fake.calls]
    assert "CreateListener" not in names
    assert names.count("DescribeListeners") == 1  # no refetch in check mode


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeAlbClient([_listener()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="present", load_balancer_id="alb-8b0a1c2d",
                listener_id="lbl-8b0a1c2d", name="https-v2", port=443, protocol="HTTPS",
                default_actions=[{"Type": "ForwardGroup",
                                  "TargetGroupConfig": {"TargetGroups": [{"TargetGroupId": "alb-tg-8b0a1c2d", "Weight": 100}]}}])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["listener"]["ListenerName"] == "https-v2"
    assert not any("ModifyListenerAttributes" == c[0] for c in fake.calls)


def test_absent_removes_listener(monkeypatch):
    fake = FakeAlbClient([_listener()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", load_balancer_id="alb-8b0a1c2d", listener_id="lbl-8b0a1c2d")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["listener"] is None
    names = [c[0] for c in fake.calls]
    assert names.count("DeleteListener") == 1
    assert fake.listeners == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeAlbClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", load_balancer_id="alb-8b0a1c2d", port=443)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["listener"] is None
    assert not any("DeleteListener" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeAlbClient([_listener()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", load_balancer_id="alb-8b0a1c2d",
                listener_id="lbl-8b0a1c2d")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["listener"] is None
    assert not any("DeleteListener" == c[0] for c in fake.calls)
    assert len(fake.listeners) == 1
