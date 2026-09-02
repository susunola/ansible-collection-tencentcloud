"""Unit tests for the tat_invoker write module (helpers + run_module).

Covers the create / drift-update / enable-toggle / delete flows of
``plugins/modules/tat_invoker.py`` with an in-memory fake TAT client whose
write operations mutate the invoker store, so the module's post-write
``find`` refetch converges immediately. Invokers are matched by
``invoker_id`` or ``name``; schedules are compared on their three policy
fields and command parameters only via a SHA-256 digest so secret values
never leave the module (output parameters are scrubbed to ``<redacted>``).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import hashlib
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tat_invoker as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

PARAMS_JSON = '{"environment":"production"}'

INVOKER = {
    "InvokerId": "ivk-8b0a1c2d",
    "Name": "nightly-maintenance",
    "Type": "SCHEDULE",
    "CommandId": "cmd-8b0a1c2d",
    "InstanceIds": ["ins-8b0a1c2d", "ins-9c3d2e1f"],
    "Username": "root",
    "Parameters": PARAMS_JSON,
    "ScheduleSettings": {"Policy": "RECURRENCE", "Recurrence": "0 2 * * *", "InvokeTime": None},
    "Enable": True,
}


def _invoker(**overrides):
    """API-shaped invoker dict isolated from the shared constant."""
    item = copy.deepcopy(INVOKER)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec (base included)."""
    params = {
        "state": "present",
        "invoker_id": None,
        "name": "nightly-maintenance",
        "command_id": "cmd-8b0a1c2d",
        "instance_ids": ["ins-8b0a1c2d", "ins-9c3d2e1f"],
        "username": "root",
        "parameters": {"environment": "production"},
        "policy": "RECURRENCE",
        "recurrence": "0 2 * * *",
        "invoke_time": None,
        "enabled": True,
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


class FakeTatClient(object):
    """In-memory TatClient stand-in.

    Stores API-shaped invoker dicts. DescribeInvokers honours Offset/Limit
    and the optional InvokerIds filter so find() pagination is exercised;
    write ops mutate the store so post-write refetches converge. Create
    defaults to an enabled invoker; the module then issues an explicit
    Enable/Disable call to converge the desired state.
    """

    def __init__(self, invokers=None):
        self.invokers = [copy.deepcopy(i) for i in (invokers or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    @staticmethod
    def _schedule_dict(schedule):
        return {k: v for k, v in vars(schedule).items() if not k.startswith("_")}

    def _invoker_payload(self, request):
        return {
            "Name": request.Name,
            "Type": request.Type,
            "CommandId": request.CommandId,
            "InstanceIds": list(request.InstanceIds or []),
            "Username": getattr(request, "Username", None),
            "Parameters": request.Parameters,
            "ScheduleSettings": self._schedule_dict(request.ScheduleSettings),
        }

    def _update_item(self, resource_id, **fields):
        for item in self.invokers:
            if item.get("InvokerId") == resource_id:
                item.update(fields)
                return True
        return False

    def DescribeInvokers(self, request):
        self._record("DescribeInvokers", request)
        pool = self.invokers
        ids = list(getattr(request, "InvokerIds", None) or [])
        if ids:
            pool = [i for i in pool if i.get("InvokerId") in ids]
        page = pool[request.Offset : request.Offset + request.Limit]
        return SimpleNamespace(
            InvokerSet=[FakeResource(dict(i)) for i in page],
            TotalCount=len(pool),
            RequestId="req-fake",
        )

    def CreateInvoker(self, request):
        self._record("CreateInvoker", request)
        self._next += 1
        invoker_id = "ivk-fake-%03d" % self._next
        item = self._invoker_payload(request)
        item["InvokerId"] = invoker_id
        item["Enable"] = True  # API default; Enable/Disable calls converge it
        self.invokers.append(item)
        return SimpleNamespace(InvokerId=invoker_id, RequestId="req-fake")

    def ModifyInvoker(self, request):
        self._record("ModifyInvoker", request)
        payload = self._invoker_payload(request)
        self._update_item(request.InvokerId, **payload)
        return SimpleNamespace(RequestId="req-fake")

    def EnableInvoker(self, request):
        self._record("EnableInvoker", request)
        self._update_item(request.InvokerId, Enable=True)
        return SimpleNamespace(RequestId="req-fake")

    def DisableInvoker(self, request):
        self._record("DisableInvoker", request)
        self._update_item(request.InvokerId, Enable=False)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteInvoker(self, request):
        self._record("DeleteInvoker", request)
        self.invokers = [i for i in self.invokers if i.get("InvokerId") != request.InvokerId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TatClient=object)),
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
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------


def test_json_empty_becomes_braces():
    assert mod._json(None) == "{}"
    assert mod._json("") == "{}"
    assert mod._json({}) == "{}"


def test_json_canonicalises_dict():
    assert mod._json({"b": 1, "a": {"z": 2, "y": 3}}) == '{"a":{"y":3,"z":2},"b":1}'


def test_json_round_trips_string_input():
    assert mod._json('{"b": 1, "a": 2}') == '{"a":2,"b":1}'


def test_digest_tracks_value_and_is_stable():
    assert mod._digest({"environment": "production"}) == hashlib.sha256(PARAMS_JSON.encode("utf-8")).hexdigest()
    assert mod._digest({"environment": "staging"}) != mod._digest({"environment": "production"})


# ---------------------------------------------------------------------------
# Request builders
# ---------------------------------------------------------------------------


def test_schedule_builder_fields():
    schedule = mod._schedule(FakeModels(), _params(policy="ONCE", recurrence=None, invoke_time="2026-09-05T03:00:00Z"))
    assert schedule.Policy == "ONCE"
    assert schedule.Recurrence is None
    assert schedule.InvokeTime == "2026-09-05T03:00:00Z"


def test_describe_request_fields_without_id():
    request = mod.describe_request(FakeModels(), _params(invoker_id=None), offset=4)
    assert request.Offset == 4
    assert request.Limit == 100
    assert not hasattr(request, "InvokerIds")


def test_describe_request_filters_by_id():
    request = mod.describe_request(FakeModels(), _params(invoker_id="ivk-1"), offset=0)
    assert request.InvokerIds == ["ivk-1"]


def test_create_request_fields():
    models = FakeModels()
    p = _params(instance_ids=["ins-b", "ins-a"], parameters={"environment": "production"})
    request = mod.create_request(models, p)
    assert request.Name == "nightly-maintenance"
    assert request.Type == "SCHEDULE"
    assert request.CommandId == "cmd-8b0a1c2d"
    assert request.InstanceIds == ["ins-a", "ins-b"]  # sorted
    assert request.Username == "root"
    assert request.Parameters == PARAMS_JSON
    assert request.ScheduleSettings.Policy == "RECURRENCE"
    assert not hasattr(request, "InvokerId")


def test_update_request_carries_invoker_id():
    request = mod.update_request(FakeModels(), _params(), "ivk-8b0a1c2d")
    assert request.InvokerId == "ivk-8b0a1c2d"
    assert request.Name == "nightly-maintenance"


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), "ivk-8b0a1c2d")
    assert request.InvokerId == "ivk-8b0a1c2d"


