"""Unit tests for the mongodb_account write module (helpers + run_module).

Covers the create / role-reconcile / password-rotate / destroy flows of
``plugins/modules/mongodb_account.py`` with an in-memory fake MongoDB
client whose write operations mutate the account store, so the module's
post-write ``find`` refetch converges immediately. Accounts are matched by
``UserName`` against the flat DescribeAccountUsers ``Users`` list; roles use
the numeric Mask coding (none/read/read_write -> 0/1/3) and are sorted in
comparable form. UserDesc is immutable after creation. ``rotate_password``
explicitly calls ResetDBInstancePassword; create and delete both require the
built-in ``mongo_user_password``. In check mode a would-be create reports
``account=None`` and a would-be update the pre-change account.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import mongodb_account as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

USER = {
    "UserName": "app",
    "UserDesc": "",
    "AuthRole": [{"NameSpace": "orders", "Mask": 3}],
}


def _user(**overrides):
    """API-shaped account dict isolated from the shared constant."""
    item = copy.deepcopy(USER)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec."""
    params = {
        "state": "present",
        "instance_id": "cmgo-1",
        "username": "app",
        "password": "s3cret",
        "rotate_password": False,
        "mongo_user_password": "mongo-secret",
        "description": "",
        "roles": [{"namespace": "orders", "access": "read_write"}],
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter (None dropped)."""
    args = dict(_params())
    args.update(extra)
    return module_args(**{k: v for k, v in args.items() if v is not None})


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


class FakeMongodbClient(object):
    """In-memory MongodbClient stand-in for accounts.

    Stores API-shaped account dicts keyed by UserName; DescribeAccountUsers
    returns the whole store under ``Users``. Write operations mutate the
    store so post-write refetches converge.
    """

    def __init__(self, users=None):
        self.users = [copy.deepcopy(u) for u in (users or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _roles(self, auth_role):
        return [{"NameSpace": r.NameSpace, "Mask": r.Mask} for r in (auth_role or [])]

    def DescribeAccountUsers(self, request):
        self._record("DescribeAccountUsers", request)
        return SimpleNamespace(Users=[FakeResource(dict(u)) for u in self.users], RequestId="req-fake")

    def CreateAccountUser(self, request):
        self._record("CreateAccountUser", request)
        self.users.append(
            {
                "UserName": request.UserName,
                "UserDesc": request.UserDesc,
                "AuthRole": self._roles(request.AuthRole),
            }
        )
        return SimpleNamespace(RequestId="req-fake")

    def SetAccountUserPrivilege(self, request):
        self._record("SetAccountUserPrivilege", request)
        for stored in self.users:
            if stored.get("UserName") == request.UserName:
                stored["AuthRole"] = self._roles(request.AuthRole)
        return SimpleNamespace(RequestId="req-fake")

    def ResetDBInstancePassword(self, request):
        self._record("ResetDBInstancePassword", request)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteAccountUser(self, request):
        self._record("DeleteAccountUser", request)
        self.users = [u for u in self.users if u.get("UserName") != request.UserName]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(MongodbClient=object)),
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
# request-builder / normalisation helper tests
# ---------------------------------------------------------------------------


def test_auth_roles_maps_access_to_mask():
    items = mod.auth_roles(FakeModels(), [{"namespace": "a", "access": "read"}, {"namespace": "b", "access": "read_write"}, {"namespace": "c", "access": "none"}])
    masks = {i.NameSpace: i.Mask for i in items}
    assert masks == {"a": 1, "b": 3, "c": 0}


def test_describe_request_fields():
    request = mod.describe_request(FakeModels(), "cmgo-1")
    assert request.InstanceId == "cmgo-1"


def test_create_request_fields():
    request = mod.create_request(FakeModels(), _params(description="svc"))
    assert request.InstanceId == "cmgo-1"
    assert request.UserName == "app"
    assert request.Password == "s3cret"
    assert request.MongoUserPassword == "mongo-secret"
    assert request.UserDesc == "svc"
    assert [(r.NameSpace, r.Mask) for r in request.AuthRole] == [("orders", 3)]


def test_privilege_request_fields():
    request = mod.privilege_request(FakeModels(), _params(roles=[{"namespace": "billing", "access": "read"}]))
    assert request.InstanceId == "cmgo-1"
    assert request.UserName == "app"
    assert [(r.NameSpace, r.Mask) for r in request.AuthRole] == [("billing", 1)]


def test_password_request_fields():
    request = mod.password_request(FakeModels(), _params(password="new-secret"))
    assert request.InstanceId == "cmgo-1"
    assert request.UserName == "app"
    assert request.Password == "new-secret"


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params())
    assert request.InstanceId == "cmgo-1"
    assert request.UserName == "app"
    assert request.MongoUserPassword == "mongo-secret"


def test_normalized_roles_maps_masks_to_access():
    values = mod.normalized_roles(
        [
            {"NameSpace": "c", "Mask": 0},
            {"NameSpace": "a", "Mask": 1},
            {"NameSpace": "b", "Mask": 3},
        ]
    )
    assert values == [
        {"namespace": "a", "access": "read"},
        {"namespace": "b", "access": "read_write"},
        {"namespace": "c", "access": "none"},
    ]


def test_normalized_roles_handles_sdk_objects_and_unknown_mask():
    item = SimpleNamespace(_serialize=lambda allow_none=True: {"NameSpace": "x", "Mask": 7})
    assert mod.normalized_roles([item]) == [{"namespace": "x", "access": 7}]
    assert mod.normalized_roles(None) == []


def test_comparable_normalises_desc_and_roles():
    value = mod.comparable(_user(UserDesc=None))
    assert value["UserName"] == "app"
    assert value["UserDesc"] == ""
    assert value["AuthRole"] == [{"namespace": "orders", "access": "read_write"}]


def test_desired_maps_roles():
    value = mod.desired(_params(roles=[{"namespace": "billing", "access": "read"}]))
    assert value == {"UserName": "app", "UserDesc": "", "AuthRole": [{"namespace": "billing", "access": "read"}]}


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_by_username(monkeypatch):
    fake = FakeMongodbClient([_user(UserName="other"), _user()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["UserName"] == "app"
    assert [c[0] for c in fake.calls] == ["DescribeAccountUsers"]


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeMongodbClient([_user()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(username="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_required_if_roles_when_present():
    module_args(instance_id="cmgo-1", username="app")  # state present without roles
    with pytest.raises(AnsibleFailJson):
        run(mod.run_module)


def test_rotate_requires_password():
    module_args(instance_id="cmgo-1", username="app", rotate_password=True, roles=[{"namespace": "orders", "access": "read_write"}])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password is required when rotate_password=true" in exc.value.args[0]["msg"]


def test_present_creates_account(monkeypatch):
    fake = FakeMongodbClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    account = result["account"]
    assert account["UserName"] == "app"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeAccountUsers") == 2  # find + refetch
    assert names.count("CreateAccountUser") == 1
    create = [c for c in fake.calls if c[0] == "CreateAccountUser"][0][1]
    assert create.Password == "s3cret"
    assert create.MongoUserPassword == "mongo-secret"


def test_present_create_requires_passwords(monkeypatch):
    fake = FakeMongodbClient()
    _make_module(monkeypatch, fake)
    _run_args(password=None, mongo_user_password=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "password and mongo_user_password are required when creating a MongoDB account" in exc.value.args[0]["msg"]
    assert not any("CreateAccountUser" == c[0] for c in fake.calls)


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeMongodbClient([_user()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account"]["UserName"] == "app"
    names = [c[0] for c in fake.calls]
    assert "SetAccountUserPrivilege" not in names
    assert "ResetDBInstancePassword" not in names
    assert "CreateAccountUser" not in names


def test_present_roles_drift_triggers_privilege_update(monkeypatch):
    fake = FakeMongodbClient([_user()])
    _make_module(monkeypatch, fake)
    _run_args(roles=[{"namespace": "billing", "access": "read"}])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["AuthRole"] == [{"NameSpace": "billing", "Mask": 1}]
    names = [c[0] for c in fake.calls]
    assert names.count("SetAccountUserPrivilege") == 1
    assert "ResetDBInstancePassword" not in names
    privilege = [c for c in fake.calls if c[0] == "SetAccountUserPrivilege"][0][1]
    assert privilege.UserName == "app"


def test_present_immutable_desc_drift_fails(monkeypatch):
    fake = FakeMongodbClient([_user(UserDesc="svc")])
    _make_module(monkeypatch, fake)
    _run_args(description="changed")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["replacement_required"] is True
    assert payload["immutable_changes"]["UserDesc"]["before"] == "svc"
    assert payload["immutable_changes"]["UserDesc"]["after"] == "changed"
    assert not any("SetAccountUserPrivilege" == c[0] for c in fake.calls)


def test_present_rotate_password_triggers_reset(monkeypatch):
    fake = FakeMongodbClient([_user()])
    _make_module(monkeypatch, fake)
    _run_args(rotate_password=True, password="rotated")
    result = run(mod.run_module)
    assert result["changed"] is True
    names = [c[0] for c in fake.calls]
    assert names.count("ResetDBInstancePassword") == 1
    assert "SetAccountUserPrivilege" not in names  # roles unchanged
    reset = [c for c in fake.calls if c[0] == "ResetDBInstancePassword"][0][1]
    assert reset.Password == "rotated"
    assert reset.UserName == "app"


def test_present_rotate_and_roles_drift_both_called(monkeypatch):
    fake = FakeMongodbClient([_user()])
    _make_module(monkeypatch, fake)
    _run_args(rotate_password=True, roles=[{"namespace": "billing", "access": "read_write"}])
    result = run(mod.run_module)
    assert result["changed"] is True
    names = [c[0] for c in fake.calls]
    assert names.count("SetAccountUserPrivilege") == 1
    assert names.count("ResetDBInstancePassword") == 1


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeMongodbClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"] is None  # no refetch in check mode
    assert not any("CreateAccountUser" == c[0] for c in fake.calls)


def test_check_mode_rotate_is_dry_run(monkeypatch):
    fake = FakeMongodbClient([_user()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(rotate_password=True).items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["UserName"] == "app"  # pre-change account reported
    assert not any("ResetDBInstancePassword" == c[0] for c in fake.calls)


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(MongodbClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_absent_deletes_account(monkeypatch):
    fake = FakeMongodbClient([_user()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", username="app")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteAccountUser"][0][1]
    assert delete.UserName == "app"
    assert delete.MongoUserPassword == "mongo-secret"
    assert fake.users == []


def test_absent_requires_mongo_password(monkeypatch):
    fake = FakeMongodbClient([_user()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", mongo_user_password=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "mongo_user_password is required when deleting a MongoDB account" in exc.value.args[0]["msg"]
    assert not any("DeleteAccountUser" == c[0] for c in fake.calls)


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeMongodbClient([_user()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", username="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["account"] is None
    assert not any("DeleteAccountUser" == c[0] for c in fake.calls)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeMongodbClient([_user()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(state="absent").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["account"]["UserName"] == "app"  # pre-change account reported
    assert not any("DeleteAccountUser" == c[0] for c in fake.calls)
    assert len(fake.users) == 1
