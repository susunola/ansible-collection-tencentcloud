"""Unit tests for the clb_listener write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.tencentcloud.cloud.plugins.modules.clb_listener import (
    build_certificate,
    build_create_request,
    build_describe_request,
    build_health_check,
    find_listener,
    listener_drift,
)


class FakeHealthCheck(object):
    """Mimics the SDK HealthCheck model: zero-arg constructor, attribute assignment."""

    def __init__(self):
        pass


class FakeCertificateInput(object):
    def __init__(self):
        pass


class FakeRequest(object):
    pass


class FakeModels(object):
    HealthCheck = FakeHealthCheck
    CertificateInput = FakeCertificateInput
    DescribeListenersRequest = FakeRequest
    CreateListenerRequest = FakeRequest


class FakeListener(object):
    def __init__(self, listener_id, name, protocol, port, **extra):
        self.ListenerId = listener_id
        self.ListenerName = name
        self.Protocol = protocol
        self.Port = port
        self._extra = extra

    def _serialize(self, allow_none=True):
        data = {
            "ListenerId": self.ListenerId,
            "ListenerName": self.ListenerName,
            "Protocol": self.Protocol,
            "Port": self.Port,
        }
        data.update(self._extra)
        return data


class FakeResponse(object):
    def __init__(self, listeners):
        self.Listeners = listeners


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeListeners(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


def _params(**overrides):
    params = {
        "load_balancer_id": "lb-xxxxxxxx",
        "listener_id": None,
        "port": 8080,
        "protocol": "TCP",
        "name": None,
        "scheduler": None,
        "session_expire_time": None,
        "health_check": None,
        "certificate": None,
        "sni_switch": None,
        "keepalive_enable": None,
    }
    params.update(overrides)
    return params


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, "lb-1", "lbl-1", None, None)
    assert request.LoadBalancerId == "lb-1"
    assert request.ListenerIds == ["lbl-1"]
    assert not hasattr(request, "Port")


def test_build_describe_request_by_port_protocol():
    request = build_describe_request(FakeModels, "lb-1", None, 8080, "TCP")
    assert request.Port == 8080
    assert request.Protocol == "TCP"
    assert not hasattr(request, "ListenerIds")


def test_find_listener_matches_port_and_protocol():
    client = FakeClient(FakeResponse([
        FakeListener("lbl-1", "udp-8080", "UDP", 8080),
        FakeListener("lbl-2", "tcp-8080", "TCP", 8080),
    ]))
    module = FakeModule()
    found = find_listener(module, client, FakeModels, "lb-1", None, 8080, "TCP")
    assert found["ListenerId"] == "lbl-2"


def test_find_listener_returns_none_when_absent():
    client = FakeClient(FakeResponse([]))
    module = FakeModule()
    assert find_listener(module, client, FakeModels, "lb-1", None, 80, "HTTP") is None


def test_build_health_check_maps_fields_and_converts_bool():
    health_check = build_health_check(FakeModels, {
        "health_switch": True,
        "interval_time": 10,
        "check_type": "HTTP",
        "http_check_path": "/healthz",
        "http_check_method": "GET",
    })
    assert health_check.HealthSwitch == 1
    assert health_check.IntervalTime == 10
    assert health_check.CheckType == "HTTP"
    assert health_check.HttpCheckPath == "/healthz"
    assert health_check.HttpCheckMethod == "GET"
    assert not hasattr(health_check, "HttpCode")


def test_build_health_check_none():
    assert build_health_check(FakeModels, None) is None


def test_build_certificate_maps_fields():
    certificate = build_certificate(FakeModels, {
        "ssl_mode": "MUTUAL",
        "cert_id": "cert-1",
        "cert_ca_id": "ca-1",
    })
    assert certificate.SSLMode == "MUTUAL"
    assert certificate.CertId == "cert-1"
    assert certificate.CertCaId == "ca-1"


def test_build_create_request_tcp():
    request = build_create_request(FakeModels, _params(
        name="tcp-8080",
        scheduler="WRR",
        session_expire_time=0,
        health_check={"health_switch": False, "interval_time": 5},
    ))
    assert request.LoadBalancerId == "lb-xxxxxxxx"
    assert request.Ports == [8080]
    assert request.Protocol == "TCP"
    assert request.ListenerNames == ["tcp-8080"]
    assert request.Scheduler == "WRR"
    assert request.SessionExpireTime == 0
    assert request.HealthCheck.HealthSwitch == 0
    assert not hasattr(request, "Certificate")
    assert not hasattr(request, "SniSwitch")


def test_build_create_request_https():
    request = build_create_request(FakeModels, _params(
        protocol="HTTPS",
        port=443,
        certificate={"ssl_mode": "UNIDIRECTIONAL", "cert_id": "abc", "cert_ca_id": None},
        sni_switch=False,
        keepalive_enable=True,
    ))
    assert request.Certificate.CertId == "abc"
    assert not hasattr(request.Certificate, "CertCaId")
    assert request.SniSwitch == 0
    assert request.KeepaliveEnable == 1


def test_listener_drift_detects_changes():
    current = {
        "ListenerName": "old",
        "Scheduler": "WRR",
        "SessionExpireTime": 0,
        "HealthCheck": {"HealthSwitch": 1, "IntervalTime": 5},
        "Certificate": {"CertId": "abc", "SSLMode": "UNIDIRECTIONAL"},
        "SniSwitch": 0,
        "KeepaliveEnable": 0,
    }
    params = _params(
        name="new",
        scheduler="LEAST_CONN",
        session_expire_time=300,
        health_check={"health_switch": False},
        certificate={"cert_id": "xyz"},
        sni_switch=True,
        keepalive_enable=True,
    )
    assert listener_drift(current, params) == [
        "name", "scheduler", "session_expire_time",
        "health_check", "certificate", "sni_switch", "keepalive_enable",
    ]


def test_listener_drift_empty_when_matching():
    current = {
        "ListenerName": "tcp-8080",
        "Scheduler": "WRR",
        "SessionExpireTime": 0,
        "HealthCheck": {"HealthSwitch": 1, "IntervalTime": 5},
        "SniSwitch": 0,
    }
    params = _params(
        name="tcp-8080",
        scheduler="WRR",
        session_expire_time=0,
        health_check={"health_switch": True, "interval_time": 5},
        sni_switch=False,
    )
    assert listener_drift(current, params) == []


def test_listener_drift_ignores_unset_params():
    current = {"ListenerName": "tcp-8080", "Scheduler": "WRR"}
    assert listener_drift(current, _params()) == []


def test_listener_drift_health_check_partial_compare():
    """Only user-provided health_check keys participate in the comparison."""
    current = {"HealthCheck": {"HealthSwitch": 1, "IntervalTime": 5, "HealthNum": 3}}
    assert listener_drift(current, _params(health_check={"interval_time": 5})) == []
    assert listener_drift(current, _params(health_check={"interval_time": 10})) == ["health_check"]