def test_enable_request_selects_operation_class():
    enable = mod.enable_request(FakeModels(), "ivk-1", True)
    assert type(enable).__name__ == "EnableInvokerRequest"
    assert enable.InvokerId == "ivk-1"
    disable = mod.enable_request(FakeModels(), "ivk-1", False)
    assert type(disable).__name__ == "DisableInvokerRequest"
    assert disable.InvokerId == "ivk-1"


# ---------------------------------------------------------------------------
# comparable / desired / scrub
# ---------------------------------------------------------------------------


def test_schedule_dict_normalises_missing():
    assert mod._schedule_dict(None) == {"Policy": None, "Recurrence": None, "InvokeTime": None}
    assert mod._schedule_dict({"Policy": "ONCE", "InvokeTime": "t"}) == {
        "Policy": "ONCE",
        "Recurrence": None,
        "InvokeTime": "t",
    }


def test_comparable_digests_parameters_and_sorts_instances():
    value = mod.comparable(_invoker(InstanceIds=["ins-9c3d2e1f", "ins-8b0a1c2d"], Parameters='{"environment":"staging"}'))
    assert value["InstanceIds"] == ["ins-8b0a1c2d", "ins-9c3d2e1f"]
    assert value["Enable"] is True
    assert value["ParametersSha256"] == mod._digest({"environment": "staging"})
    assert "Parameters" not in value


def test_desired_matches_comparable_round_trip():
    remote = _invoker()
    p = _params()
    assert mod.comparable(remote) == mod.desired(p)


def test_desired_once_policy():
    value = mod.desired(_params(policy="ONCE", recurrence=None, invoke_time="2026-09-05T03:00:00Z"))
    assert value["ScheduleSettings"] == {"Policy": "ONCE", "Recurrence": None, "InvokeTime": "2026-09-05T03:00:00Z"}


def test_scrub_redacts_parameters():
    scrubbed = mod.scrub(_invoker())
    assert scrubbed["Parameters"] == "<redacted>"
    assert scrubbed["Name"] == "nightly-maintenance"
    assert "environment" not in json.dumps(scrubbed)


