"""Unit tests for the cls_config write module (helpers + run_module).

Creates, updates and deletes CLS LogListener collection configurations.
Nested SDK objects (extract_rule -> ExtractRuleInfo, each exclude_path ->
ExcludePathInfo) are built through ``cls._deserialize(payload)``, so the
model stand-in exposes a payload-capturing ``_deserialize``. The API
carries the destination topic as ``Output``. find() pages the config list
(name-filtered when looking up by name) and fails on more than one match.
Every create/update refinds by the resulting ConfigId with no name filter.
name + topic_id are validated before the SDK is reached; the config_id /
name required_one_of fires for absent runs too.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cls_config as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeResource,
    module_args,
    run,
)


class _SdkError(Exception):
    """Stand-in for TencentCloudSDKException carrying a code/request id."""

    def __init__(self, code, message="", request_id=None):
        super(_SdkError, self).__init__(message)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


class _DeserializableRequest(object):
    """SDK request/model stand-in whose ``_deserialize`` captures payloads."""

    def _deserialize(self, data):
        self._payload = dict(data or {})


class _Models(object):
    """Stand-in for the CLS ``models`` module.

    ExtractRuleInfo and ExcludePathInfo return ``_deserialize``-capable
    classes (they are payload-ingested); every other name (Filter, request
    builders, ...) is a plain attribute-assignable class.
    """

    def __getattr__(self, name):
        if name in ("ExtractRuleInfo", "ExcludePathInfo"):
            return type(name, (_DeserializableRequest,), {})
        return type(name, (object,), {})


def _config(**overrides):
    """API-shaped stored config; fresh copy per call."""
    item = {
        "config_id": "cs-1001",
        "name": "nginx-access",
        "topic_id": "topic-1001",
        "path": "/var/log/nginx/access.log",
        "log_type": "minimalist_log",
        "extract_rule": None,
        "exclude_paths": [],
        "user_define_rule": None,
        "advanced_config": None,
        "input_type": None,
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "config_id": None,
        "name": "nginx-access",
        "topic_id": "topic-1001",
        "path": "/var/log/nginx/access.log",
        "log_type": "minimalist_log",
        "extract_rule": None,
        "exclude_paths": [],
        "user_define_rule": None,
        "advanced_config": None,
        "input_type": None,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    params = _params(**extra)
    args = {k: v for k, v in params.items() if v is not None}
    for key, value in extra.items():
        if key.startswith("_"):
            args[key] = value
    return module_args(**args)


def _serialize_config(a):
    """Map a stored config dict onto its API response shape."""
    return {
        "ConfigId": a["config_id"],
        "Name": a["name"],
        "Output": a["topic_id"],
        "Path": a["path"],
        "LogType": a["log_type"],
        "ExtractRule": a["extract_rule"],
        "ExcludePaths": list(a["exclude_paths"]),
        "UserDefineRule": a["user_define_rule"],
        "AdvancedConfig": a["advanced_config"],
        "InputType": a["input_type"],
    }


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


class FakeClsClient(object):
    """In-memory ClsClient stand-in storing config dicts.

    DescribeConfigs honours the configName Filter when present and returns
    every config otherwise (the module applies its own id/name match and
    multi-match check); CreateConfig synthesises sequential cs-NNNN ids and
    unwraps the payload-bearing ExtractRule / ExcludePaths requests;
    ModifyConfig rewrites the config selected by request.ConfigId;
    DeleteConfig removes by id.
    """

    def __init__(self, configs=None):
        self.configs = [dict(c) for c in (configs or [])]
        self.calls = []
        self._seq = 2000

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _next_id(self):
        self._seq += 1
        return "cs-%d" % self._seq

    def DescribeConfigs(self, request):
        self._record("DescribeConfigs", request)
        filters = getattr(request, "Filters", None) or []
        result = self.configs
        if filters:
            wanted = filters[0].Values[0]
            result = [c for c in self.configs if c["name"] == wanted]
        return SimpleNamespace(
            Configs=[FakeResource(_serialize_config(c)) for c in result],
            TotalCount=len(result),
            RequestId="req-fake",
        )

    def _ingest(self, request):
        return {
            "name": request.Name,
            "topic_id": request.Output,
            "path": request.Path,
            "log_type": request.LogType,
            "extract_rule": getattr(request.ExtractRule, "_payload", None) if getattr(request, "ExtractRule", None) else None,
            "exclude_paths": [x._payload for x in request.ExcludePaths],
            "user_define_rule": getattr(request, "UserDefineRule", None),
            "advanced_config": getattr(request, "AdvancedConfig", None),
            "input_type": getattr(request, "InputType", None),
        }

    def CreateConfig(self, request):
        self._record("CreateConfig", request)
        config_id = self._next_id()
        stored = _config(config_id=config_id)
        stored.update(self._ingest(request))
        self.configs.append(stored)
        return SimpleNamespace(ConfigId=config_id, RequestId="req-fake")

    def ModifyConfig(self, request):
        self._record("ModifyConfig", request)
        ingested = self._ingest(request)
        for config in self.configs:
            if config["config_id"] == request.ConfigId:
                config.update(ingested)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteConfig(self, request):
        self._record("DeleteConfig", request)
        self.configs = [c for c in self.configs if c["config_id"] != request.ConfigId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (_Models(), SimpleNamespace(ClsClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise _SdkError("AuthFailure", "auth rejected", request_id="req-err")

        return boom


# ---------------------------------------------------------------------------
# helper tests
# ---------------------------------------------------------------------------


def test_build_describe_without_name_sets_paging():
    request = mod.build_describe(_Models())
    assert request.Offset == 0
    assert request.Limit == 100
    assert not hasattr(request, "Filters")


def test_build_describe_with_name_sets_filter():
    request = mod.build_describe(_Models(), "nginx-access")
    assert request.Filters[0].Key == "configName"
    assert request.Filters[0].Values == ["nginx-access"]


def test_model_deserializes_payload():
    item = mod._model(_Models(), "ExtractRuleInfo", {"delimiter": "|"})
    assert item._payload == {"delimiter": "|"}


def test_apply_create_sets_flat_fields():
    request = mod.apply(_Models().CreateConfigRequest(), _Models(), _params())
    assert request.Name == "nginx-access"
    assert request.Output == "topic-1001"
    assert request.Path == "/var/log/nginx/access.log"
    assert request.LogType == "minimalist_log"
    assert request.ExcludePaths == []
    assert not hasattr(request, "ConfigId")
    assert not hasattr(request, "ExtractRule")


def test_apply_ingests_extract_rule_and_exclude_paths():
    params = _params(
        extract_rule={"delimiter": "|", "keys": ["time", "msg"]},
        exclude_paths=[{"Type": "Path", "Value": "/tmp/err.log"}],
    )
    request = mod.apply(_Models().CreateConfigRequest(), _Models(), params)
    assert request.ExtractRule._payload == {"delimiter": "|", "keys": ["time", "msg"]}
    assert request.ExcludePaths[0]._payload == {"Type": "Path", "Value": "/tmp/err.log"}


def test_apply_update_sets_config_id():
    request = mod.apply(_Models().ModifyConfigRequest(), _Models(), _params(), "cs-7")
    assert request.ConfigId == "cs-7"
    assert request.Name == "nginx-access"


def test_apply_threads_optional_strings():
    request = mod.apply(
        _Models().CreateConfigRequest(),
        _Models(),
        _params(user_define_rule='{"k":1}', advanced_config='{"a":1}', input_type="file"),
    )
    assert request.UserDefineRule == '{"k":1}'
    assert request.AdvancedConfig == '{"a":1}'
    assert request.InputType == "file"


def test_build_wrappers_and_delete():
    create = mod.build_create(_Models(), _params())
    assert create.Name == "nginx-access"
    update = mod.build_update(_Models(), _params(), "cs-9")
    assert update.ConfigId == "cs-9"
    delete = mod.build_delete(_Models(), "cs-9")
    assert delete.ConfigId == "cs-9"


def test_desired_builds_nine_key_target():
    value = mod.desired(_params(user_define_rule='{"k":1}'))
    assert value["Name"] == "nginx-access"
    assert value["Output"] == "topic-1001"
    assert value["Path"] == "/var/log/nginx/access.log"
    assert value["UserDefineRule"] == '{"k":1}'
    assert value["ExcludePaths"] == []


def test_comparable_keeps_nine_keys():
    value = mod.comparable({"Name": "x", "Output": "y", "Path": "p", "LogType": "z", "ExtractRule": None,
                            "ExcludePaths": [], "UserDefineRule": None, "AdvancedConfig": None, "InputType": "file"})
    assert value["InputType"] == "file"
    assert value["Name"] == "x"


def test_find_matches_by_config_id():
    fake = FakeClsClient([_config()])
    module = FakeModule(_params(config_id="cs-1001"))
    value = mod.find(module, fake, _Models(), "cs-1001", None)
    assert value["ConfigId"] == "cs-1001"
    assert value["Name"] == "nginx-access"
    assert not hasattr(module.sdk_calls[0][1], "Filters")


def test_find_matches_by_name():
    fake = FakeClsClient([_config()])
    module = FakeModule(_params())
    value = mod.find(module, fake, _Models(), None, "nginx-access")
    assert value["ConfigId"] == "cs-1001"
    assert module.sdk_calls[0][1].Filters[0].Values == ["nginx-access"]


def test_find_no_match_returns_none():
    fake = FakeClsClient([_config()])
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, _Models(), None, "ghost") is None


def test_find_multi_match_fails():
    fake = FakeClsClient([_config(), _config(config_id="cs-1002")])
    module = FakeModule(_params())
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, _Models(), None, "nginx-access")
    payload = exc.value.args[0]
    assert "Multiple CLS configs have the requested name" in payload["msg"]
    assert payload["name"] == "nginx-access"


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_requires_either_config_id_or_name(monkeypatch):
    fake = FakeClsClient()
    _make_module(monkeypatch, fake)
    _run_args(name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "one of the following is required" in exc.value.args[0]["msg"]
    assert fake.calls == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"config_id": "cs-x", "name": None},
        {"topic_id": None},
    ],
)
def test_present_requires_name_and_topic(monkeypatch, overrides):
    fake = FakeClsClient()
    _make_module(monkeypatch, fake)
    _run_args(**overrides)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name and topic_id are required when state=present" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_absent_noop_when_missing(monkeypatch):
    fake = FakeClsClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["config"] is None
    assert [c[0] for c in fake.calls] == ["DescribeConfigs"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakeClsClient([_config()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["config"]["ConfigId"] == "cs-1001"
    assert result["diff"]["before"]["ConfigId"] == "cs-1001"
    assert result["diff"]["after"] is None
    assert [c[0] for c in fake.calls] == ["DescribeConfigs"]
    assert len(fake.configs) == 1


def test_absent_deletes_config(monkeypatch):
    fake = FakeClsClient([_config()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["config"] is None
    assert [c[0] for c in fake.calls] == ["DescribeConfigs", "DeleteConfig"]
    deleted = fake.calls[1][1]
    assert deleted.ConfigId == "cs-1001"
    assert fake.configs == []


def test_present_noop_when_config_matches(monkeypatch):
    fake = FakeClsClient([_config()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["config"]["ConfigId"] == "cs-1001"
    assert result["config"]["Name"] == "nginx-access"
    assert [c[0] for c in fake.calls] == ["DescribeConfigs"]


def test_present_path_drift_updates_config(monkeypatch):
    fake = FakeClsClient([_config()])
    _make_module(monkeypatch, fake)
    _run_args(path="/var/log/nginx/error.log")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["config"]["Path"] == "/var/log/nginx/error.log"
    assert [c[0] for c in fake.calls] == [
        "DescribeConfigs",
        "ModifyConfig",
        "DescribeConfigs",
    ]
    updated = fake.calls[1][1]
    assert updated.ConfigId == "cs-1001"
    assert updated.Path == "/var/log/nginx/error.log"
    assert updated.Output == "topic-1001"
    assert fake.configs[0]["path"] == "/var/log/nginx/error.log"


def test_present_extract_rule_drift_updates_config(monkeypatch):
    fake = FakeClsClient([_config(extract_rule={"delimiter": ","})])
    _make_module(monkeypatch, fake)
    _run_args(extract_rule={"delimiter": "|"})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["config"]["ExtractRule"] == {"delimiter": "|"}
    updated = fake.calls[1][1]
    assert updated.ConfigId == "cs-1001"
    assert updated.ExtractRule._payload == {"delimiter": "|"}
    assert fake.configs[0]["extract_rule"] == {"delimiter": "|"}


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeClsClient([_config()])
    _make_module(monkeypatch, fake)
    _run_args(path="/var/log/nginx/error.log", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["config"]["Path"] == "/var/log/nginx/access.log"
    assert result["diff"]["before"]["Path"] == "/var/log/nginx/access.log"
    assert result["diff"]["after"]["Path"] == "/var/log/nginx/error.log"
    assert [c[0] for c in fake.calls] == ["DescribeConfigs"]
    assert fake.configs[0]["path"] == "/var/log/nginx/access.log"


def test_present_creates_config(monkeypatch):
    fake = FakeClsClient()
    _make_module(monkeypatch, fake)
    _run_args(
        extract_rule={"delimiter": "|"},
        exclude_paths=[{"Type": "Path", "Value": "/tmp/err.log"}],
        user_define_rule='{"k":1}',
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["config"]["ConfigId"] == "cs-2001"
    assert result["config"]["Name"] == "nginx-access"
    assert result["config"]["Output"] == "topic-1001"
    assert result["config"]["ExtractRule"] == {"delimiter": "|"}
    assert result["config"]["ExcludePaths"] == [{"Type": "Path", "Value": "/tmp/err.log"}]
    assert result["config"]["UserDefineRule"] == '{"k":1}'
    assert [c[0] for c in fake.calls] == [
        "DescribeConfigs",
        "CreateConfig",
        "DescribeConfigs",
    ]
    created = fake.calls[1][1]
    assert created.Name == "nginx-access"
    assert created.Output == "topic-1001"
    assert created.Path == "/var/log/nginx/access.log"
    assert created.LogType == "minimalist_log"
    assert created.ExtractRule._payload == {"delimiter": "|"}
    assert created.ExcludePaths[0]._payload == {"Type": "Path", "Value": "/tmp/err.log"}
    assert created.UserDefineRule == '{"k":1}'
    assert not hasattr(created, "ConfigId")
    assert len(fake.configs) == 1
    assert fake.configs[0]["config_id"] == "cs-2001"


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeClsClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["config"] is None
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["Name"] == "nginx-access"
    assert [c[0] for c in fake.calls] == ["DescribeConfigs"]
    assert fake.configs == []


def test_sdk_failure_reports_error_payload(monkeypatch):
    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "auth rejected"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeClsClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.main)
    assert result["changed"] is False
    assert result["config"] is None
