"""Unit tests for the clb_rule write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.clb_rule import (
    build_describe_request,
    find_rule,
    build_health_check,
    health_check_differs,
    _create,
    _update,
    _delete,
)


class FakeRequest(object):
    pass


class FakeHealthCheck(object):
    def __init__(self):
        self.HealthSwitch = None
        self.HttpCheckPath = None
        self.IntervalTime = None


class FakeRuleInput(object):
    def __init__(self):
        self.Domain = None
        self.Url = None


class FakeModels(object):
    DescribeListenersRequest = FakeRequest
    CreateRuleRequest = FakeRequest
    ModifyRuleRequest = FakeRequest
    DeleteRuleRequest = FakeRequest
    HealthCheck = FakeHealthCheck
    RuleInput = FakeRuleInput


class FakeRule(object):
    def __init__(self, location_id, domain, url, scheduler="WRR"):
        self.LocationId = location_id
        self.Domain = domain
        self.Url = url
        self.Scheduler = scheduler
        self.SessionExpireTime = 300
        self.ForwardType = "TRADITIONAL"
        self.CookieName = None
        self.Http2 = False
        self.HealthCheck = None

    def _serialize(self, allow_none=True):
        return {
            "LocationId": self.LocationId,
            "Domain": self.Domain,
            "Url": self.Url,
            "Scheduler": self.Scheduler,
            "SessionExpireTime": self.SessionExpireTime,
            "ForwardType": self.ForwardType,
            "CookieName": self.CookieName,
            "Http2": self.Http2,
            "HealthCheck": self.HealthCheck,
        }


class FakeListener(object):
    def __init__(self, rules):
        self.Rules = rules
        self.ListenerId = "lbl-1"

    def _serialize(self, allow_none=True):
        return {"ListenerId": self.ListenerId, "Rules": self.Rules}


class FakeListenersResponse(object):
    def __init__(self, listeners):
        self.Listeners = listeners


class FakeCreateResponse(object):
    def __init__(self, location_ids):
        self.LocationIds = location_ids


class FakeClient(object):
    def __init__(self, listeners_response=None, create_response=None, exc=None):
        self.listeners_response = listeners_response
        self.create_response = create_response
        self.exc = exc
        self.calls = []

    def DescribeListeners(self, request):
        self.calls.append(("DescribeListeners", request))
        if self.exc:
            raise self.exc
        return self.listeners_response

    def CreateRule(self, request):
        self.calls.append(("CreateRule", request))
        return self.create_response

    def ModifyRule(self, request):
        self.calls.append(("ModifyRule", request))

    def DeleteRule(self, request):
        self.calls.append(("DeleteRule", request))


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


BASE_PARAMS = {
    "load_balancer_id": "lb-1",
    "listener_id": "lbl-1",
    "location_id": None,
    "domain": "api.example.com",
    "url": "/api",
    "scheduler": None,
    "session_expire_time": None,
    "forward_type": None,
    "http2": False,
    "cookie_name": None,
    "health_check": None,
}


def test_build_describe_request_sends_lb_and_listener():
    request = build_describe_request(FakeModels, "lb-1", "lbl-1")
    assert request.LoadBalancerId == "lb-1"
    assert request.ListenerIds == ["lbl-1"]


def test_find_rule_matches_by_location_id():
    client = FakeClient(FakeListenersResponse([
        FakeListener([FakeRule("loc-2", "old.example.com", "/old"), FakeRule("loc-1", "api.example.com", "/api")]),
    ]))
    module = FakeModule()
    rule = find_rule(module, client, FakeModels, "lb-1", "lbl-1", "loc-1", None, None)
    assert rule["LocationId"] == "loc-1"
    assert len(client.calls) == 1


def test_find_rule_matches_by_domain_and_url():
    client = FakeClient(FakeListenersResponse([
        FakeListener([FakeRule("loc-1", "api.example.com", "/api")]),
    ]))
    module = FakeModule()
    rule = find_rule(module, client, FakeModels, "lb-1", "lbl-1", None, "api.example.com", "/api")
    assert rule["LocationId"] == "loc-1"


def test_find_rule_returns_none_when_absent():
    client = FakeClient(FakeListenersResponse([FakeListener([])]))
    module = FakeModule()
    assert find_rule(module, client, FakeModels, "lb-1", "lbl-1", None, "api.example.com", "/api") is None


def test_find_rule_returns_none_when_no_listener():
    client = FakeClient(FakeListenersResponse([]))
    module = FakeModule()
    assert find_rule(module, client, FakeModels, "lb-1", "lbl-1", "loc-1", None, None) is None


def test_build_health_check_maps_fields():
    model = build_health_check(FakeModels, {"health_switch": True, "http_check_path": "/healthz", "interval_time": 10})
    assert model.HealthSwitch == 1
    assert model.HttpCheckPath == "/healthz"
    assert model.IntervalTime == 10


def test_build_health_check_returns_none_when_empty():
    assert build_health_check(FakeModels, None) is None
    assert build_health_check(FakeModels, {}) is None


def test_health_check_differs_on_changed_field():
    current = {"HealthSwitch": 1, "HttpCheckPath": "/healthz", "IntervalTime": 10}
    assert health_check_differs(current, {"interval_time": 20}) is True
    assert health_check_differs(current, {"interval_time": 10}) is False
    assert health_check_differs(current, {}) is False


def test_create_sends_rule_input():
    client = FakeClient(create_response=FakeCreateResponse(["loc-9"]))
    module = FakeModule()
    created_id = _create(module, client, FakeModels, dict(
        BASE_PARAMS,
        scheduler="WRR",
        session_expire_time=300,
        health_check={"health_switch": True, "http_check_path": "/healthz"},
    ))
    assert created_id == "loc-9"
    request = client.calls[-1][1]
    assert request.LoadBalancerId == "lb-1"
    assert request.ListenerId == "lbl-1"
    rule = request.Rules[0]
    assert rule.Domain == "api.example.com"
    assert rule.Url == "/api"
    assert rule.Scheduler == "WRR"
    assert rule.SessionExpireTime == 300
    assert rule.HealthCheck is not None


def test_create_omits_optional_fields():
    client = FakeClient(create_response=FakeCreateResponse(["loc-9"]))
    module = FakeModule()
    _create(module, client, FakeModels, BASE_PARAMS)
    rule = client.calls[-1][1].Rules[0]
    assert not hasattr(rule, "Scheduler")
    assert not hasattr(rule, "SessionExpireTime")
    assert not hasattr(rule, "Http2")
    assert not hasattr(rule, "HealthCheck")


def test_update_sends_location_and_url():
    client = FakeClient()
    module = FakeModule()
    _update(module, client, FakeModels, dict(BASE_PARAMS, scheduler="LEAST_CONN"), "loc-1")
    request = client.calls[-1][1]
    assert request.LocationId == "loc-1"
    assert request.Url == "/api"
    assert request.Scheduler == "LEAST_CONN"


def test_delete_sends_location_ids():
    client = FakeClient()
    module = FakeModule()
    _delete(module, client, FakeModels, BASE_PARAMS, "loc-1")
    request = client.calls[-1][1]
    assert request.LocationIds == ["loc-1"]
    assert request.Domain == "api.example.com"
    assert request.Url == "/api"
