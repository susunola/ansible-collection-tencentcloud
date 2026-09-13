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

from ansible_collections.susunola.tencentcloud.plugins.modules import cdwdoris_instance_info


class FakeRequest:
    pass


class FakeModels:
    DescribeInstancesRequest = FakeRequest
    DescribeInstanceStateRequest = FakeRequest


class FakeResource:
    def __init__(self, value):
        self.value = dict(value)

    def _serialize(self, allow_none=True):
        return dict(self.value)


def test_build_list_request_prefers_instance_id_over_name():
    request = cdwdoris_instance_info.build_list_request(FakeModels, "cdwdoris-x", "ignored", 20, 10)
    assert request.SearchInstanceId == "cdwdoris-x"
    assert request.SearchInstanceName is None
    assert request.Offset == 20
    assert request.Limit == 10


def test_build_state_request_sets_instance_id():
    request = cdwdoris_instance_info.build_state_request(FakeModels, "cdwdoris-x")
    assert request.InstanceId == "cdwdoris-x"


@pytest.mark.parametrize(
    ("item", "instance_id", "name", "expected"),
    [
        ({"InstanceId": "cdwdoris-x", "InstanceName": "analytics"}, "cdwdoris-x", None, True),
        ({"InstanceId": "cdwdoris-x", "InstanceName": "analytics"}, None, "analytics", True),
        ({"InstanceId": "cdwdoris-x", "InstanceName": "analytics"}, "other", None, False),
        ({"InstanceId": "cdwdoris-x", "InstanceName": "analytics"}, None, "other", False),
    ],
)
def test_matches_filters_by_id_or_name(item, instance_id, name, expected):
    assert cdwdoris_instance_info._matches(item, instance_id, name) is expected


class FakeClient:
    def __init__(self):
        self.requests = []

    def DescribeInstances(self, request):
        self.requests.append(("DescribeInstances", request))
        return types.SimpleNamespace(
            InstancesList=[
                FakeResource({"InstanceId": "cdwdoris-x", "InstanceName": "analytics"}),
                FakeResource({"InstanceId": "cdwdoris-y", "InstanceName": "dev"}),
            ],
            TotalCount=2,
            RequestId="req-list",
        )

    def DescribeInstanceState(self, request):
        self.requests.append(("DescribeInstanceState", request))
        return types.SimpleNamespace(InstanceState="Serving", FlowMsg="", RequestId="req-state")


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
    service = types.ModuleType("tencentcloud.cdwdoris.v20211228")
    service.models = FakeModels
    service.cdwdoris_client = types.SimpleNamespace(CdwdorisClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cdwdoris", types.ModuleType("tencentcloud.cdwdoris"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cdwdoris.v20211228", service)


def test_run_module_returns_selected_instance_with_state(monkeypatch):
    client = FakeClient()
    _inject_sdk(monkeypatch, client)
    fake = FakeModule({
        "region": "ap-guangzhou",
        "instance_id": None,
        "name": "analytics",
        "include_state": True,
        "page_size": 100,
    })
    monkeypatch.setattr(cdwdoris_instance_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(cdwdoris_instance_info, "create_credential", lambda module: object())
    monkeypatch.setattr(cdwdoris_instance_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        cdwdoris_instance_info.run_module()
    assert fake.exit_payload["changed"] is False
    assert fake.exit_payload["instance"]["InstanceId"] == "cdwdoris-x"
    assert fake.exit_payload["instance"]["InstanceState"] == "Serving"
    assert [name for name, request in client.requests] == ["DescribeInstances", "DescribeInstanceState"]