def test_scrub_none_passthrough():
    assert mod.scrub(None) is None


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeTatClient([_invoker()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="no-such-invoker"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_by_name(monkeypatch):
    fake = FakeTatClient([_invoker(), _invoker(InvokerId="ivk-2", Name="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="nightly-maintenance"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["InvokerId"] == "ivk-8b0a1c2d"


def test_find_by_invoker_id(monkeypatch):
    fake = FakeTatClient([_invoker(), _invoker(InvokerId="ivk-2", Name="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(invoker_id="ivk-2"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["Name"] == "other"


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeTatClient([_invoker(InvokerId="ivk-1"), _invoker(InvokerId="ivk-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="nightly-maintenance"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    assert "Multiple TAT invokers matched" in exc.value.args[0]["msg"]


def test_find_paginates_until_match(monkeypatch):
    invokers = [_invoker(InvokerId="ivk-bulk-%03d" % i, Name="bulk-%03d" % i) for i in range(150)]
    invokers.append(_invoker(InvokerId="ivk-last", Name="nightly-maintenance"))
    fake = FakeTatClient(invokers)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="nightly-maintenance"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["InvokerId"] == "ivk-last"
    list_calls = [c for c in fake.calls if c[0] == "DescribeInvokers"]
    assert len(list_calls) == 2  # page 1 (100) + page 2 (51)
    assert list_calls[0][1].Offset == 0
    assert list_calls[1][1].Offset == 100


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_one_of_enforced():
    module_args()  # neither invoker_id nor name
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_present_requires_name_command_and_instances():
    module_args(state="present", name="x")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name, command_id and instance_ids are required" in exc.value.args[0]["msg"]


def test_recurrence_policy_requires_recurrence():
    module_args(state="present", name="x", command_id="cmd-x", instance_ids=["ins-x"],
                policy="RECURRENCE", recurrence=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "recurrence is required" in exc.value.args[0]["msg"]


def test_once_policy_requires_invoke_time():
    module_args(state="present", name="x", command_id="cmd-x", instance_ids=["ins-x"],
                policy="ONCE", invoke_time=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "invoke_time is required" in exc.value.args[0]["msg"]


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TatClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args(name="nightly-maintenance", command_id="cmd-x", instance_ids=["ins-x"],
              recurrence="0 2 * * *")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_present_creates_enabled_invoker(monkeypatch):
    fake = FakeTatClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", name="nightly-maintenance", command_id="cmd-8b0a1c2d",
                instance_ids=["ins-8b0a1c2d", "ins-9c3d2e1f"], username="root",
                parameters={"environment": "production"}, policy="RECURRENCE", recurrence="0 2 * * *")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["invoker"]["InvokerId"] == "ivk-fake-001"
    assert result["invoker"]["Parameters"] == "<redacted>"
    names = [c[0] for c in fake.calls]
    assert names.count("CreateInvoker") == 1
    assert names.count("EnableInvoker") == 1  # create defaults enabled; toggle converges
    assert "DisableInvoker" not in names


def test_present_creates_disabled_invoker(monkeypatch):
    fake = FakeTatClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", name="nightly-maintenance", command_id="cmd-8b0a1c2d",
                instance_ids=["ins-8b0a1c2d", "ins-9c3d2e1f"], enabled=False,
                policy="RECURRENCE", recurrence="0 2 * * *")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["invoker"]["Enable"] is False
    names = [c[0] for c in fake.calls]
    assert names.count("CreateInvoker") == 1
    assert names.count("DisableInvoker") == 1
    assert "EnableInvoker" not in names


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeTatClient([_invoker()])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="nightly-maintenance", command_id="cmd-8b0a1c2d",
                instance_ids=["ins-8b0a1c2d", "ins-9c3d2e1f"], username="root",
                parameters={"environment": "production"}, policy="RECURRENCE", recurrence="0 2 * * *")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["invoker"]["Parameters"] == "<redacted>"
    names = [c[0] for c in fake.calls]
    assert "CreateInvoker" not in names
    assert "ModifyInvoker" not in names
    assert "EnableInvoker" not in names


def test_present_name_drift_triggers_update(monkeypatch):
    fake = FakeTatClient([_invoker()])
    _make_module(monkeypatch, fake)
    # Renaming requires referencing the existing invoker by id; by name alone
    # the module would treat the new name as a brand-new invoker.
    module_args(state="present", invoker_id="ivk-8b0a1c2d", name="renamed-maintenance",
                command_id="cmd-8b0a1c2d",
                instance_ids=["ins-8b0a1c2d", "ins-9c3d2e1f"], username="root",
                parameters={"environment": "production"}, policy="RECURRENCE", recurrence="0 2 * * *")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["invoker"]["Name"] == "renamed-maintenance"
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyInvoker") == 1
    modify = [c for c in fake.calls if c[0] == "ModifyInvoker"][0][1]
    assert modify.InvokerId == "ivk-8b0a1c2d"
    # no enable change -> no toggle call after the modify
    assert "EnableInvoker" not in names
    assert "DisableInvoker" not in names


def test_present_parameters_drift_triggers_update(monkeypatch):
    fake = FakeTatClient([_invoker()])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="nightly-maintenance", command_id="cmd-8b0a1c2d",
                instance_ids=["ins-8b0a1c2d", "ins-9c3d2e1f"], username="root",
                parameters={"environment": "staging"}, policy="RECURRENCE", recurrence="0 2 * * *")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["invoker"]["Parameters"] == "<redacted>"
    assert "environment" not in str(result)
    assert "ModifyInvoker" in [c[0] for c in fake.calls]


def test_present_enable_drift_triggers_enable_call(monkeypatch):
    fake = FakeTatClient([_invoker(Enable=False)])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="nightly-maintenance", command_id="cmd-8b0a1c2d",
                instance_ids=["ins-8b0a1c2d", "ins-9c3d2e1f"], username="root",
                parameters={"environment": "production"}, policy="RECURRENCE", recurrence="0 2 * * *",
                enabled=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["invoker"]["Enable"] is True
    names = [c[0] for c in fake.calls]
    assert names.count("EnableInvoker") == 1
    assert "DisableInvoker" not in names


def test_present_disable_drift_triggers_disable_call(monkeypatch):
    fake = FakeTatClient([_invoker(Enable=True)])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="nightly-maintenance", command_id="cmd-8b0a1c2d",
                instance_ids=["ins-8b0a1c2d", "ins-9c3d2e1f"], username="root",
                parameters={"environment": "production"}, policy="RECURRENCE", recurrence="0 2 * * *",
                enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["invoker"]["Enable"] is False
    names = [c[0] for c in fake.calls]
    assert names.count("DisableInvoker") == 1


def test_present_creates_once_invoker(monkeypatch):
    fake = FakeTatClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", name="one-off-patch", command_id="cmd-x",
                instance_ids=["ins-x"], username="root",
                policy="ONCE", invoke_time="2026-09-05T03:00:00Z")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["invoker"]["ScheduleSettings"]["Policy"] == "ONCE"
    create = [c for c in fake.calls if c[0] == "CreateInvoker"][0][1]
    assert create.ScheduleSettings.Policy == "ONCE"
    assert create.ScheduleSettings.InvokeTime == "2026-09-05T03:00:00Z"
    assert create.ScheduleSettings.Recurrence is None


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTatClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="present", name="nightly-maintenance",
                command_id="cmd-x", instance_ids=["ins-x"], recurrence="0 2 * * *")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["invoker"] is None
    assert not any("CreateInvoker" == c[0] for c in fake.calls)


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeTatClient([_invoker()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="present", invoker_id="ivk-8b0a1c2d",
                name="renamed-maintenance",
                command_id="cmd-8b0a1c2d", instance_ids=["ins-8b0a1c2d", "ins-9c3d2e1f"],
                username="root", parameters={"environment": "production"},
                policy="RECURRENCE", recurrence="0 2 * * *")
    result = run(mod.run_module)
    assert result["changed"] is True
    # No write happened, so the reported invoker is the pre-change state.
    assert result["invoker"]["Name"] == "nightly-maintenance"
    assert not any(n.startswith("Modify") or n.startswith("Enable") or n.startswith("Disable")
                   for n, _ in fake.calls)


def test_absent_removes_invoker(monkeypatch):
    fake = FakeTatClient([_invoker()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="nightly-maintenance")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["invoker"] is None
    names = [c[0] for c in fake.calls]
    assert names.count("DeleteInvoker") == 1
    delete = [c for c in fake.calls if c[0] == "DeleteInvoker"][0][1]
    assert delete.InvokerId == "ivk-8b0a1c2d"
    assert fake.invokers == []


def test_absent_by_invoker_id_removes(monkeypatch):
    fake = FakeTatClient([_invoker(InvokerId="ivk-1", Name="a"), _invoker(InvokerId="ivk-2", Name="b")])
    _make_module(monkeypatch, fake)
    module_args(state="absent", invoker_id="ivk-2")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert [i["InvokerId"] for i in fake.invokers] == ["ivk-1"]


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeTatClient([_invoker()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="no-such-invoker")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["invoker"] is None
    assert not any("DeleteInvoker" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTatClient([_invoker()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", name="nightly-maintenance")
    result = run(mod.run_module)
    assert result["changed"] is True
    # Pre-change state is reported with parameters redacted.
    assert result["invoker"]["Parameters"] == "<redacted>"
    assert not any("DeleteInvoker" == c[0] for c in fake.calls)
    assert len(fake.invokers) == 1
