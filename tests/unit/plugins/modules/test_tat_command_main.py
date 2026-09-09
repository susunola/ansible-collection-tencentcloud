"""Unit tests for the tat_command write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TAT client whose
write operations mutate the command store so the post-write waiter converges
on its first poll.

Scenario matrix:

* absent on a missing command (idempotent no-op)
* absent with a matching command (check-mode dry run and the real delete)
* creation when missing (argument-spec guard for state=present, the
  default_parameters guard, check-mode dry run and the happy path)
* no-op when nothing drifts
* drift updates (description / content) with and without check mode
* immutable guards: enable_parameters and tags cannot be changed
* the blanket ``Tencent Cloud API request failed`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tat_command as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

COMMAND_ID = "cmd-8b0a1c2d"

CONTENT = "echo hi"


def _content(value):
    return mod._content(value)


def _parameters(value):
    return mod._parameters(value)


def _command(**overrides):
    item = {
        "CommandId": COMMAND_ID,
        "CommandName": "install-agent",
        "Content": _content(CONTENT),
        "Description": "",
        "CommandType": "SHELL",
        "WorkingDirectory": "/root",
        "Timeout": 60,
        "EnableParameter": False,
        "DefaultParameters": _parameters({}),
        "Username": "root",
        "CreatedBy": "USER",
        "Tags": [{"Key": "env", "Value": "prod"}],
    }
    item.update(overrides)
    return item


def _base(**overrides):
    # NOTE: keys carrying ``choices`` (state, command_type) must not be
    # pre-filled with None. command_id/name are a required_one_of pair.
    params = {}
    params.update(overrides)
    return module_args(**params)


def _present_args(**overrides):
    # ``_matches`` compares ``_tags(current)`` against ``(desired or None)``,
    # so an empty tags dict never converges: every create/update scenario
    # manages at least one tag (matching the store default).
    params = {"name": "install-agent", "content": CONTENT, "tags": {"env": "prod"}}
    params.update(overrides)
    return module_args(**params)


def _id_args(**overrides):
    params = {"command_id": COMMAND_ID}
    params.update(overrides)
    return module_args(**params)


class FakeTatClient(object):
    """In-memory TAT client mutating a small command store."""

    def __init__(self, commands=None):
        self.commands = [copy.deepcopy(t) for t in (commands or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeCommands(self, request):
        self._record("DescribeCommands", request)
        ids = list(getattr(request, "CommandIds", None) or [])
        filters = {getattr(f, "Name", None): list(getattr(f, "Values", None) or []) for f in (getattr(request, "Filters", None) or [])}
        matched = []
        for item in self.commands:
            if ids and item.get("CommandId") not in ids:
                continue
            if filters.get("command-name") and item.get("CommandName") not in filters["command-name"]:
                continue
            matched.append(dict(item))
        return SimpleNamespace(CommandSet=[FakeResource(t) for t in matched], TotalCount=len(matched))

    def CreateCommand(self, request):
        self._record("CreateCommand", request)
        item = {
            "CommandId": "cmd-new-%d" % (len(self.commands) + 1),
            "CommandName": getattr(request, "CommandName", None),
            "Content": getattr(request, "Content", None),
            "Description": getattr(request, "Description", None),
            "CommandType": getattr(request, "CommandType", None),
            "WorkingDirectory": getattr(request, "WorkingDirectory", None),
            "Timeout": getattr(request, "Timeout", None),
            "EnableParameter": getattr(request, "EnableParameter", None),
            "DefaultParameters": getattr(request, "DefaultParameters", None),
            "Username": getattr(request, "Username", None),
            "OutputCOSBucketUrl": getattr(request, "OutputCOSBucketUrl", None),
            "OutputCOSKeyPrefix": getattr(request, "OutputCOSKeyPrefix", None),
            "CreatedBy": "USER",
        }
        item["Tags"] = [{"Key": getattr(t, "Key", None), "Value": getattr(t, "Value", None)} for t in (getattr(request, "Tags", None) or [])]
        self.commands.append(item)
        return SimpleNamespace(CommandId=item["CommandId"], RequestId="req-fake")

    def ModifyCommand(self, request):
        self._record("ModifyCommand", request)
        for item in self.commands:
            if item.get("CommandId") == getattr(request, "CommandId", None):
                for attr in (
                    "CommandName", "Content", "Description", "CommandType",
                    "WorkingDirectory", "Timeout", "DefaultParameters", "Username",
                    "OutputCOSBucketUrl", "OutputCOSKeyPrefix",
                ):
                    value = getattr(request, attr, None)
                    if value is not None:
                        item[attr] = value
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCommand(self, request):
        self._record("DeleteCommand", request)
        self.commands = [t for t in self.commands if t.get("CommandId") != getattr(request, "CommandId", None)]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_tat", lambda: (models or FakeModels(), SimpleNamespace(TatClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_command_is_idempotent(monkeypatch):
    fake = FakeTatClient(commands=[])
    _make_module(monkeypatch, fake)
    _id_args(state="absent", command_id="cmd-ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["command"] is None
    assert result["msg"] == "TAT command is absent"


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTatClient(commands=[_command()])
    _make_module(monkeypatch, fake)
    _id_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would delete TAT command"
    assert len(fake.commands) == 1
    assert "DeleteCommand" not in [c for c, unused in fake.calls]


def test_absent_deletes_command(monkeypatch):
    fake = FakeTatClient(commands=[_command()])
    _make_module(monkeypatch, fake)
    _id_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "TAT command deleted"
    assert result["command"] is None
    assert fake.commands == []
    assert "DeleteCommand" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_name_and_content(monkeypatch):
    fake = FakeTatClient(commands=[])
    _make_module(monkeypatch, fake)
    _base(state="present", command_id=COMMAND_ID)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "name" in payload["msg"]
    assert "content" in payload["msg"]


def test_default_parameters_require_enable_parameters(monkeypatch):
    fake = FakeTatClient(commands=[])
    _make_module(monkeypatch, fake)
    _present_args(state="present", default_parameters={"region": "cn"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "enable_parameters must be true" in exc.value.args[0]["msg"]


def test_create_command(monkeypatch):
    fake = FakeTatClient(commands=[])
    _make_module(monkeypatch, fake)
    _present_args(state="present", timeout=300, description="bootstrap agent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "TAT command created"
    assert result["command"]["CommandName"] == "install-agent"
    assert result["command"]["Timeout"] == 300
    assert len(fake.commands) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeCommands"
    assert "CreateCommand" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeTatClient(commands=[])
    _make_module(monkeypatch, fake)
    _present_args(_ansible_check_mode=True, state="present")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would create TAT command"
    assert fake.commands == []
    assert "CreateCommand" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# existing-command flows
# ---------------------------------------------------------------------------


def test_existing_command_no_drift_is_idempotent(monkeypatch):
    fake = FakeTatClient(commands=[_command()])
    _make_module(monkeypatch, fake)
    _present_args(state="present")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "TAT command is up to date"
    assert result["command"]["CommandId"] == COMMAND_ID


def test_update_command_description(monkeypatch):
    fake = FakeTatClient(commands=[_command(Description="old desc")])
    _make_module(monkeypatch, fake)
    _present_args(state="present", description="new desc")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "TAT command updated"
    assert result["command"]["Description"] == "new desc"
    assert "ModifyCommand" in [c for c, unused in fake.calls]


def test_update_command_content(monkeypatch):
    fake = FakeTatClient(commands=[_command()])
    _make_module(monkeypatch, fake)
    _present_args(state="present", content="echo hi updated", description="bump")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["command"]["Content"] == _content("echo hi updated")
    assert result["command"]["Description"] == "bump"


def test_update_check_mode_is_dry_run(monkeypatch):
    fake = FakeTatClient(commands=[_command(Description="old desc")])
    _make_module(monkeypatch, fake)
    _present_args(_ansible_check_mode=True, state="present", description="new desc")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update TAT command"
    assert fake.commands[0]["Description"] == "old desc"
    assert "ModifyCommand" not in [c for c, unused in fake.calls]


def test_enable_parameters_cannot_change(monkeypatch):
    fake = FakeTatClient(commands=[_command(EnableParameter=False)])
    _make_module(monkeypatch, fake)
    _present_args(state="present", enable_parameters=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "enable_parameters cannot be changed" in exc.value.args[0]["msg"]


def test_tags_cannot_change(monkeypatch):
    fake = FakeTatClient(commands=[_command(Tags=[{"Key": "env", "Value": "prod"}])])
    _make_module(monkeypatch, fake)
    _present_args(state="present", tags={"env": "dev"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "tags cannot be changed" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeCommands(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _present_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tat_command.py)
# ---------------------------------------------------------------------------

PARAMS = {
    "name": "hello",
    "content": "#!/bin/bash\necho {{word}}",
    "description": "hello",
    "command_type": "SHELL",
    "working_directory": "/root",
    "timeout": 60,
    "enable_parameters": True,
    "default_parameters": {"word": "hello"},
    "username": "root",
    "output_cos_bucket_url": None,
    "output_cos_key_prefix": None,
    "tags": {"env": "prod"},
}


def test_request_builders_encode_content_and_parameters():
    models = FakeModels()
    create = mod.build_create_request(models, PARAMS)
    assert create.Content == "IyEvYmluL2Jhc2gKZWNobyB7e3dvcmR9fQ=="
    assert create.DefaultParameters == '{"word":"hello"}'
    assert create.Tags[0].Key == "env"
    update = mod.build_update_request(models, "cmd-x", PARAMS)
    assert update.CommandId == "cmd-x"
    assert mod.build_delete_request(models, "cmd-x").CommandId == "cmd-x"


def test_exact_idempotency():
    desired = mod._desired(PARAMS)
    current = dict(desired)
    current["Tags"] = [{"Key": "env", "Value": "prod"}]
    assert mod._matches(current, desired)
    current["Timeout"] = 120
    assert not mod._matches(current, desired)
