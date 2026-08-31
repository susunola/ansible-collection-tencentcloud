"""SCF backend contract tests for api_gateway_api."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.modules.api_gateway_api import (
    apply_request,
    comparable,
    desired,
)


class Object(object):
    pass


class Models(object):
    ApiRequestConfig = Object


def params(service_type="SCF"):
    return {
        "service_id": "service-1",
        "name": "orders",
        "description": "Orders API",
        "auth_type": "NONE",
        "service_type": service_type,
        "service_timeout": 20,
        "path": "/orders",
        "method": "POST",
        "enable_cors": True,
        "mock_response": '{"ok":true}',
        "scf_function_name": "order-handler",
        "scf_function_namespace": "default",
        "scf_function_qualifier": "production",
        "scf_function_type": "EVENT",
        "scf_integrated_response": True,
    }


def test_apply_request_sets_typed_scf_backend_fields():
    request = apply_request(Object(), Models, params())
    assert request.ServiceType == "SCF"
    assert request.ServiceScfFunctionName == "order-handler"
    assert request.ServiceScfFunctionNamespace == "default"
    assert request.ServiceScfFunctionQualifier == "production"
    assert request.ServiceScfFunctionType == "EVENT"
    assert request.ServiceScfIsIntegratedResponse is True


def test_scf_desired_and_comparable_have_same_shape():
    expected = desired(params())
    remote = dict(expected)
    remote["RequestConfig"] = {"Path": remote.pop("Path"), "Method": remote.pop("Method")}
    assert comparable(remote) == expected


def test_mock_response_drift_is_compared():
    expected = desired(params("MOCK"))
    assert expected["ServiceMockReturnMessage"] == '{"ok":true}'
    remote = dict(expected)
    remote["ServiceMockReturnMessage"] = "different"
    remote["RequestConfig"] = {"Path": remote.pop("Path"), "Method": remote.pop("Method")}
    assert comparable(remote) != expected
