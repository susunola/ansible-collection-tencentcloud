"""Deep harness tests for tse_sre_topology_info.

Covers the generic topology request builder, the fetch_all pagination
loop, the nacos/zookeeper engine_type branch, and run_module() end to
end: happy-path replica and interface pagination for both engine
families, empty results, page_size validation and the
sdk_error_payload fail contract.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.modules import tse_sre_topology_info


class FakeRequest:
    pass


class FakeModels:
    DescribeNacosReplicasRequest = FakeRequest
    DescribeNacosServerInterfacesRequest = FakeRequest
    DescribeZookeeperReplicasRequest = FakeRequest
    DescribeZookeeperServerInterfacesRequest = FakeRequest


def test_build_request_maps_pagination():
    value = tse_sre_topology_info.build_request(FakeRequest, "ins-1", 20, 10)
    assert value.InstanceId == "ins-1"
    assert value.Offset == 20 and value.Limit == 10


class FakeItem:
    def __init__(self, marker):
        self.marker = marker

    def _serialize(self, allow_none=True):
        return {"Value": self.marker}


class FakeResponse:
    def __init__(self, field, items, total_count, request_id):
        setattr(self, field, items)
        self.TotalCount = total_count
        self.RequestId = request_id


class FakeClient:
    def __init__(self):
        self.pages = {}
        self.requests = {"nacos_replicas": [], "nacos_interfaces": [],
                         "zk_replicas": [], "zk_interfaces": []}

    def _pop(self, key, request):
        self.requests[key].append(request)
        return self.pages[key].pop(0)

    def DescribeNacosReplicas(self, request):
        return self._pop("nacos_replicas", request)

    def DescribeNacosServerInterfaces(self, request):
        return self._pop("nacos_interfaces", request)

    def DescribeZookeeperReplicas(self, request):
        return self._pop("zk_replicas", request)

    def DescribeZookeeperServerInterfaces(self, request):
        return self._pop("zk_interfaces", request)


class ModuleExit(BaseException):
    pass


class ModuleFail(BaseException):
    def __init__(self, payload):
        self.payload = payload
        super(ModuleFail, self).__init__("module failed: %r" % (payload,))


class FakeModule:
    def __init__(self, params):
        self.params = params
        self.exit_payload = None
        self.fail_payload = None

    def require_sdk(self):
        pass

    def create_client(self, client_class, endpoint):
        return self._client

    def sdk_call(self, operation, request=None):
        if request is not None:
            return operation(request)
        return operation()

    def exit_json(self, **kwargs):
        self.exit_payload = kwargs
        raise ModuleExit()

    def fail_json(self, **kwargs):
        self.fail_payload = kwargs
        raise ModuleFail(kwargs)


def _inject_sdk(monkeypatch, client):
    service = types.ModuleType("tencentcloud.tse.v20201207")
    service.models = FakeModels
    service.tse_client = types.SimpleNamespace(TseClient=lambda *args: object())
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.tse",
                        types.ModuleType("tencentcloud.tse"))
    monkeypatch.setitem(sys.modules, "tencentcloud.tse.v20201207", service)


def _run(monkeypatch, client, **params):
    _inject_sdk(monkeypatch, client)
    fake = FakeModule(params)
    fake._client = client
    monkeypatch.setattr(tse_sre_topology_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleExit):
        tse_sre_topology_info.run_module()
    return fake


def _expect_fail(monkeypatch, fake):
    monkeypatch.setattr(tse_sre_topology_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tse_sre_topology_info.run_module()
    return excinfo.value.payload


def test_run_module_fetches_nacos_topology(monkeypatch):
    client = FakeClient()
    client.pages["nacos_replicas"] = [
        FakeResponse("Replicas", [FakeItem("r1"), FakeItem("r2")], 3, "req-nr-1"),
        FakeResponse("Replicas", [FakeItem("r3")], 3, "req-nr-2"),
    ]
    client.pages["nacos_interfaces"] = [
        FakeResponse("Content", [FakeItem("i1"), FakeItem("i2")], 2, "req-ni-1")]
    fake = _run(monkeypatch, client, instance_id="ins-1", engine_type="nacos", page_size=2)
    payload = fake.exit_payload
    assert payload["changed"] is False
    assert [item["Value"] for item in payload["replicas"]] == ["r1", "r2", "r3"]
    assert [item["Value"] for item in payload["interfaces"]] == ["i1", "i2"]
    assert payload["replica_count"] == 3 and payload["interface_count"] == 2
    assert payload["request_ids"] == {"replicas": "req-nr-2", "interfaces": "req-ni-1"}
    assert [request.Offset for request in client.requests["nacos_replicas"]] == [0, 2]
    assert client.requests["zk_replicas"] == [] and client.requests["zk_interfaces"] == []


def test_run_module_fetches_zookeeper_topology(monkeypatch):
    client = FakeClient()
    client.pages["zk_replicas"] = [FakeResponse("Replicas", [FakeItem("r1")], 1, "req-zr-1")]
    client.pages["zk_interfaces"] = [FakeResponse("Content", [FakeItem("i1")], 1, "req-zi-1")]
    fake = _run(monkeypatch, client, instance_id="ins-1", engine_type="zookeeper", page_size=2)
    payload = fake.exit_payload
    assert [item["Value"] for item in payload["replicas"]] == ["r1"]
    assert payload["request_ids"] == {"replicas": "req-zr-1", "interfaces": "req-zi-1"}
    assert client.requests["nacos_replicas"] == [] and client.requests["nacos_interfaces"] == []
    assert client.requests["zk_replicas"][0].InstanceId == "ins-1"


def test_run_module_empty_topology_reports_zero_counts(monkeypatch):
    client = FakeClient()
    client.pages["nacos_replicas"] = [FakeResponse("Replicas", [], 0, "req-nr-empty")]
    client.pages["nacos_interfaces"] = [FakeResponse("Content", [], 0, "req-ni-empty")]
    fake = _run(monkeypatch, client, instance_id="ins-1", engine_type="nacos", page_size=2)
    payload = fake.exit_payload
    assert payload["replicas"] == [] and payload["interfaces"] == []
    assert payload["replica_count"] == 0 and payload["interface_count"] == 0


@pytest.mark.parametrize("page_size,message", [
    (0, "page_size must be between 1 and 100"),
    (101, "page_size must be between 1 and 100"),
])
def test_run_module_validates_page_size_bounds(monkeypatch, page_size, message):
    p = {"instance_id": "ins-1", "engine_type": "nacos", "page_size": page_size}
    payload = _expect_fail(monkeypatch, FakeModule(p))
    assert payload["msg"] == message


class SdkError(Exception):
    def __init__(self, code, request_id):
        self._code = code
        self._request_id = request_id
        super(SdkError, self).__init__("api exploded")

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient(FakeClient):
        def DescribeNacosReplicas(self, request):
            raise SdkError("FailedOperation", "req-err")

    failing = FailingClient()
    _inject_sdk(monkeypatch, failing)
    fake = FakeModule({"instance_id": "ins-1", "engine_type": "nacos", "page_size": 2})
    fake._client = failing
    monkeypatch.setattr(tse_sre_topology_info, "TencentCloudModule", lambda **kwargs: fake)
    with pytest.raises(ModuleFail) as excinfo:
        tse_sre_topology_info.run_module()
    payload = excinfo.value.payload
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
