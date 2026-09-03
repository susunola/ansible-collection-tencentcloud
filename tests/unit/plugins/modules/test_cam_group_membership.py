"""Unit tests for the cam_group_membership write module (helpers + run_module).

Idempotently adds a CAM sub-user to (state=present) or removes it from
(state=absent) a user group. Lookup pages ListGroupsForUser (Rp=200) and
matches the group_id; mutations go through AddUserToGroup /
RemoveUserFromGroup and are then polled by wait_for_membership until the
remote state converges or waiter_timeout elapses. sub_uin and uid are
mutually exclusive and one of them is required.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cam_group_membership as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

_ORIG_LOAD = mod._load_cam  # captured before any monkeypatching


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "group_id": 12345,
        "sub_uin": 100000000001,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    return module_args(**{k: v for k, v in _params(**extra).items() if v is not None})


def _load_real_or_fake():
    """Exercise the real lazy SDK import body when the SDK is installed.

    The coverage gate runs with the SDK present (see ci.yml "SDK contract
    tests"), so the real import executes and the ``_load_cam`` body is
    covered; in SDK-less environments (``ansible-test units``) the import
    falls back to fake models so the same test file stays portable.
    """
    try:
        return _ORIG_LOAD()
    except ImportError:
        return FakeModels(), SimpleNamespace(CamClient=object)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or {}

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeCamClient(object):
    """In-memory CamClient stand-in storing one user's group memberships.

    ListGroupsForUser pages over the stored groups (Page/Rp=200 slicing) so
    multi-page membership scans are observable; AddUserToGroup /
    RemoveUserFromGroup mutate the stored set immediately, so
    wait_for_membership converges on its first re-check.
    """

    def __init__(self, groups=None):
        # (sub_uin, uid) -> sorted list of group ids
        self.groups = {key: sorted(set(value)) for key, value in (groups or {}).items()}
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _key(self, request):
        return (getattr(request, "SubUin", None), getattr(request, "Uid", None))

    def ListGroupsForUser(self, request):
        self._record("ListGroupsForUser", request)
        groups = self.groups.get(self._key(request), [])
        page = request.Page or 1
        page_items = groups[(page - 1) * 200:page * 200]
        return SimpleNamespace(
            GroupInfo=[FakeResource({"GroupId": g}) for g in page_items],
            TotalNum=len(groups),
            RequestId="req-fake",
        )

    def AddUserToGroup(self, request):
        self._record("AddUserToGroup", request)
        info = request.Info[0]
        key = (info.Uin, info.Uid)
        self.groups.setdefault(key, []).append(info.GroupId)
        self.groups[key] = sorted(set(self.groups[key]))
        return SimpleNamespace(RequestId="req-fake")

    def RemoveUserFromGroup(self, request):
        self._record("RemoveUserFromGroup", request)
        info = request.Info[0]
        key = (info.Uin, info.Uid)
        groups = self.groups.get(key, [])
        if info.GroupId in groups:
            groups.remove(info.GroupId)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_cam", _load_real_or_fake)
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


class _NoopMutationClient(FakeCamClient):
    """Add/Remove record the call but never mutate, so the waiter times out."""

    def AddUserToGroup(self, request):
        self._record("AddUserToGroup", request)
        return SimpleNamespace(RequestId="req-fake")

    def RemoveUserFromGroup(self, request):
        self._record("RemoveUserFromGroup", request)
        return SimpleNamespace(RequestId="req-fake")


# ---------------------------------------------------------------------------
# request-builder helper tests
# ---------------------------------------------------------------------------


def test_build_list_request_defaults():
    request = mod.build_list_request(FakeModels(), {"group_id": 12345, "sub_uin": 100000000001, "uid": None})
    assert request.Page == 1
    assert request.Rp == 200
    assert request.SubUin == 100000000001
    assert request.Uid is None


def test_build_list_request_page_and_uid():
    request = mod.build_list_request(FakeModels(), {"group_id": 12345, "sub_uin": None, "uid": 777}, page=3)
    assert request.Page == 3
    assert request.SubUin is None
    assert request.Uid == 777


def test_build_mutation_request_add():
    request = mod.build_mutation_request(FakeModels(), _params(), present=True)
    assert type(request).__name__ == "AddUserToGroupRequest"
    info = request.Info[0]
    assert info.GroupId == 12345
    assert info.Uin == 100000000001
    assert info.Uid is None


def test_build_mutation_request_remove_by_uid():
    request = mod.build_mutation_request(FakeModels(), _params(sub_uin=None, uid=777), present=False)
    assert type(request).__name__ == "RemoveUserFromGroupRequest"
    info = request.Info[0]
    assert info.GroupId == 12345
    assert info.Uin is None
    assert info.Uid == 777


# ---------------------------------------------------------------------------
# is_member helper tests
# ---------------------------------------------------------------------------


def _find_params(**overrides):
    params = {"group_id": 12345, "sub_uin": 100000000001, "uid": None}
    params.update(overrides)
    return params


def test_is_member_true_when_group_present():
    fake = FakeCamClient({(100000000001, None): [111, 12345]})
    module = FakeModule(_find_params())
    assert mod.is_member(module, fake, FakeModels(), module.params) is True
    assert [name for name, _ in fake.calls] == ["ListGroupsForUser"]


def test_is_member_coerces_string_group_id():
    fake = FakeCamClient({(100000000001, None): [12345]})
    module = FakeModule(_find_params())
    assert mod.is_member(module, fake, FakeModels(), module.params) is True


def test_is_member_false_when_group_absent():
    fake = FakeCamClient({(100000000001, None): [111, 222]})
    module = FakeModule(_find_params())
    assert mod.is_member(module, fake, FakeModels(), module.params) is False


def test_is_member_false_for_other_user():
    fake = FakeCamClient({(999, None): [12345]})  # different sub-uin
    module = FakeModule(_find_params())
    assert mod.is_member(module, fake, FakeModels(), module.params) is False


def test_is_member_empty_memberships_is_false():
    fake = FakeCamClient()
    module = FakeModule(_find_params())
    assert mod.is_member(module, fake, FakeModels(), module.params) is False


def test_is_member_pages_until_target_found():
    groups = list(range(1, 251))  # 250 memberships: target on the second page
    fake = FakeCamClient({(100000000001, None): groups})
    module = FakeModule(_find_params(group_id=250))
    assert mod.is_member(module, fake, FakeModels(), module.params) is True
    list_calls = [req for name, req in fake.calls if name == "ListGroupsForUser"]
    assert [req.Page for req in list_calls] == [1, 2]


def test_is_member_pages_to_exhaustion_when_absent():
    fake = FakeCamClient({(100000000001, None): list(range(1, 251))})
    module = FakeModule(_find_params(group_id=999))
    assert mod.is_member(module, fake, FakeModels(), module.params) is False
    list_calls = [req for name, req in fake.calls if name == "ListGroupsForUser"]
    assert [req.Page for req in list_calls] == [1, 2]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_neither_sub_uin_nor_uid_fails_validation():
    _run_args(sub_uin=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    msg = exc.value.args[0]["msg"]
    assert "sub_uin" in msg and "uid" in msg


def test_both_sub_uin_and_uid_fail_validation():
    _run_args(sub_uin=100000000001, uid=777)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "mutually exclusive" in exc.value.args[0]["msg"]


def test_present_already_member_is_noop(monkeypatch):
    fake = FakeCamClient({(100000000001, None): [12345]})
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["msg"] == "CAM group membership is up to date"
    assert result["membership"]["present"] is True
    assert not any(name.startswith("Add") or name.startswith("Remove") for name, _ in fake.calls)


def test_absent_non_member_is_noop(monkeypatch):
    fake = FakeCamClient({(100000000001, None): [111]})
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["membership"]["present"] is False


def test_present_adds_member(monkeypatch):
    fake = FakeCamClient({(100000000001, None): [111]})
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "CAM group membership updated"
    assert result["membership"]["present"] is True
    assert result["membership"]["group_id"] == 12345
    assert "diff" not in result  # no diff outside check mode
    assert any(name == "AddUserToGroup" for name, _ in fake.calls)
    add = [req for name, req in fake.calls if name == "AddUserToGroup"][0]
    assert add.Info[0].GroupId == 12345
    assert add.Info[0].Uin == 100000000001


def test_absent_removes_member(monkeypatch):
    fake = FakeCamClient({(100000000001, None): [12345]})
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["membership"]["present"] is False
    assert any(name == "RemoveUserFromGroup" for name, _ in fake.calls)
    remove = [req for name, req in fake.calls if name == "RemoveUserFromGroup"][0]
    assert remove.Info[0].GroupId == 12345


def test_check_mode_add_is_dry_run(monkeypatch):
    fake = FakeCamClient({(100000000001, None): [111]})
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would update CAM group membership"
    assert result["membership"]["present"] is False  # current state, not target
    assert result["diff"]["before"]["present"] is False
    assert result["diff"]["after"]["present"] is True
    assert not any(name.startswith("Add") or name.startswith("Remove") for name, _ in fake.calls)


def test_check_mode_remove_is_dry_run(monkeypatch):
    fake = FakeCamClient({(100000000001, None): [12345]})
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["diff"]["after"]["present"] is False
    assert not any(name.startswith("Add") or name.startswith("Remove") for name, _ in fake.calls)


def test_wait_times_out_when_mutation_never_applies(monkeypatch):
    fake = _NoopMutationClient({(100000000001, None): [111]})
    _make_module(monkeypatch, fake)
    _run_args(waiter_timeout=0, waiter_delay=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Timed out waiting for CAM group membership"
    assert payload["expected"] is True
    assert payload["current"] is False
    assert any(name == "AddUserToGroup" for name, _ in fake.calls)


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_cam", lambda: (FakeModels(), SimpleNamespace(CamClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: _BoomClient())
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"
    assert payload["error_code"] is None
    assert payload["request_id"] is None


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeCamClient({(100000000001, None): [12345]})
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.main)
    assert result["changed"] is False
    assert result["membership"]["present"] is True
