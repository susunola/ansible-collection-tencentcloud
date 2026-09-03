"""Unit tests for the tdmq_rabbitmq_user write module (helpers + run_module).

Creates, updates and deletes TDMQ RabbitMQ users. Users are looked up by
name through a paginated DescribeRabbitMQUser walk. The password is never
compared: it is sent at creation, or on update only when
rotate_password=true (explicit rotation always reports changed). Creation
demands a password, optional max_connections/max_channels are omitted
from requests when unset, and tags are deduplicated and sorted.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tdmq_rabbitmq_user as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
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


def _user(**overrides):
    """API-shaped RabbitMQ user dict; fresh copy per call."""
    item = {
        "User": "application",
        "Description": "",
        "Tags": [],
        "MaxConnections": None,
        "MaxChannels": None,
        "CamAuthEnabled": False,
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "instance_id": "amqp-abc",
        "name": "application",
        "password": None,
        "rotate_password": False,
        "description": "",
        "tags": [],
        "max_connections": None,
        "max_channels": None,
        "cam_auth_enabled": False,
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


class FakeTdmqClient(object):
    """In-memory TdmqClient stand-in storing RabbitMQ user dicts.

    DescribeRabbitMQUser returns one page (Limit 100) of every stored
    user with a TotalCount so the module's pagination walk runs; the
    module re-filters by name client-side. Create/Modify mirror the
    module's request field conventions (optional Max* attributes are only
    applied when present) and Delete removes by name.
    """

    def __init__(self, users=None):
        self.users = [dict(u) for u in (users or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeRabbitMQUser(self, request):
        self._record("DescribeRabbitMQUser", request)
        offset = request.Offset
        limit = request.Limit
        page = self.users[offset:offset + limit]
        return SimpleNamespace(
            RabbitMQUserList=[FakeResource(dict(u)) for u in page],
            TotalCount=len(self.users),
            RequestId="req-fake",
        )

    def _apply(self, request, user):
        user["Description"] = request.Description
        user["Tags"] = list(request.Tags)
        if hasattr(request, "MaxConnections"):
            user["MaxConnections"] = request.MaxConnections
        if hasattr(request, "MaxChannels"):
            user["MaxChannels"] = request.MaxChannels
        user["CamAuthEnabled"] = request.EnableCamAuth

    def CreateRabbitMQUser(self, request):
        self._record("CreateRabbitMQUser", request)
        stored = {
            "User": request.User,
            "Description": "",
            "Tags": [],
            "MaxConnections": None,
            "MaxChannels": None,
            "CamAuthEnabled": False,
        }
        self._apply(request, stored)
        self.users.append(stored)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyRabbitMQUser(self, request):
        self._record("ModifyRabbitMQUser", request)
        for user in self.users:
            if user["User"] == request.User:
                self._apply(request, user)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteRabbitMQUser(self, request):
        self._record("DeleteRabbitMQUser", request)
        self.users = [u for u in self.users if u["User"] != request.User]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TdmqClient=object)),
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
# request-builder / helper tests
# ---------------------------------------------------------------------------


def test_describe_request_builds_paged_request():
    request = mod.describe_request(FakeModels(), _params(), offset=0)
    assert request.InstanceId == "amqp-abc"
    assert request.User == "application"
    assert request.Offset == 0
    assert request.Limit == 100
    request = mod.describe_request(FakeModels(), _params(), offset=100)
    assert request.Offset == 100


def test_create_request_carries_password_and_fields():
    request = mod.create_request(
        FakeModels(),
        _params(
            password="s3cret",
            description="api user",
            tags=["management", "monitoring", "management"],
            max_connections=100,
            max_channels=50,
            cam_auth_enabled=True,
        ),
    )
    assert request.InstanceId == "amqp-abc"
    assert request.User == "application"
    assert request.Password == "s3cret"
    assert request.Description == "api user"
    assert request.Tags == ["management", "monitoring"]
    assert request.MaxConnections == 100
    assert request.MaxChannels == 50
    assert request.EnableCamAuth is True


def test_create_request_without_password_sets_none():
    request = mod.create_request(FakeModels(), _params())
    assert request.Password is None
    assert not hasattr(request, "MaxConnections")
    assert not hasattr(request, "MaxChannels")
    assert request.EnableCamAuth is False


def test_update_request_omits_password_without_rotation():
    request = mod.update_request(FakeModels(), _params(description="tuned"))
    assert request.InstanceId == "amqp-abc"
    assert request.User == "application"
    assert not hasattr(request, "Password")


def test_update_request_rotates_password():
    request = mod.update_request(
        FakeModels(), _params(rotate_password=True, password="new-secret")
    )
    assert request.Password == "new-secret"


def test_update_request_carries_optional_max_fields():
    request = mod.update_request(
        FakeModels(), _params(max_connections=200, max_channels=80)
    )
    assert request.MaxConnections == 200
    assert request.MaxChannels == 80


def test_delete_request_carries_identity():
    request = mod.delete_request(FakeModels(), _params())
    assert request.InstanceId == "amqp-abc"
    assert request.User == "application"


def test_comparable_normalizes_missing_values():
    value = mod.comparable({"User": "application"})
    assert value == {
        "User": "application",
        "Description": "",
        "Tags": [],
        "MaxConnections": None,
        "MaxChannels": None,
        "CamAuthEnabled": False,
    }


def test_comparable_sorts_tags_and_coerces_cam():
    value = mod.comparable(
        _user(Tags=["b", "a"], CamAuthEnabled=1, Description="x")
    )
    assert value["Tags"] == ["a", "b"]
    assert value["CamAuthEnabled"] is True
    assert value["Description"] == "x"


def test_desired_uses_params_when_given():
    value = mod.desired(
        _params(
            description="d",
            tags=["b", "a", "b"],
            max_connections=10,
            max_channels=20,
            cam_auth_enabled=True,
        ),
        _user(),
    )
    assert value == {
        "User": "application",
        "Description": "d",
        "Tags": ["a", "b"],
        "MaxConnections": 10,
        "MaxChannels": 20,
        "CamAuthEnabled": True,
    }


def test_desired_falls_back_to_current_max_fields():
    current = _user(MaxConnections=300, MaxChannels=120)
    value = mod.desired(_params(), current)
    assert value["MaxConnections"] == 300
    assert value["MaxChannels"] == 120


def test_find_by_name(monkeypatch):
    fake = FakeTdmqClient([_user(), _user(User="other")])
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["User"] == "application"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeTdmqClient([_user(User="other")])
    module = FakeModule(_params())
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_paginates_until_match(monkeypatch):
    users = [_user(User="bulk-%d" % i) for i in range(150)]
    fake = FakeTdmqClient(users)
    module = FakeModule(_params(name="bulk-130"))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["User"] == "bulk-130"
    assert len(module.sdk_calls) == 2


def test_find_paginates_and_returns_none(monkeypatch):
    users = [_user(User="bulk-%d" % i) for i in range(150)]
    fake = FakeTdmqClient(users)
    module = FakeModule(_params(name="absent"))
    assert mod.find(module, fake, FakeModels(), module.params) is None
    assert len(module.sdk_calls) == 2


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_rotation_without_password_fails(monkeypatch):
    fake = FakeTdmqClient()
    _make_module(monkeypatch, fake)
    _run_args(rotate_password=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password is required when rotate_password=true" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_absent_noop_when_missing(monkeypatch):
    fake = FakeTdmqClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["user"] is None
    assert [c[0] for c in fake.calls] == ["DescribeRabbitMQUser"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakeTdmqClient([_user()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["User"] == "application"
    assert result["diff"]["before"]["User"] == "application"
    assert result["diff"]["after"] is None
    assert [c[0] for c in fake.calls] == ["DescribeRabbitMQUser"]
    assert len(fake.users) == 1


def test_absent_deletes_user(monkeypatch):
    fake = FakeTdmqClient([_user()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"] is None
    assert [c[0] for c in fake.calls] == ["DescribeRabbitMQUser", "DeleteRabbitMQUser"]
    assert fake.calls[1][1].User == "application"
    assert fake.users == []


def test_present_requires_password_when_creating(monkeypatch):
    fake = FakeTdmqClient()
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password is required when creating a RabbitMQ user" in exc.value.args[0]["msg"]
    assert [c[0] for c in fake.calls] == ["DescribeRabbitMQUser"]


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTdmqClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"] is None
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["User"] == "application"
    assert [c[0] for c in fake.calls] == ["DescribeRabbitMQUser"]
    assert fake.users == []


def test_present_creates_user(monkeypatch):
    fake = FakeTdmqClient()
    _make_module(monkeypatch, fake)
    _run_args(
        password="s3cret",
        description="api",
        tags=["management"],
        max_connections=100,
        cam_auth_enabled=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["User"] == "application"
    assert result["user"]["MaxConnections"] == 100
    assert result["user"]["CamAuthEnabled"] is True
    assert [c[0] for c in fake.calls] == [
        "DescribeRabbitMQUser",
        "CreateRabbitMQUser",
        "DescribeRabbitMQUser",
    ]
    created = fake.calls[1][1]
    assert created.InstanceId == "amqp-abc"
    assert created.User == "application"
    assert created.Password == "s3cret"
    assert created.Tags == ["management"]
    assert created.MaxConnections == 100
    assert created.EnableCamAuth is True
    assert len(fake.users) == 1


def test_present_noop_when_user_matches(monkeypatch):
    fake = FakeTdmqClient([_user()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["user"]["User"] == "application"
    assert [c[0] for c in fake.calls] == ["DescribeRabbitMQUser"]


def test_present_rotates_password_on_existing_user(monkeypatch):
    fake = FakeTdmqClient([_user()])
    _make_module(monkeypatch, fake)
    _run_args(rotate_password=True, password="new-secret")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["User"] == "application"
    assert [c[0] for c in fake.calls] == [
        "DescribeRabbitMQUser",
        "ModifyRabbitMQUser",
        "DescribeRabbitMQUser",
    ]
    updated = fake.calls[1][1]
    assert updated.Password == "new-secret"
    assert updated.InstanceId == "amqp-abc"


def test_present_check_mode_rotation_is_dry_run(monkeypatch):
    fake = FakeTdmqClient([_user()])
    _make_module(monkeypatch, fake)
    _run_args(rotate_password=True, password="new-secret", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["User"] == "application"
    assert [c[0] for c in fake.calls] == ["DescribeRabbitMQUser"]
    assert len(fake.users) == 1


def test_present_updates_description_drift(monkeypatch):
    fake = FakeTdmqClient([_user(Description="old")])
    _make_module(monkeypatch, fake)
    _run_args(description="new")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["Description"] == "new"
    assert [c[0] for c in fake.calls] == [
        "DescribeRabbitMQUser",
        "ModifyRabbitMQUser",
        "DescribeRabbitMQUser",
    ]
    updated = fake.calls[1][1]
    assert not hasattr(updated, "Password")
    assert updated.Description == "new"


def test_present_updates_max_connections_drift(monkeypatch):
    fake = FakeTdmqClient([_user(MaxConnections=100)])
    _make_module(monkeypatch, fake)
    _run_args(max_connections=250)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["MaxConnections"] == 250
    assert fake.calls[1][1].MaxConnections == 250


def test_present_updates_cam_auth_drift(monkeypatch):
    fake = FakeTdmqClient([_user(CamAuthEnabled=True)])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["user"]["CamAuthEnabled"] is False
    assert fake.calls[1][1].EnableCamAuth is False


def test_sdk_failure_reports_error_payload(monkeypatch):
    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "auth rejected"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeTdmqClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.main)
    assert result["changed"] is False
    assert result["user"] is None
