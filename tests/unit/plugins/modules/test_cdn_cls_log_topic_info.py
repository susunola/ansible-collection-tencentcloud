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

from ansible_collections.susunola.tencentcloud.plugins.modules import cdn_cls_log_topic_info


class FakeRequest:
    pass


class FakeModels:
    ListClsLogTopicsRequest = FakeRequest
    ListClsTopicDomainsRequest = FakeRequest


class FakeResource:
    def __init__(self, value):
        self.value = dict(value)

    def _serialize(self, allow_none=True):
        return dict(self.value)


def test_list_topics_request_sets_channel():
    request = cdn_cls_log_topic_info.list_topics_request(FakeModels, "ecdn")
    assert request.Channel == "ecdn"


def test_list_domains_request_sets_identifiers():
    request = cdn_cls_log_topic_info.list_domains_request(FakeModels, "topic-x", "logset-x", "cdn")
    assert request.TopicId == "topic-x"
    assert request.LogsetId == "logset-x"
    assert request.Channel == "cdn"


def test_topic_candidates_flattens_default_and_extra_logsets():
    response = types.SimpleNamespace(
        Logset=FakeResource({"LogsetId": "logset-a"}),
        Topics=[FakeResource({"TopicId": "topic-a", "TopicName": "a"})],
        ExtraLogset=[
            types.SimpleNamespace(
                Logset=FakeResource({"LogsetId": "logset-b"}),
                Topics=[FakeResource({"TopicId": "topic-b", "TopicName": "b"})],
            )
        ],
    )
    assert cdn_cls_log_topic_info._topic_candidates(response) == [
        {"TopicId": "topic-a", "TopicName": "a", "LogsetId": "logset-a"},
        {"TopicId": "topic-b", "TopicName": "b", "LogsetId": "logset-b"},
    ]


@pytest.mark.parametrize(
    ("item", "topic_id", "topic_name", "logset_id", "expected"),
    [
        ({"TopicId": "topic-x", "TopicName": "name", "LogsetId": "logset-x"}, "topic-x", None, None, True),
        ({"TopicId": "topic-x", "TopicName": "name", "LogsetId": "logset-x"}, None, "name", "logset-x", True),
        ({"TopicId": "topic-x", "TopicName": "name", "LogsetId": "logset-x"}, "topic-y", None, None, False),
        ({"TopicId": "topic-x", "TopicName": "name", "LogsetId": "logset-x"}, None, "other", None, False),
        ({"TopicId": "topic-x", "TopicName": "name", "LogsetId": "logset-x"}, None, None, "logset-y", False),
    ],
)
def test_matches_filters_by_topic_name_and_logset(item, topic_id, topic_name, logset_id, expected):
    assert cdn_cls_log_topic_info._matches(item, topic_id, topic_name, logset_id) is expected


class FakeResponse:
    RequestId = "req-list"

    def __init__(self):
        self.Logset = FakeResource({"LogsetId": "logset-a"})
        self.Topics = [FakeResource({"TopicId": "topic-a", "TopicName": "cdn-access"})]
        self.ExtraLogset = []


class FakeDomainResponse:
    RequestId = "req-domains"
    DomainAreaConfigs = [FakeResource({"Domain": "static.example.com", "Area": ["mainland"]})]
    InheritDomainTags = True


class FakeClient:
    def __init__(self):
        self.requests = []

    def ListClsLogTopics(self, request):
        self.requests.append(("ListClsLogTopics", request))
        return FakeResponse()

    def ListClsTopicDomains(self, request):
        self.requests.append(("ListClsTopicDomains", request))
        return FakeDomainResponse()


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
    service = types.ModuleType("tencentcloud.cdn.v20180606")
    service.models = FakeModels
    service.cdn_client = types.SimpleNamespace(CdnClient=lambda *args: client)
    monkeypatch.setitem(sys.modules, "tencentcloud", types.ModuleType("tencentcloud"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cdn", types.ModuleType("tencentcloud.cdn"))
    monkeypatch.setitem(sys.modules, "tencentcloud.cdn.v20180606", service)


def test_run_module_returns_topic_with_domain_bindings(monkeypatch):
    client = FakeClient()
    _inject_sdk(monkeypatch, client)
    fake = FakeModule({
        "region": "ap-guangzhou",
        "topic_id": None,
        "topic_name": "cdn-access",
        "logset_id": "logset-a",
        "channel": "cdn",
    })
    monkeypatch.setattr(cdn_cls_log_topic_info, "AnsibleModule", lambda **kwargs: fake)
    monkeypatch.setattr(cdn_cls_log_topic_info, "create_credential", lambda module: object())
    monkeypatch.setattr(cdn_cls_log_topic_info, "create_client_profile", lambda module, endpoint: object())
    with pytest.raises(ModuleExit):
        cdn_cls_log_topic_info.run_module()
    assert fake.exit_payload["changed"] is False
    assert fake.exit_payload["topic"]["TopicId"] == "topic-a"
    assert fake.exit_payload["topic"]["DomainAreaConfigs"] == [
        {"Domain": "static.example.com", "Area": ["mainland"]}
    ]
    assert fake.exit_payload["topic"]["InheritDomainTags"] is True
    assert [name for name, request in client.requests] == ["ListClsLogTopics", "ListClsTopicDomains"]
