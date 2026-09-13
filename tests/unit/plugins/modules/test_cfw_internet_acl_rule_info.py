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

from ansible_collections.susunola.tencentcloud.plugins.modules import cfw_internet_acl_rule_info


class FakeRequest:
    pass


class FakeModels:
    DescribeAclRuleRequest = FakeRequest


class FakeResource:
    def __init__(self, value):
        self.value = dict(value)

    def _serialize(self, allow_none=True):
        return dict(self.value)


def test_build_request_sets_pagination():
    request = cfw_internet_acl_rule_info.build_request(FakeModels, 100, 50)
    assert request.Offset == 100
    assert request.Limit == 50


@pytest.mark.parametrize(
    ("item", "rule_uuid", "description", "expected"),
    [
        ({"Uuid": 1, "Description": "allow"}, 1, None, True),
        ({"Uuid": 1, "Description": "allow"}, None, "allow", True),
        ({"Uuid": 1, "Description": "allow"}, 2, None, False),
        ({"Uuid": 1, "Description": "allow"}, None, "deny", False),
    ],
)
def test_matches_filters_by_uuid_or_description(item, rule_uuid, description, expected):
    assert cfw_internet_acl_rule_info._matches(item, rule_uuid, description) is expected


class FakeClient:
    def __init__(self):
        self.requests = []

    def DescribeAclRule(self, request):
        self.requests.append(request)
        return types.SimpleNamespace(
            Data=[FakeResource({"Uuid": 7, "Description": "allow-web"})],
            Total=1,
            RequestId="req-acl",
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


def test_run_module_returns_selected_rule(monkeypatch):
    client = FakeClient()
    service = types.ModuleType("tencentcloud.cfw.v20190904")
    service.models = FakeModels
    service.cfw_client = types.SimpleNamespace(CfwClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cfw", types.ModuleType("tencentcloud.cfw"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cfw.v20190904", service)
    fake = FakeModule({"region": "ap-guangzhou", "rule_uuid": None, "description": "allow-web", "page_size": 100})
    monkeypatch.setattr(cfw_internet_acl_rule_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(cfw_internet_acl_rule_info, "create_credential", lambda module: object())
    monkeypatch.setattr(cfw_internet_acl_rule_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        cfw_internet_acl_rule_info.run_module()
    assert fake.exit_payload["changed"] is False
    assert fake.exit_payload["rule"] == {"Uuid": 7, "Description": "allow-web"}
    assert fake.exit_payload["total_count"] == 1
