"""Unit tests for the tsf_application_config write module.

Drives ``run_module()`` against an in-memory fake TSF client whose config
describe / create / delete calls mutate a version-keyed config list so
post-write describes converge immediately.

Version-content semantics: an existing application config version is
immutable. Re-running ``present`` with matching content is a no-op, but any
drift on the version's identity or content fails with an immutable-change
error instead of silently creating a competing version.

Scenario matrix:

* present: create with value, immutable no-op by name/version and by
  config_id, missing-value guard, immutable drift rejection, check mode
* absent: no-op, delete, check mode, rejected delete
* lookup ambiguity guard and the blanket SDK failure path
* legacy pure-helper assertions folded from the shallow test file
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tsf_application_config as mod
from ansible_collections.susunola.tencentcloud.plugins.modules.tsf_application_config import desired
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

APP_ID = "app-a"
CFG_NAME = "settings"
CFG_VERSION = "v1"
CFG_VALUE = "feature: true"

_STORE_KEYS = ("ConfigId", "ApplicationId", "ConfigName", "ConfigVersion",
               "ConfigValue", "ConfigVersionDesc", "ConfigType")


def _config(config_id, **overrides):
    value = {"ConfigId": config_id, "ApplicationId": APP_ID, "ConfigName": CFG_NAME,
             "ConfigVersion": CFG_VERSION, "ConfigValue": CFG_VALUE,
             "ConfigVersionDesc": "initial", "ConfigType": "application"}
    value.update(overrides)
    return value


def _config_args(**overrides):
    params = {"application_id": APP_ID, "name": CFG_NAME, "version": CFG_VERSION,
              "value": CFG_VALUE, "state": "present"}
    params.update(overrides)
    return module_args(**params)


class FakeTsfClient(object):
    """In-memory TSF client backed by a mutable application-config list."""

    def __init__(self, configs=None):
        self.configs = [dict(c) for c in configs or []]
        self.calls = []
        self._next_id = 1

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _new_id(self):
        value = "config-%d" % self._next_id
        self._next_id += 1
        return value

    def DescribeConfig(self, request):
        self._record("DescribeConfig", request)
        for config in self.configs:
            if config["ConfigId"] == getattr(request, "ConfigId", None):
                return SimpleNamespace(Result=FakeResource(dict(config)), RequestId="req-fake")
        return SimpleNamespace(Result=None, RequestId="req-fake")

    def DescribeConfigs(self, request):
        self._record("DescribeConfigs", request)
        matches = [c for c in self.configs
                   if c["ApplicationId"] == getattr(request, "ApplicationId", None)
                   and c["ConfigName"] == getattr(request, "ConfigName", None)
                   and c["ConfigVersion"] == getattr(request, "ConfigVersion", None)]
        payload = [FakeResource(dict(c)) for c in matches]
        return SimpleNamespace(Result=SimpleNamespace(Content=payload), RequestId="req-fake")

    def CreateConfig(self, request):
        self._record("CreateConfig", request)
        config = {"ConfigId": self._new_id()}
        for key in _STORE_KEYS:
            if key != "ConfigId" and hasattr(request, key):
                config[key] = getattr(request, key)
        self.configs.append(config)
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def DeleteConfig(self, request):
        self._record("DeleteConfig", request)
        self.configs = [c for c in self.configs if c["ConfigId"] != getattr(request, "ConfigId", None)]
        return SimpleNamespace(Result=True, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TsfClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_creates_config(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _config_args(value="checkout: true")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["config"]["ConfigId"] == "config-1"
    assert result["config"]["ConfigName"] == CFG_NAME
    assert result["config"]["ConfigVersion"] == CFG_VERSION
    assert result["config"]["ConfigValue"] == "checkout: true"
    assert result["config"]["ConfigType"] == "application"
    assert "CreateConfig" in _names(fake)
    assert len(fake.configs) == 1


def test_present_matching_version_is_idempotent(monkeypatch):
    fake = FakeTsfClient(configs=[_config("config-7")])
    _make_module(monkeypatch, fake)
    _config_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["config"]["ConfigId"] == "config-7"
    assert "CreateConfig" not in _names(fake)


def test_present_by_config_id_is_idempotent(monkeypatch):
    fake = FakeTsfClient(configs=[_config("config-7")])
    _make_module(monkeypatch, fake)
    _config_args(config_id="config-7")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["config"]["ConfigId"] == "config-7"


def test_present_value_drift_is_rejected_as_immutable(monkeypatch):
    fake = FakeTsfClient(configs=[_config("config-7", ConfigValue="old: true")])
    _make_module(monkeypatch, fake)
    _config_args(value="new: true")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed on an existing" in payload["msg"]
    assert "ConfigValue" in payload["immutable_changes"]
    assert "CreateConfig" not in _names(fake)


def test_present_missing_value_when_creating_fails(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _config_args(value=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "value is required when creating" in exc.value.args[0]["msg"]


def test_present_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _config_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["config"]["ConfigName"] == CFG_NAME
    assert "ConfigId" not in result["config"]
    assert "CreateConfig" not in _names(fake)
    assert fake.configs == []


# ---------------------------------------------------------------------------
# lookup semantics
# ---------------------------------------------------------------------------


def test_multiple_matching_versions_fail(monkeypatch):
    fake = FakeTsfClient(configs=[_config("config-1", ConfigValue="a"), _config("config-2", ConfigValue="b")])
    _make_module(monkeypatch, fake)
    _config_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSF application configuration versions matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_unregistered_is_idempotent(monkeypatch):
    fake = FakeTsfClient(configs=[_config("config-7", ConfigVersion="v0")])
    _make_module(monkeypatch, fake)
    _config_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["config"] is None
    assert "DeleteConfig" not in _names(fake)


def test_absent_deletes_config(monkeypatch):
    fake = FakeTsfClient(configs=[_config("config-7")])
    _make_module(monkeypatch, fake)
    _config_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["config"] is None
    assert "DeleteConfig" in _names(fake)
    assert fake.configs == []


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfClient(configs=[_config("config-7")])
    _make_module(monkeypatch, fake)
    _config_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["config"] is None
    assert "DeleteConfig" not in _names(fake)
    assert len(fake.configs) == 1


def test_rejected_delete_fails(monkeypatch):
    class RejectingClient(FakeTsfClient):
        def DeleteConfig(self, request):
            self._record("DeleteConfig", request)
            return SimpleNamespace(Result=False, RequestId="req-err")

    fake = RejectingClient(configs=[_config("config-7")])
    _make_module(monkeypatch, fake)
    _config_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rejected the TSF application configuration deletion" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeConfigs(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _config_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy pure-helper assertions (folded from the shallow test file)
# ---------------------------------------------------------------------------


def test_legacy_desired_maps_exact_version_state():
    params = {"application_id": "app-a", "name": "settings", "version": "v1",
              "value": "feature: true", "version_description": "initial"}
    assert desired(params) == {
        "ApplicationId": "app-a",
        "ConfigName": "settings",
        "ConfigVersion": "v1",
        "ConfigValue": "feature: true",
        "ConfigVersionDesc": "initial",
        "ConfigType": "application",
    }
