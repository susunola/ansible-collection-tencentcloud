"""Unit tests for the trabbit_serverless_user write module (helpers + run_module).

Creates, updates and deletes a RabbitMQ Serverless instance user. Lookup
is a single DescribeRabbitMQServerlessUser call filtered by ``User``; the
module fails when the response contains more than one matching entry and
strips the password from the metadata it returns. Passwords are only ever
sent on create or when ``rotate_password`` is explicitly requested, and
unset ``max_connections``/``max_channels`` fall back to the remote value
so omitting them never causes drift.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import trabbit_serverless_user as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _user(**overrides):
    """API-shaped RabbitMQ Serverless user dict; fresh copy per call."""
    item = {
        "User": "application",
        "Description": "",
        "Tags": [],
        "MaxConnections": None,
        "MaxChannels": None,
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "instance_id": "amqp-abc123",
        "name": "application",
        "password": None,
        "rotate_password": False,
        "description": "",
        "tags": [],
        "max_connections": None,
        "max_channels": None,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    return module_args(**{k: v for k, v in _params(**extra).items() if v is not None})


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


class FakeTrabbitClient(object):
    """In-memory TrabbitClient stand-in storing user dicts.

    DescribeRabbitMQServerlessUser ignores the request's ``User`` filter
    and returns every user of the instance so the module's own match and
    multi-match guard are exercised. Create/Modify write back the request
    attributes the ``_apply`` helper placed on the model.
    """

    def __init__(self, users=None):
        self.users = [dict(u) for u in (users or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _instance_items(self, instance_id):
        return [u for u in self.users if u.get("_instance") == instance_id]

    @staticmethod
    def _serializable(user):
        return {k: v for k, v in user.items() if not k.startswith("_")}

    def DescribeRabbitMQServerlessUser(self, request):
        self._record("DescribeRabbitMQServerlessUser", request)
        items = self._instance_items(request.InstanceId)
        return SimpleNamespace(
            RabbitMQUserList=[FakeResource(self._serializable(u)) for u in items],
            RequestId="req-fake",
        )

    def CreateRabbitMQServerlessUser(self, request):
        self._record("CreateRabbitMQServerlessUser", request)
        self.users.append({
            "_instance": request.InstanceId,
            "User": request.User,
            "Password": getattr(request, "Password", None),
            "Description": request.Description,
            "Tags": list(request.Tags or []),
            "MaxConnections": request.MaxConnections,
            "MaxChannels": request.MaxChannels,
        })
        return SimpleNamespace(RequestId="req-fake")

    def ModifyRabbitMQServerlessUser(self, request):
        self._record("ModifyRabbitMQServerlessUser", request)
        for user in self._instance_items(request.InstanceId):
            if user.get("User") == request.User:
                if hasattr(request, "Password"):
                    user["Password"] = request.Password
                user["Description"] = request.Description
                user["Tags"] = list(request.Tags or [])
                # None-valued fields are omitted from the SDK payload, so an
                # unset limit never clobbers the remote value.
                if request.MaxConnections is not None:
                    user["MaxConnections"] = request.MaxConnections
                if request.MaxChannels is not None:
                    user["MaxChannels"] = request.MaxChannels
        return SimpleNamespace(RequestId="req-fake")

    def DeleteRabbitMQServerlessUser(self, request):
        self._record("DeleteRabbitMQServerlessUser", request)
        self.users = [
            u for u in self.users
            if u.get("_instance") != request.InstanceId or u.get("User") != request.User
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TrabbitClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def _store(fake, user, instance="amqp-abc123"):
    """Store an API-shaped user dict under an instance identity."""
    record = dict(user)
    record["_instance"] = instance
    fake.users.append(record)


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# request-builder / comparable / desired tests
# ---------------------------------------------------------------------------


def test_describe_request_fields():
    request = mod.describe_request(FakeModels(), _params(), offset=20)
    assert request.InstanceId == "amqp-abc123"
    assert request.User == "application"
    assert request.Offset == 20
    assert request.Limit == 100


def test_describe_request_default_offset_is_zero():
    request = mod.describe_request(FakeModels(), _params())
    assert request.Offset == 0


def test_create_request_fields():
    request = mod.create_request(FakeModels(), _params(
        password="s3cret",
        description="App user",
        tags=["monitor", "management", "monitor"],
        max_connections=50,
        max_channels=200,
    ))
    assert request.InstanceId == "amqp-abc123"
    assert request.User == "application"
    assert request.Password == "s3cret"
    assert request.Description == "App user"
    assert request.Tags == ["management", "monitor"]  # sorted + de-duplicated
    assert request.MaxConnections == 50
    assert request.MaxChannels == 200


def test_update_request_omits_password_without_rotate():
    request = mod.update_request(FakeModels(), _params(password="s3cret"))
    assert request.InstanceId == "amqp-abc123"
    assert request.User == "application"
    assert not hasattr(request, "Password")  # password is not re-sent on drift-only updates


def test_update_request_includes_password_when_rotating():
    request = mod.update_request(FakeModels(), _params(rotate_password=True, password="newpass"))
    assert request.Password == "newpass"


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params())
    assert request.InstanceId == "amqp-abc123"
    assert request.User == "application"


def test_comparable_normalizes_scalars_and_tags():
    value = mod.comparable({
        "User": "application",
        "Description": None,
        "Tags": ["monitor", "management"],
        "MaxConnections": None,
        "MaxChannels": 100,
        "Password": "hidden",
    })
    assert value == {
        "User": "application",
        "Description": "",
        "Tags": ["management", "monitor"],
        "MaxConnections": None,
        "MaxChannels": 100,
    }


def test_desired_matches_params():
    assert mod.desired(_params(description="App user", tags=["monitor"])) == {
        "User": "application",
        "Description": "App user",
        "Tags": ["monitor"],
        "MaxConnections": None,
        "MaxChannels": None,
    }


def test_desired_falls_back_to_current_for_unset_limits():
    current = _user(MaxConnections=50, MaxChannels=200)
    target = mod.desired(_params(), current)
    assert target["MaxConnections"] == 50
    assert target["MaxChannels"] == 200


def test_desired_explicit_limits_override_current():
    current = _user(MaxConnections=50, MaxChannels=200)
    target = mod.desired(_params(max_connections=10, max_channels=20), current)
    assert target["MaxConnections"] == 10
    assert target["MaxChannels"] == 20


def test_desired_sorts_and_dedupes_tags():
    target = mod.desired(_params(tags=["monitor", "management", "monitor"]))
    assert target["Tags"] == ["management", "monitor"]


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_matches_user_and_strips_password(monkeypatch):
    fake = FakeTrabbitClient()
    _store(fake, _user(User="other", Password="pw"))
    _store(fake, _user(User="application", Password="pw", Description="App"))
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["User"] == "application"
    assert value["Description"] == "App"
    assert "Password" not in value


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeTrabbitClient()
    _store(fake, _user(User="other"))
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(name="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_other_instance_is_isolated(monkeypatch):
    fake = FakeTrabbitClient()
    _store(fake, _user(User="application"), instance="amqp-other")
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeTrabbitClient()
    _store(fake, _user(User="application", Description="one"))
    _store(fake, _user(User="application", Description="two"))
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    assert "Multiple RabbitMQ Serverless users matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_rotate_password_requires_password():
    _run_args(rotate_password=True, password=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password is required when rotate_password=true" in exc.value.args[0]["msg"]


def test_present_creates_user(monkeypatch):
    fake = FakeTrabbitClient()
    _make_module(monkeypatch, fake)
    _run_args(password="s3cret", description="App user", tags=["monitor"])
    result = run(mod.run_module)
    assert result["changed"] is True
    user = result["user"]
    assert user["User"] == "application"
    assert user["Description"] == "App user"
    assert user["Tags"] == ["monitor"]
    assert "Password" not in user  # metadata never carries the password
    assert [c[0] for c in fake.calls].count("DescribeRabbitMQServerlessUser") == 2  # find + refetch
    create = [c for c in fake.calls if c[0] == "CreateRabbitMQServerlessUser"][0][1]
    assert create.Password == "s3cret"
    assert create.Tags == ["monitor"]


def test_present_create_requires_password(monkeypatch):
    fake = FakeTrabbitClient()
    _make_module(monkeypatch, fake)
    _run_args(password=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password is required when creating a RabbitMQ Serverless user" in exc.value.args[0]["msg"]
    assert not any(c[0] == "CreateRabbitMQServerlessUser" for c in fake.calls)


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeTrabbitClient()
    _store(fake, _user())
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["user"]["User"] == "application"
    assert not any(c[0].startswith("Create") or c[0].startswith("Modify") for c in fake.calls)


def test_present_description_drift_triggers_update(monkeypatch):
    fake = FakeTrabbitClient()
    _store(fake, _user(Description="old"))
    _make_module(monkeypatch, fake)
    _run_args(description="new", password="s3cret")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["Description"] == "new"
    update = [c for c in fake.calls if c[0] == "ModifyRabbitMQServerlessUser"][0][1]
    assert update.Description == "new"
    assert not hasattr(update, "Password")  # drift-only update re-sends nothing secret


def test_present_tags_drift_triggers_update(monkeypatch):
    fake = FakeTrabbitClient()
    _store(fake, _user(Tags=["monitor"]))
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["Tags"] == []
    update = [c for c in fake.calls if c[0] == "ModifyRabbitMQServerlessUser"][0][1]
    assert update.Tags == []


def test_present_limit_drift_triggers_update(monkeypatch):
    fake = FakeTrabbitClient()
    _store(fake, _user(MaxConnections=50, MaxChannels=100))
    _make_module(monkeypatch, fake)
    _run_args(max_connections=200)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["MaxConnections"] == 200
    assert result["user"]["MaxChannels"] == 100  # unset limit preserved
    update = [c for c in fake.calls if c[0] == "ModifyRabbitMQServerlessUser"][0][1]
    assert update.MaxConnections == 200
    assert update.MaxChannels is None  # unset limit is omitted from the payload


def test_present_unset_limit_matching_current_is_noop(monkeypatch):
    fake = FakeTrabbitClient()
    _store(fake, _user(MaxConnections=50))
    _make_module(monkeypatch, fake)
    _run_args()  # max_connections unset -> falls back to current 50
    result = run(mod.run_module)
    assert result["changed"] is False
    assert not any(c[0].startswith("Create") or c[0].startswith("Modify") for c in fake.calls)


def test_present_rotate_password_updates(monkeypatch):
    fake = FakeTrabbitClient()
    _store(fake, _user())
    _make_module(monkeypatch, fake)
    _run_args(rotate_password=True, password="newpass")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["User"] == "application"
    update = [c for c in fake.calls if c[0] == "ModifyRabbitMQServerlessUser"][0][1]
    assert update.Password == "newpass"


def test_present_password_without_rotate_is_noop(monkeypatch):
    fake = FakeTrabbitClient()
    _store(fake, _user())
    _make_module(monkeypatch, fake)
    _run_args(password="newpass")  # rotate_password defaults false
    result = run(mod.run_module)
    assert result["changed"] is False
    assert not any(c[0].startswith("Create") or c[0].startswith("Modify") for c in fake.calls)


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeTrabbitClient()
    _store(fake, _user(Description="old"))
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, description="new")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["Description"] == "old"  # pre-change state reported
    assert result["diff"]["after"]["Description"] == "new"
    assert not any(c[0].startswith("Create") or c[0].startswith("Modify") for c in fake.calls)


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTrabbitClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, password="s3cret")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"] is None  # nothing was created to report
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["User"] == "application"
    assert not any(c[0] == "CreateRabbitMQServerlessUser" for c in fake.calls)
    assert fake.users == []


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeTrabbitClient()
    _store(fake, _user(User="other"))
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["user"] is None
    assert not any(c[0] == "DeleteRabbitMQServerlessUser" for c in fake.calls)


def test_absent_deletes_user(monkeypatch):
    fake = FakeTrabbitClient()
    _store(fake, _user(User="application"))
    _store(fake, _user(User="other"))
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteRabbitMQServerlessUser"][0][1]
    assert delete.InstanceId == "amqp-abc123"
    assert delete.User == "application"
    assert [u["User"] for u in fake.users] == ["other"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTrabbitClient()
    _store(fake, _user(User="application"))
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["User"] == "application"  # pre-delete state reported
    assert result["diff"]["after"] is None
    assert not any(c[0] == "DeleteRabbitMQServerlessUser" for c in fake.calls)
    assert len(fake.users) == 1


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TrabbitClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args(password="s3cret")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeTrabbitClient()
    _store(fake, _user(User="application"))
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.main)
    assert result["changed"] is False
    assert result["user"]["User"] == "application"
