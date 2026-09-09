"""Unit tests for the tse_config_file write module (run_module flows).

``run_module()`` creates, updates and deletes TSE configuration-file draft
content. It is driven end to end against an in-memory fake client whose
create/modify/delete operations mutate a config-file store, so the
post-write ``DescribeConfigFile`` refetch converges immediately.

Scenario matrix:

* absent without a file (idempotent) / check-mode delete / real delete
* creation when missing, with content/format required (check mode and real)
* idempotent no-op when the live file already contains the desired fields
* content drift updates through the modify API (check mode and real)
* creation without content or format fails before mutation
* blanket ``sdk_error_payload`` failure path
* legacy helper regression tests (folded from test_tse_config_file.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_config_file as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "ins-tse-abc"
NAMESPACE = "production"
GROUP = "application"
NAME = "orders.yaml"
CONTENT = "server:\n  port: 8080\n"


def _base(**overrides):
    params = {
        "state": "present",
        "instance_id": INSTANCE_ID,
        "namespace": NAMESPACE,
        "group": GROUP,
        "name": NAME,
        "content": CONTENT,
        "format": "YAML",
    }
    params.update(overrides)
    return module_args(**params)


def _file(content=CONTENT, extra=None):
    value = {
        "Id": "cf-1",
        "Name": NAME,
        "Namespace": NAMESPACE,
        "Group": GROUP,
        "Content": content,
        "Format": "YAML",
        "Status": "EDITING",
    }
    if extra:
        value.update(extra)
    return value


class FakeConfigFileClient(object):
    """In-memory TSE client holding configuration files by identity."""

    def __init__(self, files=None):
        self.files = {}
        for value in (files or []):
            self.files[self._key(value)] = copy.deepcopy(value)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    @staticmethod
    def _key(value):
        return (value["Namespace"], value["Group"], value["Name"])

    def DescribeConfigFile(self, request):
        self._record("DescribeConfigFile", request)
        assert request.InstanceId == INSTANCE_ID
        assert request.Namespace == NAMESPACE
        assert request.Group == GROUP
        assert request.Name == NAME
        value = self.files.get((request.Namespace, request.Group, request.Name))
        return SimpleNamespace(ConfigFile=FakeResource(value) if value else None, RequestId="req-fake")

    def _payload(self, request):
        return dict(request.ConfigFile.__dict__)

    def CreateConfigFile(self, request):
        self._record("CreateConfigFile", request)
        payload = self._payload(request)
        payload.setdefault("Id", "cf-new")
        self.files[self._key(payload)] = payload
        return SimpleNamespace(RequestId="req-fake")

    def ModifyConfigFiles(self, request):
        self._record("ModifyConfigFiles", request)
        payload = self._payload(request)
        self.files[self._key(payload)] = payload
        return SimpleNamespace(RequestId="req-fake")

    def DeleteConfigFiles(self, request):
        self._record("DeleteConfigFiles", request)
        key = (request.Namespace, request.Group, request.Name)
        self.files.pop(key, None)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_without_file_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeConfigFileClient())
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["config_file"] is None
    assert _names(fake) == ["DescribeConfigFile"]


def test_absent_deletes_existing_file(monkeypatch):
    fake = _make_module(monkeypatch, FakeConfigFileClient(files=[_file()]))
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["config_file"] is None
    assert fake.files == {}
    assert _names(fake) == ["DescribeConfigFile", "DeleteConfigFiles"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeConfigFileClient(files=[_file()]))
    _base(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.files) == 1
    assert "DeleteConfigFiles" not in _names(fake)


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_present_creates_missing_file(monkeypatch):
    fake = _make_module(monkeypatch, FakeConfigFileClient())
    _base(comment="order config")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["config_file"]["Content"] == CONTENT
    assert result["config_file"]["Comment"] == "order config"
    assert len(fake.files) == 1
    assert _names(fake) == ["DescribeConfigFile", "CreateConfigFile", "DescribeConfigFile"]


def test_present_create_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeConfigFileClient())
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["config_file"]["Name"] == NAME
    assert fake.files == {}
    assert "CreateConfigFile" not in _names(fake)


def test_present_create_requires_content_and_format(monkeypatch):
    fake = _make_module(monkeypatch, FakeConfigFileClient())
    _base(content=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "required for a new TSE configuration file" in payload["msg"]
    assert payload["missing"] == ["content"]
    assert _names(fake) == ["DescribeConfigFile"]


# ---------------------------------------------------------------------------
# idempotent and drift flows
# ---------------------------------------------------------------------------


def test_converged_file_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeConfigFileClient(files=[_file()]))
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["config_file"]["Id"] == "cf-1"
    assert _names(fake) == ["DescribeConfigFile"]


def test_content_drift_updates_existing_file(monkeypatch):
    fake = _make_module(monkeypatch, FakeConfigFileClient(files=[_file(content="server:\n  port: 3000\n")]))
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["config_file"]["Content"] == CONTENT
    assert fake.files[(NAMESPACE, GROUP, NAME)]["Content"] == CONTENT
    assert _names(fake) == ["DescribeConfigFile", "ModifyConfigFiles", "DescribeConfigFile"]


def test_content_drift_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeConfigFileClient(files=[_file(content="server:\n  port: 3000\n")]))
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["config_file"]["Content"] == CONTENT
    assert fake.files[(NAMESPACE, GROUP, NAME)]["Content"] == "server:\n  port: 3000\n"
    assert "ModifyConfigFiles" not in _names(fake)


def test_comment_drift_updates_without_content_change(monkeypatch):
    fake = _make_module(monkeypatch, FakeConfigFileClient(files=[_file()]))
    _base(comment="new description")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["config_file"]["Comment"] == "new description"
    assert fake.files[(NAMESPACE, GROUP, NAME)]["Comment"] == "new description"


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeConfigFile(self, request):
            raise Boom("tse endpoint unreachable")

    fake = _make_module(monkeypatch, ExplodingClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "tse endpoint unreachable" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tse_config_file.py)
# ---------------------------------------------------------------------------


def test_desired_maps_only_supplied_fields():
    p = {
        "name": NAME,
        "namespace": NAMESPACE,
        "group": GROUP,
        "content": CONTENT,
        "format": "YAML",
        "comment": None,
        "tags": None,
        "supported_client": None,
        "persistent": None,
        "encrypted": None,
        "encrypt_algo": None,
    }
    target = mod.desired(p)
    assert target == {"Name": NAME, "Namespace": NAMESPACE, "Group": GROUP, "Content": CONTENT, "Format": "YAML"}


def test_contains_allows_extra_live_fields():
    target = mod.desired(
        {
            "name": "a.yaml",
            "namespace": "prod",
            "group": "app",
            "content": "x",
            "format": "YAML",
        }
    )
    assert mod.contains(dict(target, Status="EDITING", Id="f1"), target)
    assert not mod.contains(dict(target, Content="stale"), target)


def test_delete_request_maps_identity_and_id():
    p = {
        "instance_id": "i1",
        "namespace": "prod",
        "group": "app",
        "name": "a.yaml",
        "content": "x",
        "format": "YAML",
    }
    request = mod.delete_request(FakeModels(), p, {"Id": "f1"})
    assert request.InstanceId == "i1"
    assert request.Namespace == "prod"
    assert request.Group == "app"
    assert request.Name == "a.yaml"
    assert request.Id == "f1"


def test_request_wraps_payload_in_config_file_model():
    p = {"instance_id": "i1"}
    value = {"Name": "a.yaml", "Content": "x"}
    create = mod.request(FakeModels().CreateConfigFileRequest, FakeModels(), p, value)
    assert create.InstanceId == "i1"
    assert create.ConfigFile.__dict__["Name"] == "a.yaml"
    assert create.ConfigFile.__dict__["Content"] == "x"
    modify = mod.request(FakeModels().ModifyConfigFilesRequest, FakeModels(), p, value)
    assert modify.InstanceId == "i1"
    assert modify.ConfigFile.__dict__["Content"] == "x"
