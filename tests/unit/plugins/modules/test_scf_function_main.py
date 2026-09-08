"""Unit tests for the scf_function write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake SCF client whose
writes mutate the function store so the post-write ``GetFunction`` refetch
converges immediately. A missing function is signalled the way the real SDK
does: ``GetFunction`` raises an exception whose code starts with
``ResourceNotFound``.

Scenario matrix:

* absent on a missing function (idempotent no-op)
* absent with a matching function (check-mode dry run and the real delete)
* creation when missing (handler/runtime guards, zip-vs-cos exclusivity guard,
  check-mode dry run and the happy path)
* no-op when nothing drifts
* configuration drift updates (memory size / description)
* code drift updates through the COS source
* the blanket ``Tencent Cloud API request failed`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import scf_function as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

FUNCTION = {
    "FunctionName": "hello-world",
    "Namespace": "default",
    "Runtime": "Python3.10",
    "Handler": "index.main_handler",
    "Status": "Active",
    "MemorySize": 128,
    "Timeout": 3,
    "Description": "",
    "CodeSize": 0,
}


def _function(**overrides):
    item = copy.deepcopy(FUNCTION)
    item.update(overrides)
    return item


def _base(**overrides):
    # NOTE: keys carrying ``choices`` (state) must not be pre-filled with None.
    params = {"function_name": "hello-world"}
    params.update(overrides)
    return module_args(**params)


class FakeNotFound(Exception):
    def get_code(self):
        return "ResourceNotFound.Function"

    def get_request_id(self):
        return "req-missing"


class FakeScfClient(object):
    """In-memory SCF client mutating a small function store."""

    def __init__(self, functions=None):
        self.functions = [copy.deepcopy(t) for t in (functions or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _function(self, function_name, namespace):
        for item in self.functions:
            if item.get("FunctionName") == function_name and item.get("Namespace", "default") == namespace:
                return item
        return None

    def GetFunction(self, request):
        self._record("GetFunction", request)
        item = self._function(getattr(request, "FunctionName", None), getattr(request, "Namespace", None))
        if item is None:
            raise FakeNotFound("function does not exist")
        return FakeResource(dict(item))

    def CreateFunction(self, request):
        self._record("CreateFunction", request)
        item = {
            "FunctionName": getattr(request, "FunctionName", None),
            "Namespace": getattr(request, "Namespace", None),
            "Runtime": getattr(request, "Runtime", None),
            "Handler": getattr(request, "Handler", None),
            "Status": "Active",
        }
        for attr, name in (
            ("MemorySize", "MemorySize"), ("Timeout", "Timeout"),
            ("Description", "Description"), ("CodeSize", "CodeSize"),
        ):
            value = getattr(request, attr, None)
            if value is not None:
                item[name] = value
        if getattr(request, "Code", None) is not None:
            code = request.Code
            if getattr(code, "CosObjectName", None):
                item["CodeSize"] = len(getattr(code, "CosObjectName", ""))
        self.functions.append(item)
        return SimpleNamespace(RequestId="req-fake")

    def UpdateFunctionConfiguration(self, request):
        self._record("UpdateFunctionConfiguration", request)
        item = self._function(getattr(request, "FunctionName", None), getattr(request, "Namespace", None))
        if item is None:
            return SimpleNamespace(RequestId="req-fake")
        for attr, name in (
            ("Description", "Description"), ("MemorySize", "MemorySize"),
            ("Timeout", "Timeout"),
        ):
            value = getattr(request, attr, None)
            if value is not None:
                item[name] = value
        return SimpleNamespace(RequestId="req-fake")

    def UpdateFunctionCode(self, request):
        self._record("UpdateFunctionCode", request)
        item = self._function(getattr(request, "FunctionName", None), getattr(request, "Namespace", None))
        if item is not None:
            item["CodeSize"] = len(getattr(request, "CosObjectName", None) or "")
        return SimpleNamespace(RequestId="req-fake")

    def DeleteFunction(self, request):
        self._record("DeleteFunction", request)
        name = getattr(request, "FunctionName", None)
        namespace = getattr(request, "Namespace", None)
        self.functions = [
            t for t in self.functions
            if not (t.get("FunctionName") == name and t.get("Namespace", "default") == namespace)
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_scf", lambda: (models or FakeModels(), SimpleNamespace(ScfClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_function_is_idempotent(monkeypatch):
    fake = FakeScfClient(functions=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", function_name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "Function already absent"
    assert [c for c, unused in fake.calls] == ["GetFunction"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeScfClient(functions=[_function()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete function"
    assert len(fake.functions) == 1
    assert "DeleteFunction" not in [c for c, unused in fake.calls]


def test_absent_deletes_function(monkeypatch):
    fake = FakeScfClient(functions=[_function()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Function deleted"
    assert result["function"] is None
    assert fake.functions == []
    assert "DeleteFunction" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_handler(monkeypatch):
    fake = FakeScfClient(functions=[])
    _make_module(monkeypatch, fake)
    _base(state="present", runtime="Python3.10")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "handler is required when creating a function" in exc.value.args[0]["msg"]


def test_create_requires_runtime(monkeypatch):
    fake = FakeScfClient(functions=[])
    _make_module(monkeypatch, fake)
    _base(state="present", handler="index.main_handler")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "runtime is required when creating a function" in exc.value.args[0]["msg"]


def test_zip_and_cos_are_mutually_exclusive(monkeypatch):
    fake = FakeScfClient(functions=[])
    _make_module(monkeypatch, fake)
    _base(state="present", zip_file="/tmp/some.zip", cos_bucket_name="bucket")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "mutually exclusive" in exc.value.args[0]["msg"]


def test_create_function(monkeypatch):
    fake = FakeScfClient(functions=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        runtime="Python3.10",
        handler="index.main_handler",
        memory_size=128,
        execution_timeout=3,
        description="hello demo",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Function created"
    assert result["function"]["FunctionName"] == "hello-world"
    assert result["function"]["MemorySize"] == 128
    assert len(fake.functions) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "GetFunction"
    assert "CreateFunction" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeScfClient(functions=[])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        runtime="Python3.10",
        handler="index.main_handler",
        memory_size=128,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create function"
    assert fake.functions == []
    assert "CreateFunction" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-function flows
# ---------------------------------------------------------------------------


def test_existing_function_no_drift_is_idempotent(monkeypatch):
    fake = FakeScfClient(functions=[_function()])
    _make_module(monkeypatch, fake)
    _base(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "Function is up to date"
    assert result["function"]["FunctionName"] == "hello-world"


def test_update_memory_size(monkeypatch):
    fake = FakeScfClient(functions=[_function()])
    _make_module(monkeypatch, fake)
    _base(state="present", memory_size=256)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Function updated"
    assert result["function"]["MemorySize"] == 256
    ops = [c for c, unused in fake.calls]
    assert "UpdateFunctionConfiguration" in ops
    assert "UpdateFunctionCode" not in ops


def test_update_description_drift(monkeypatch):
    fake = FakeScfClient(functions=[_function()])
    _make_module(monkeypatch, fake)
    _base(state="present", description="renamed purpose")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["function"]["Description"] == "renamed purpose"


def test_update_code_from_cos(monkeypatch):
    fake = FakeScfClient(functions=[_function()])
    _make_module(monkeypatch, fake)
    _base(state="present", cos_bucket_name="my-bucket", cos_object_name="fn/v2.zip", cos_bucket_region="ap-guangzhou")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["function"]["CodeSize"] == len("fn/v2.zip")
    ops = [c for c, unused in fake.calls]
    assert "UpdateFunctionCode" in ops


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeScfClient(functions=[_function()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", memory_size=512)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update function"
    assert fake.functions[0]["MemorySize"] == 128
    assert "UpdateFunctionConfiguration" not in [c for c, unused in fake.calls]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def GetFunction(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
