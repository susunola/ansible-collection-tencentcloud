"""Deep harness tests for tse_sre_topology_info.

Covers the generic topology request builder, the fetch_all pagination
loop, the nacos/zookeeper engine_type branch, and run_module() end to
end: happy-path replica and interface pagination for both engine
families, empty results, page_size validation and the
sdk_error_payload fail contract.

The module subclasses ``TencentCloudModule``, so the migration patches the
base class's ``create_client`` and the module's own ``_load`` (which is where
it imports its models and client class), and lets ``module_args()`` supply the
credentials the base class validates. The fake items serialise the field the
API really returns for each family: ``Name`` on ``NacosReplica`` /
``ZookeeperReplica`` and ``Interface`` on ``NacosServerInterface`` /
``ZookeeperServerInterface`` (neither model has a generic ``Value``).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_sre_topology_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


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


class FakeReplica:
    def __init__(self, name):
        self.name = name

    def _serialize(self, allow_none=True):
        return {"Name": self.name}


class FakeInterface:
    def __init__(self, interface):
        self.interface = interface

    def _serialize(self, allow_none=True):
        return {"Interface": self.interface}


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


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(tse_sre_topology_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(TseClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def test_run_module_fetches_nacos_topology(monkeypatch):
    client = FakeClient()
    client.pages["nacos_replicas"] = [
        FakeResponse("Replicas", [FakeReplica("r1"), FakeReplica("r2")], 3, "req-nr-1"),
        FakeResponse("Replicas", [FakeReplica("r3")], 3, "req-nr-2"),
    ]
    client.pages["nacos_interfaces"] = [
        FakeResponse("Content", [FakeInterface("i1"), FakeInterface("i2")], 2, "req-ni-1")]
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", instance_id="ins-1", engine_type="nacos", page_size=2)

    payload = run(tse_sre_topology_info.run_module)

    assert payload["changed"] is False
    assert [item["Name"] for item in payload["replicas"]] == ["r1", "r2", "r3"]
    assert [item["Interface"] for item in payload["interfaces"]] == ["i1", "i2"]
    assert payload["replica_count"] == 3 and payload["interface_count"] == 2
    assert payload["request_ids"] == {"replicas": "req-nr-2", "interfaces": "req-ni-1"}
    assert [request.Offset for request in client.requests["nacos_replicas"]] == [0, 2]
    assert client.requests["zk_replicas"] == [] and client.requests["zk_interfaces"] == []


def test_run_module_fetches_zookeeper_topology(monkeypatch):
    client = FakeClient()
    client.pages["zk_replicas"] = [FakeResponse("Replicas", [FakeReplica("r1")], 1, "req-zr-1")]
    client.pages["zk_interfaces"] = [FakeResponse("Content", [FakeInterface("i1")], 1, "req-zi-1")]
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", instance_id="ins-1", engine_type="zookeeper", page_size=2)

    payload = run(tse_sre_topology_info.run_module)

    assert [item["Name"] for item in payload["replicas"]] == ["r1"]
    assert payload["request_ids"] == {"replicas": "req-zr-1", "interfaces": "req-zi-1"}
    assert client.requests["nacos_replicas"] == [] and client.requests["nacos_interfaces"] == []
    assert client.requests["zk_replicas"][0].InstanceId == "ins-1"


def test_run_module_empty_topology_reports_zero_counts(monkeypatch):
    client = FakeClient()
    client.pages["nacos_replicas"] = [FakeResponse("Replicas", [], 0, "req-nr-empty")]
    client.pages["nacos_interfaces"] = [FakeResponse("Content", [], 0, "req-ni-empty")]
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", instance_id="ins-1", engine_type="nacos", page_size=2)

    payload = run(tse_sre_topology_info.run_module)

    assert payload["replicas"] == [] and payload["interfaces"] == []
    assert payload["replica_count"] == 0 and payload["interface_count"] == 0


@pytest.mark.parametrize("page_size,message", [
    (0, "page_size must be between 1 and 100"),
    (101, "page_size must be between 1 and 100"),
])
def test_run_module_validates_page_size_bounds(monkeypatch, page_size, message):
    module_args(region="ap-guangzhou", instance_id="ins-1", engine_type="nacos", page_size=page_size)

    with pytest.raises(AnsibleFailJson) as failure:
        run(tse_sre_topology_info.run_module)

    assert failure.value.args[0]["msg"] == message


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

    _patch_sdk(monkeypatch, FailingClient())
    module_args(region="ap-guangzhou", instance_id="ins-1", engine_type="nacos", page_size=2)

    with pytest.raises(AnsibleFailJson) as failure:
        run(tse_sre_topology_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-err"
