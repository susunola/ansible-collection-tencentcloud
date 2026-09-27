"""Deep harness tests for the dlc_model_artifact_info module.

Covers build_request (strong model-version identity) and run_module
end-to-end over the config/files/readme artifact calls: request identity,
independent artifact selection, ConfigJson parsing, the "no artifact
selected" validation and the sdk_error_payload failure contract. This module
has no paginator; each artifact is a single describe call.

The module subclasses ``TencentCloudModule``, so the migration patches the base
class's ``create_client`` and the module's own ``_load`` (which is where it
imports its models and client class), and lets ``module_args()`` supply the
credentials the base class validates. The fixtures serialise ``ModelName``,
``ConfigJson``, ``Files`` (``FileNode``) and ``Readme``, the fields the
``GetModelConfig``/``GetModelFiles``/``GetModelReadme`` responses really carry,
so the payload ``add_return_samples.py`` captures is the shape a caller sees.
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import types

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_model_artifact_info
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)


class Request:
    pass


class FakeModels:
    GetModelConfigRequest = Request
    GetModelFilesRequest = Request
    GetModelReadmeRequest = Request


def params(**overrides):
    options = {
        "model_uid": "model-1", "model_version": "v2",
        "include_config": True, "include_files": True, "include_readme": True,
    }
    options.update(overrides)
    return options


def test_build_request_uses_strong_model_version_identity():
    request = dlc_model_artifact_info.build_request(Request, params())
    assert request.ModelUid == "model-1"
    assert request.ModelVersion == "v2"


class FakeResponse:
    def __init__(self, value):
        self.value = dict(value)

    def _serialize(self, allow_none=True):
        return dict(self.value)


class FakeClient:
    def __init__(self, responses):
        self.responses = dict(responses)
        self.calls = []

    def _serve(self, name, request):
        self.calls.append((name, request.ModelUid, request.ModelVersion))
        return FakeResponse(self.responses[name])

    def GetModelConfig(self, request):
        return self._serve("config", request)

    def GetModelFiles(self, request):
        return self._serve("files", request)

    def GetModelReadme(self, request):
        return self._serve("readme", request)


class SDKError(Exception):
    def get_code(self):
        return "UnauthorizedOperation"

    def get_request_id(self):
        return "req-err"


def _patch_sdk(monkeypatch, client):
    """Hand the module its models/client class and the client itself."""
    monkeypatch.setattr(dlc_model_artifact_info, "_load", lambda: (
        FakeModels, types.SimpleNamespace(DlcClient=lambda *args: client)))
    monkeypatch.setattr(TencentCloudModule, "create_client",
                        lambda self, client_class, endpoint: client)


def test_run_module_combines_all_artifacts_and_parses_config_json(monkeypatch):
    client = FakeClient({
        "config": {"ModelName": "m", "ConfigJson": '{"layers": 12}', "RequestId": "rc"},
        "files": {"Files": [{"Name": "weights"}], "RequestId": "rf"},
        "readme": {"Readme": "# Model", "RequestId": "rr"},
    })
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", **params())

    payload = run(dlc_model_artifact_info.run_module)

    assert payload["changed"] is False
    assert payload["request_ids"] == {"config": "rc", "files": "rf", "readme": "rr"}
    assert payload["config"]["Config"] == {"layers": 12}
    assert "RequestId" not in payload["config"]
    assert payload["files"]["Files"] == [{"Name": "weights"}]
    assert payload["readme"]["Readme"] == "# Model"
    assert all(call[1:] == ("model-1", "v2") for call in client.calls)
    assert [call[0] for call in client.calls] == ["config", "files", "readme"]


def test_run_module_honours_selection_and_tolerates_invalid_config_json(monkeypatch):
    p = params(include_files=False, include_readme=False)
    client = FakeClient({"config": {"ConfigJson": "not-json", "RequestId": "rc"}})
    _patch_sdk(monkeypatch, client)
    module_args(region="ap-guangzhou", **p)

    payload = run(dlc_model_artifact_info.run_module)

    # The real TencentCloudModule.exit_json adds the audit trail of the SDK
    # calls it recorded, so take it out before the exact payload assertion.
    calls = payload.pop("tc_api_calls")
    assert [call["operation"] for call in calls] == ["GetModelConfig"]
    assert payload == {
        "changed": False,
        "request_ids": {"config": "rc"},
        "config": {"ConfigJson": "not-json", "Config": None},
    }
    assert [call[0] for call in client.calls] == ["config"]


def test_run_module_rejects_no_selected_artifact(monkeypatch):
    p = params(include_config=False, include_files=False, include_readme=False)
    _patch_sdk(monkeypatch, None)
    module_args(region="ap-guangzhou", **p)

    with pytest.raises(AnsibleFailJson) as failure:
        run(dlc_model_artifact_info.run_module)

    assert failure.value.args[0]["msg"] == "at least one model artifact must be selected"


def test_run_module_fails_cleanly_on_sdk_error(monkeypatch):
    class FailingClient:
        def _explode(self, request):
            raise SDKError("api exploded")

        GetModelConfig = _explode
        GetModelFiles = _explode
        GetModelReadme = _explode

    _patch_sdk(monkeypatch, FailingClient())
    module_args(region="ap-guangzhou", **params())

    with pytest.raises(AnsibleFailJson) as failure:
        run(dlc_model_artifact_info.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "api exploded"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
