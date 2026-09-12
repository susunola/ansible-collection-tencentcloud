from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
import types

import pytest

basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)

from ansible_collections.susunola.tencentcloud.plugins.modules import cdwch_instance_info


class FakeRequest:
    pass


class FakeModels:
    DescribeInstancesNewRequest = FakeRequest
    DescribeInstanceRequest = FakeRequest


class FakeResource:
    def __init__(self, value):
        self.value = dict(value)

    def _serialize(self, allow_none=True):
        return dict(self.value)


def test_build_list_request_sets_search_fields():
    request = cdwch_instance_info.build_list_request(FakeModels, "cdwch-x", "ignored", 100, 50)
    assert request.Offset == 100
    assert request.Limit == 50
    assert request.IsSimple is False
    assert request.SearchInstanceId == "cdwch-x"
    assert request.SearchInstanceName is None


def test_build_detail_request_sets_openapi_flag():
    request = cdwch_instance_info.build_detail_request(FakeModels, "cdwch-x")
    assert request.InstanceId == "cdwch-x"
    assert request.IsOpenApi is True


@pytest.mark.parametrize(
    ("item", "instance_id", "name", "expected"),
    [
        ({"InstanceId": "cdwch-x", "InstanceName": "prod"}, "cdwch-x", None, True),
        ({"InstanceId": "cdwch-x", "InstanceName": "prod"}, None, "prod", True),
        ({"InstanceId": "cdwch-x", "InstanceName": "prod"}, "cdwch-y", None, False),
        ({"InstanceId": "cdwch-x", "InstanceName": "prod"}, None, "dev", False),
    ],
)
def test_matches_filters_by_id_or_name(item, instance_id, name, expected):
    assert cdwch_instance_info._matches(item, instance_id, name) is expected


class FakeClient:
    def __init__(self):
        self.requests = []

    def DescribeInstancesNew(self, request):
        self.requests.append(("DescribeInstancesNew", request))
        return types.SimpleNamespace(
            InstancesList=[
                FakeResource({"InstanceId": "cdwch-x", "InstanceName": "prod"}),
                FakeResource({"InstanceId": "cdwch-y", "InstanceName": "dev"}),
            ],
            TotalCount=2,
            RequestId="req-list",
        )

    def DescribeInstance(self, request):
        self.requests.append(("DescribeInstance", request))
        return types.SimpleNamespace(
            InstanceInfo=FakeResource({"InstanceId": request.InstanceId, "Status": "Serving"}),
            RequestId="req-detail",
        )


class ModuleExit(Exception):
    pass


class FakeModule:
    def __init__(self, params):
        self.params = params
        self.exit_payload = None

    def exit_json(self, **kwargs):
        self.exit_payload = kwargs
        raise ModuleExit()

    def fail_json(self, **kwargs):
        raise AssertionError(kwargs)


def _inject_sdk(monkeypatch, client):
    service = types.ModuleType("tencentcloud.cdwch.v20200915")
    service.models = FakeModels
    service.cdwch_client = types.SimpleNamespace(CdwchClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cdwch", types.ModuleType("tencentcloud.cdwch"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cdwch.v20200915", service)


def test_run_module_returns_selected_instance_with_detail(monkeypatch):
    client = FakeClient()
    _inject_sdk(monkeypatch, client)
    fake = FakeModule({"region": "ap-guangzhou", "instance_id": None, "name": "prod", "page_size": 100})
    monkeypatch.setattr(cdwch_instance_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(cdwch_instance_info, "create_credential", lambda module: object())
    monkeypatch.setattr(cdwch_instance_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        cdwch_instance_info.run_module()
    assert fake.exit_payload["changed"] is False
    assert fake.exit_payload["total_count"] == 2
    assert fake.exit_payload["instance"] == {"InstanceId": "cdwch-x", "InstanceName": "prod", "Status": "Serving"}
    assert [name for name, request in client.requests] == ["DescribeInstancesNew", "DescribeInstance"]
