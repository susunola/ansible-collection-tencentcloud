"""Unit tests for the cdn_cls_log_topic write module (roadmap #57 lever 1).

Hand-finished after scripts/generate_module_test_skeleton.py: covers the
ListClsLogTopics response grouping, every request builder, the domain-area
normalizer, the finder, and all present/absent/check-mode/force_replace
reconcile paths.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cdn_cls_log_topic as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TOPIC = {
    "TopicId": "topic-8b0a1c2d",
    "TopicName": "cdn-access",
    "LogsetId": "logset-8b0a1c2d",
    "Enabled": True,
    "InheritDomainTags": True,
    "DomainAreaConfigs": [
        {"Domain": "static.example.com", "Area": ["mainland"]},
        {"Domain": "global.example.com", "Area": ["overseas"]},
    ],
}

WRITE_OPS = (
    "CreateClsLogTopic",
    "ManageClsTopicDomains",
    "EnableClsLogTopic",
    "DisableClsLogTopic",
    "DeleteClsLogTopic",
)


def _topic(**overrides):
    """Return a topic fixture isolated from the shared constant."""
    topic = copy.deepcopy(TOPIC)
    topic.update(overrides)
    return topic


def _config(domain, areas):
    """Module-side domain area config (parameter shape)."""
    return {"domain": domain, "areas": list(areas)}


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base params included)."""
    params = {
        "state": "present",
        "topic_id": None,
        "topic_name": None,
        "logset_id": None,
        "channel": "cdn",
        "enabled": True,
        "domain_area_configs": [],
        "inherit_domain_tags": False,
        "force_replace": False,
        "retries": 5,
        "waiter_delay": 5,
        "waiter_timeout": 120,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    args = dict(_params())
    args.update(extra)
    return module_args(**args)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or _params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeCdnClient(object):
    """In-memory CdnClient stand-in.

    Stores API-shaped topic dicts; ListClsLogTopics groups them by LogsetId
    (first logset as the default, the rest as ExtraLogset), mirroring the SDK
    response the module's _topic_candidates() consumes. Write ops mutate the
    store so the module's post-write find_topic() refetch converges.
    """

    def __init__(self, items=None):
        self.items = [dict(item) for item in (items or [])]
        self.calls = []
        self._next_id = 1

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _find(self, topic_id):
        for item in self.items:
            if item["TopicId"] == topic_id:
                return item
        return None

    @staticmethod
    def _domain_configs(request):
        return [{"Domain": config.Domain, "Area": list(config.Area)} for config in (request.DomainAreaConfigs or [])]

    def CreateClsLogTopic(self, request):
        self._record("CreateClsLogTopic", request)
        topic_id = "topic-fake-%d" % self._next_id
        self._next_id += 1
        self.items.append(
            {
                "TopicId": topic_id,
                "TopicName": request.TopicName,
                "LogsetId": request.LogsetId,
                "Enabled": False,
                "InheritDomainTags": request.InheritDomainTags,
                "DomainAreaConfigs": self._domain_configs(request),
            }
        )
        return SimpleNamespace(TopicId=topic_id, RequestId="req-fake")

    def DeleteClsLogTopic(self, request):
        self._record("DeleteClsLogTopic", request)
        self.items = [item for item in self.items if item["TopicId"] != request.TopicId]
        return SimpleNamespace(RequestId="req-fake")

    def DisableClsLogTopic(self, request):
        self._record("DisableClsLogTopic", request)
        item = self._find(request.TopicId)
        if item:
            item["Enabled"] = False
        return SimpleNamespace(RequestId="req-fake")

    def EnableClsLogTopic(self, request):
        self._record("EnableClsLogTopic", request)
        item = self._find(request.TopicId)
        if item:
            item["Enabled"] = True
        return SimpleNamespace(RequestId="req-fake")

    def ListClsLogTopics(self, request):
        self._record("ListClsLogTopics", request)
        grouped = {}
        for item in self.items:
            grouped.setdefault(item.get("LogsetId"), []).append(dict(item))
        logsets = sorted(grouped, key=lambda key: key or "")
        if not logsets:
            return SimpleNamespace(Logset=None, Topics=[], ExtraLogset=[], RequestId="req-fake")
        first = logsets[0]
        extras = [
            SimpleNamespace(
                Logset=FakeResource({"LogsetId": key}),
                Topics=[FakeResource(dict(topic)) for topic in grouped[key]],
            )
            for key in logsets[1:]
        ]
        return SimpleNamespace(
            Logset=FakeResource({"LogsetId": first}),
            Topics=[FakeResource(dict(topic)) for topic in grouped[first]],
            ExtraLogset=extras,
            RequestId="req-fake",
        )

    def ListClsTopicDomains(self, request):
        self._record("ListClsTopicDomains", request)
        item = self._find(request.TopicId)
        configs = (item or {}).get("DomainAreaConfigs") or []
        return SimpleNamespace(
            DomainAreaConfigs=[FakeResource(dict(config)) for config in configs],
            InheritDomainTags=bool((item or {}).get("InheritDomainTags")),
            RequestId="req-fake",
        )

    def ManageClsTopicDomains(self, request):
        self._record("ManageClsTopicDomains", request)
        item = self._find(request.TopicId)
        if item:
            item["DomainAreaConfigs"] = self._domain_configs(request)
            item["InheritDomainTags"] = request.InheritDomainTags
        return SimpleNamespace(RequestId="req-fake")

    def written(self):
        return [name for name, request in self.calls if name in WRITE_OPS]


def _patch_env(monkeypatch, fake):
    """Wire the module's SDK boundary to the in-memory client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(CdnClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


# ---------------------------------------------------------------------------
# Request-builder helpers
# ---------------------------------------------------------------------------


def test_list_topics_request():
    request = mod.list_topics_request(FakeModels(), "ecdn")
    assert request.Channel == "ecdn"


def test_list_domains_request():
    request = mod.list_domains_request(FakeModels(), _params(channel="ecdn"), "topic-1", "logset-1")
    assert request.TopicId == "topic-1"
    assert request.LogsetId == "logset-1"
    assert request.Channel == "ecdn"


def test_domain_configs_sorted_by_domain_with_sorted_areas():
    values = [
        _config("global.example.com", ["overseas", "mainland"]),
        _config("static.example.com", ["overseas"]),
    ]
    configs = mod._domain_configs(FakeModels(), values)
    assert [config.Domain for config in configs] == ["global.example.com", "static.example.com"]
    assert configs[0].Area == ["mainland", "overseas"]
    assert configs[1].Area == ["overseas"]


def test_domain_configs_none_is_empty():
    assert mod._domain_configs(FakeModels(), None) == []


def test_create_request():
    p = _params(
        topic_name="cdn-access",
        logset_id="logset-8b0a1c2d",
        channel="cdn",
        inherit_domain_tags=True,
        domain_area_configs=[_config("static.example.com", ["mainland"])],
    )
    request = mod.create_request(FakeModels(), p)
    assert request.TopicName == "cdn-access"
    assert request.LogsetId == "logset-8b0a1c2d"
    assert request.Channel == "cdn"
    assert request.InheritDomainTags is True
    assert [config.Domain for config in request.DomainAreaConfigs] == ["static.example.com"]


def test_manage_domains_request():
    p = _params(channel="cdn", domain_area_configs=[_config("static.example.com", ["mainland"])])
    request = mod.manage_domains_request(FakeModels(), p, "topic-1", "logset-1")
    assert request.TopicId == "topic-1"
    assert request.LogsetId == "logset-1"
    assert request.InheritDomainTags is False
    assert [config.Domain for config in request.DomainAreaConfigs] == ["static.example.com"]


def test_enable_disable_delete_requests():
    p = _params(channel="cdn")
    enabled = mod.enable_request(FakeModels(), p, "topic-1", "logset-1")
    assert enabled.TopicId == "topic-1"
    assert enabled.LogsetId == "logset-1"
    assert enabled.Channel == "cdn"
    disabled = mod.disable_request(FakeModels(), p, "topic-1", "logset-1")
    assert disabled.TopicId == "topic-1"
    deleted = mod.delete_request(FakeModels(), p, "topic-1", "logset-1")
    assert deleted.TopicId == "topic-1"
    assert deleted.LogsetId == "logset-1"


# ---------------------------------------------------------------------------
# _topic_candidates and _normalized
# ---------------------------------------------------------------------------


def test_topic_candidates_embeds_logset_ids():
    response = SimpleNamespace(
        Logset=FakeResource({"LogsetId": "logset-default"}),
        Topics=[FakeResource({"TopicId": "topic-1", "TopicName": "a"})],
        ExtraLogset=[
            SimpleNamespace(
                Logset=FakeResource({"LogsetId": "logset-extra"}),
                Topics=[FakeResource({"TopicId": "topic-2", "TopicName": "b"})],
            )
        ],
    )
    candidates = mod._topic_candidates(response)
    assert [(item["TopicId"], item["LogsetId"]) for item in candidates] == [
        ("topic-1", "logset-default"),
        ("topic-2", "logset-extra"),
    ]


def test_topic_candidates_empty_response():
    response = SimpleNamespace(Logset=None, Topics=[], ExtraLogset=[])
    assert mod._topic_candidates(response) == []


def test_normalized_sorts_and_normalizes_shapes():
    values = [
        {"Domain": "static.example.com", "Area": ["mainland"]},
        {"domain": "global.example.com", "areas": ["overseas"]},
        {"domain": "a.example.com", "areas": None},
    ]
    normalized = mod._normalized(values)
    assert [item["Domain"] for item in normalized] == ["a.example.com", "global.example.com", "static.example.com"]
    assert normalized[0]["Area"] == []
    assert normalized[1]["Area"] == ["overseas"]
    assert normalized[2]["Area"] == ["mainland"]


def test_normalized_none_is_empty():
    assert mod._normalized(None) == []


# ---------------------------------------------------------------------------
# find_topic()
# ---------------------------------------------------------------------------


def test_find_topic_by_id():
    fake = FakeCdnClient(items=[_topic()])
    module = FakeModule()
    found = mod.find_topic(module, fake, FakeModels(), _params(topic_id="topic-8b0a1c2d"))
    assert found["TopicName"] == "cdn-access"
    assert found["LogsetId"] == "logset-8b0a1c2d"
    assert found["DomainAreaConfigs"] == TOPIC["DomainAreaConfigs"]
    assert found["InheritDomainTags"] is True


def test_find_topic_by_name():
    fake = FakeCdnClient(items=[_topic()])
    module = FakeModule()
    found = mod.find_topic(module, fake, FakeModels(), _params(topic_name="cdn-access"))
    assert found["TopicId"] == "topic-8b0a1c2d"


def test_find_topic_none_when_absent():
    fake = FakeCdnClient()
    module = FakeModule()
    found = mod.find_topic(module, fake, FakeModels(), _params(topic_name="missing"))
    assert found is None
    assert [name for name, request in fake.calls] == ["ListClsLogTopics"]


def test_find_topic_logset_filter_disambiguates():
    fake = FakeCdnClient(items=[_topic(), _topic(TopicId="topic-2", LogsetId="logset-other")])
    module = FakeModule()
    found = mod.find_topic(module, fake, FakeModels(), _params(topic_name="cdn-access", logset_id="logset-other"))
    assert found["TopicId"] == "topic-2"


def test_find_topic_fails_on_multiple_matches():
    fake = FakeCdnClient(items=[_topic(), _topic(TopicId="topic-2", LogsetId="logset-other")])
    module = FakeModule()
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find_topic(module, fake, FakeModels(), _params(topic_name="cdn-access"))
    assert "Multiple CDN CLS topics matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main paths
# ---------------------------------------------------------------------------


def test_required_one_of_enforced(monkeypatch):
    _patch_env(monkeypatch, FakeCdnClient())
    module_args()
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_missing_create_params_fails(monkeypatch):
    _patch_env(monkeypatch, FakeCdnClient())
    _run_args(topic_id="topic-8b0a1c2d")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "topic_name and logset_id are required when creating a topic" in exc.value.args[0]["msg"]


def test_sdk_error_is_reported(monkeypatch):
    _patch_env(monkeypatch, _BoomClient())
    _run_args(topic_name="cdn-access", logset_id="logset-8b0a1c2d")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["failed"] is True
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_absent_noop_when_not_found(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCdnClient())
    _run_args(state="absent", topic_name="missing")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["topic"] is None
    assert fake.written() == []


def test_absent_removes_existing(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCdnClient(items=[_topic()]))
    _run_args(state="absent", topic_id="topic-8b0a1c2d")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"] is None
    assert fake.written() == ["DeleteClsLogTopic"]
    assert fake.items == []


def test_absent_missing_logset_fails(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCdnClient(items=[_topic(LogsetId=None)]))
    _run_args(state="absent", topic_name="cdn-access")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "logset_id is required to delete this topic" in exc.value.args[0]["msg"]
    assert fake.written() == []


def test_absent_check_mode_does_not_delete(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCdnClient(items=[_topic()]))
    _run_args(_ansible_check_mode=True, state="absent", topic_id="topic-8b0a1c2d")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"]["TopicId"] == "topic-8b0a1c2d"
    assert fake.written() == []
    assert len(fake.items) == 1


def test_present_creates_and_enables(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCdnClient())
    _run_args(
        topic_name="cdn-access",
        logset_id="logset-8b0a1c2d",
        enabled=True,
        inherit_domain_tags=True,
        domain_area_configs=[
            _config("global.example.com", ["overseas"]),
            _config("static.example.com", ["mainland"]),
        ],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.written() == ["CreateClsLogTopic", "EnableClsLogTopic"]
    topic = result["topic"]
    assert topic["TopicId"].startswith("topic-fake-")
    assert topic["TopicName"] == "cdn-access"
    assert topic["Enabled"] is True
    assert topic["InheritDomainTags"] is True
    assert [config["Domain"] for config in topic["DomainAreaConfigs"]] == ["global.example.com", "static.example.com"]


def test_present_up_to_date_noop(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCdnClient(items=[_topic()]))
    _run_args(
        topic_name="cdn-access",
        logset_id="logset-8b0a1c2d",
        enabled=True,
        inherit_domain_tags=True,
        domain_area_configs=[
            _config("global.example.com", ["overseas"]),
            _config("static.example.com", ["mainland"]),
        ],
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert fake.written() == []


def test_present_updates_domain_bindings(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCdnClient(items=[_topic()]))
    _run_args(
        topic_name="cdn-access",
        logset_id="logset-8b0a1c2d",
        enabled=True,
        inherit_domain_tags=True,
        domain_area_configs=[_config("static.example.com", ["mainland"])],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.written() == ["ManageClsTopicDomains"]
    assert result["topic"]["DomainAreaConfigs"] == [{"Domain": "static.example.com", "Area": ["mainland"]}]


def test_present_updates_inherit_domain_tags(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCdnClient(items=[_topic(InheritDomainTags=False)]))
    _run_args(
        topic_name="cdn-access",
        logset_id="logset-8b0a1c2d",
        enabled=True,
        inherit_domain_tags=True,
        domain_area_configs=[_config("global.example.com", ["overseas"]), _config("static.example.com", ["mainland"])],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.written() == ["ManageClsTopicDomains"]
    assert result["topic"]["InheritDomainTags"] is True


def test_present_disables_when_enabled_false(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCdnClient(items=[_topic()]))
    _run_args(
        topic_name="cdn-access",
        logset_id="logset-8b0a1c2d",
        enabled=False,
        inherit_domain_tags=True,
        domain_area_configs=[_config("global.example.com", ["overseas"]), _config("static.example.com", ["mainland"])],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.written() == ["DisableClsLogTopic"]
    assert result["topic"]["Enabled"] is False


def test_present_enables_when_enabled_true(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCdnClient(items=[_topic(Enabled=False)]))
    _run_args(
        topic_name="cdn-access",
        logset_id="logset-8b0a1c2d",
        enabled=True,
        inherit_domain_tags=True,
        domain_area_configs=[_config("global.example.com", ["overseas"]), _config("static.example.com", ["mainland"])],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.written() == ["EnableClsLogTopic"]
    assert result["topic"]["Enabled"] is True


def test_immutable_name_without_force_replace_fails(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCdnClient(items=[_topic()]))
    _run_args(topic_id="topic-8b0a1c2d", topic_name="renamed", logset_id="logset-8b0a1c2d")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["failed"] is True
    assert "force_replace" in payload["msg"]
    assert fake.written() == []


def test_force_replace_recreates_topic(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCdnClient(items=[_topic()]))
    _run_args(
        topic_id="topic-8b0a1c2d",
        topic_name="renamed",
        logset_id="logset-8b0a1c2d",
        enabled=True,
        force_replace=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.written() == ["DeleteClsLogTopic", "CreateClsLogTopic", "EnableClsLogTopic"]
    topic = result["topic"]
    assert topic["TopicName"] == "renamed"
    assert topic["TopicId"] != "topic-8b0a1c2d"
    assert len(fake.items) == 1
    assert fake.items[0]["TopicName"] == "renamed"


def test_present_check_mode_create_does_not_write(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCdnClient())
    _run_args(
        _ansible_check_mode=True,
        topic_name="cdn-access",
        logset_id="logset-8b0a1c2d",
        domain_area_configs=[_config("static.example.com", ["mainland"])],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"] is None
    assert fake.written() == []
    assert fake.items == []


def test_present_check_mode_update_does_not_write(monkeypatch):
    fake = _patch_env(monkeypatch, FakeCdnClient(items=[_topic()]))
    _run_args(
        _ansible_check_mode=True,
        topic_name="cdn-access",
        logset_id="logset-8b0a1c2d",
        domain_area_configs=[_config("static.example.com", ["mainland"])],
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["topic"]["TopicId"] == "topic-8b0a1c2d"
    assert fake.written() == []


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom
