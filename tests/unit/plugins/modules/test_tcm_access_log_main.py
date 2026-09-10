"""Unit tests for the tcm_access_log write module (run_module flows).

``run_module()`` is driven end to end against an in-memory fake TCM client
whose ``ModifyAccessLogConfig`` mutates a per-mesh config store, so the
post-update ``DescribeAccessLogConfig`` refetch used by the waiter converges
immediately.

Scenario matrix:

* idempotent no-op when the live config already matches (with and without
  server-enriched nested fields)
* drift update through ``ModifyAccessLogConfig`` with captured request fields
* check-mode update is a dry run that reports the desired projection
* argument-validation failures (custom template without format, gRPC server
  without address) before any SDK call
* argument-validation failure before any SDK call
* the blanket ``sdk_error_payload`` failure path
* legacy helper regression tests (folded from test_tcm_access_log.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tcm_access_log as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

MESH_ID = "mesh-abcdefgh"


def _config(**overrides):
    item = {
        "SelectedRange": None,
        "Template": "istio",
        "Enable": True,
        "CLS": None,
        "Encoding": "TEXT",
        "Format": None,
        "EnableStdout": True,
        "EnableServer": False,
        "Address": None,
    }
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"mesh_id": MESH_ID}
    params.update(overrides)
    return module_args(**params)


class FakeTcmAccessLogClient(object):
    """In-memory TCM client mutating one access-log config per mesh."""

    def __init__(self, config=None):
        self.config = copy.deepcopy(config) if config is not None else {}
        self.calls = []
        self.last_request = None

    def _raw(self, value):
        return copy.deepcopy(value.__dict__) if value is not None else None

    def DescribeAccessLogConfig(self, request):
        self.calls.append("DescribeAccessLogConfig")
        assert request.MeshId == MESH_ID
        return FakeResource(dict(self.config, RequestId="req-fake"))

    def ModifyAccessLogConfig(self, request):
        self.calls.append("ModifyAccessLogConfig")
        self.last_request = request
        self.config = {
            "SelectedRange": self._raw(request.SelectedRange),
            "Template": request.Template,
            "Enable": request.Enable,
            "CLS": self._raw(request.CLS),
            "Encoding": request.Encoding,
            "Format": request.Format,
            "EnableStdout": request.EnableStdout,
            "EnableServer": request.EnableServer,
            "Address": request.Address,
        }
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TcmClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# idempotent flows
# ---------------------------------------------------------------------------


def test_matching_config_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmAccessLogClient(config=_config()))
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["access_log"]["Enable"] is True
    assert result["access_log"]["Template"] == "istio"
    assert fake.calls == ["DescribeAccessLogConfig"]


def test_matching_config_allows_server_enriched_nested_fields(monkeypatch):
    _make_module(
        monkeypatch,
        FakeTcmAccessLogClient(config=_config(SelectedRange={"All": True, "Namespace": "default"})),
    )
    _base(selected_range={"All": True})
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["access_log"]["SelectedRange"]["Namespace"] == "default"


# ---------------------------------------------------------------------------
# update flows
# ---------------------------------------------------------------------------


def test_drift_config_is_updated(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmAccessLogClient(config=_config(Template="trace", Enable=False)))
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["access_log"]["Enable"] is True
    assert result["access_log"]["Template"] == "istio"
    request = fake.last_request
    assert request.MeshId == MESH_ID
    assert request.Enable is True
    assert request.Template == "istio"
    assert request.Encoding == "TEXT"
    assert request.EnableStdout is True
    assert fake.calls == ["DescribeAccessLogConfig", "ModifyAccessLogConfig", "DescribeAccessLogConfig"]


def test_update_maps_destinations_and_encoding(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmAccessLogClient(config=_config(Template="trace")))
    _base(encoding="JSON", selected_range={"All": True}, cls={"TopicId": "topic-1"})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["access_log"]["Encoding"] == "JSON"
    assert result["access_log"]["CLS"] == {"TopicId": "topic-1"}
    request = fake.last_request
    assert request.Encoding == "JSON"
    assert request.SelectedRange.__dict__ == {"All": True}
    assert request.CLS.__dict__ == {"TopicId": "topic-1"}


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmAccessLogClient(config=_config(Template="trace", Encoding="JSON")))
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["access_log"] == _config()  # desired projection
    assert fake.config["Template"] == "trace"
    assert "ModifyAccessLogConfig" not in fake.calls


# ---------------------------------------------------------------------------
# argument validation and failure paths
# ---------------------------------------------------------------------------


def test_custom_template_requires_format(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmAccessLogClient())
    _base(template="custom")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "format is required" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_enable_server_requires_address(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmAccessLogClient())
    _base(enable_server=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "server_address is required" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_missing_mesh_id_fails(monkeypatch):
    fake = _make_module(monkeypatch, FakeTcmAccessLogClient())
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "mesh_id" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeAccessLogConfig(self, request):
            raise Boom("tcm endpoint unreachable")

    _make_module(monkeypatch, ExplodingClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "tcm endpoint unreachable" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tcm_access_log.py)
# ---------------------------------------------------------------------------


def _legacy_params():
    return {
        "mesh_id": "mesh-1",
        "enabled": True,
        "selected_range": {"All": True},
        "template": "istio",
        "encoding": "JSON",
        "format": None,
        "cls": {"TopicId": "topic-1"},
        "enable_stdout": True,
        "enable_server": False,
        "server_address": None,
    }


def test_access_log_request_maps_destinations_and_encoding():
    value = mod.update_request(FakeModels(), _legacy_params())
    assert value.MeshId == "mesh-1"
    assert value.Encoding == "JSON"
    assert value.CLS.TopicId == "topic-1"
    assert mod.desired(_legacy_params())["EnableStdout"] is True


def test_access_log_convergence_allows_server_enriched_nested_fields():
    target = mod.desired(_legacy_params())
    current = dict(target, SelectedRange={"All": True, "Namespace": "default"})
    assert mod.converged(current, target)
