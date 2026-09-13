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

from ansible_collections.susunola.tencentcloud.plugins.modules import cdwpg_instance_info


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
    request = cdwpg_instance_info.build_list_request(FakeModels, "cdwpg-x", "ignored", 20, 10)
    assert request.SearchInstanceId == "cdwpg-x"
    assert request.SearchInstanceName is None
    assert request.Offset == 20
    assert request.Limit == 10


def test_instance_id_accepts_legacy_capitalization():
    assert cdwpg_instance_info._instance_id({"InstanceID": "cdwpg-x"}) == "cdwpg-x"


@pytest.mark.parametrize(
    ("item", "instance_id", "name", "expected"),
    [
        ({"InstanceID": "cdwpg-x", "InstanceName": "analytics"}, "cdwpg-x", None, True),
        ({"InstanceId": "cdwpg-x", "InstanceName": "analytics"}, None, "analytics", True),
        ({"InstanceID": "cdwpg-x", "InstanceName": "analytics"}, "other", None, False),
        ({"InstanceId": "cdwpg-x", "InstanceName": "analytics"}, None, "other", False),
    ],
)
def test_matches_filters_by_id_or_name(item, instance_id, name, expected):
    assert cdwpg_instance_info._matches(item, instance_id, name) is expected


class FakeClient:
    def __init__(self):
        self.requests = []

    def DescribeInstances(self, request):
        self.requests.append(("DescribeInstances", request))
        return types.SimpleNamespace(
            InstancesList=[
                FakeResource({"InstanceID": "cdwpg-x", "InstanceName": "analytics"}),
                FakeResource({"InstanceID": "cdwpg-y", "InstanceName": "dev"}),
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
    service = types.ModuleType("tencentcloud.cdwpg.v20201230")
    service.models = FakeModels
    service.cdwpg_client = types.SimpleNamespace(CdwpgClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cdwpg", types.ModuleType("tencentcloud.cdwpg"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cdwpg.v20201230", service)


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
    monkeypatch.setattr(cdwpg_instance_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(cdwpg_instance_info, "create_credential", lambda module: object())
    monkeypatch.setattr(cdwpg_instance_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        cdwpg_instance_info.run_module()
    assert fake.exit_payload["changed"] is False
    assert fake.exit_payload["instance"]["InstanceID"] == "cdwpg-x"
    assert fake.exit_payload["instance"]["InstanceState"] == "Serving"
    assert [name for name, request in client.requests] == ["DescribeInstances", "DescribeInstanceState"]
