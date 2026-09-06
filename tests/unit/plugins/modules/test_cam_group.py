"""Unit tests for the cam_group write module (helpers + run_module).

Creates, renames, updates and deletes CAM user groups. Lookup pages
ListGroups (Page/Rp=200, Keyword hint when a name is given) and matches by
group_id when given, else by exact GroupName; multiple name matches fail.
present converges GroupName/Remark via UpdateGroup (existing, addressed by
its matched GroupId) or CreateGroup then re-finds by the new id. absent
deletes the matched group. name is required when state=present.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cam_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

_ORIG_LOAD = mod._load  # captured before any monkeypatching


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "group_id": None,
        "name": "platform-engineers",
        "remark": "",
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter."""
    return module_args(**{k: v for k, v in _params(**extra).items() if v is not None})


def _load_real_or_fake():
    """Exercise the real lazy SDK import body when the SDK is installed.

    The coverage gate runs with the SDK present (see ci.yml "SDK contract
    tests"), so the real import executes and the ``_load`` body is covered;
    in SDK-less environments (``ansible-test units``) the import falls back
    to fake models so the same test file stays portable.
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


def _group(group_id, name, remark=""):
    return {"GroupId": group_id, "GroupName": name, "Remark": remark}


class FakeCamClient(object):
    """In-memory CamClient stand-in storing CAM group records.

    ListGroups slices stored records into 200-item pages (the module walks
    pages while a full page is returned); CreateGroup assigns a fresh int
    GroupId; UpdateGroup / DeleteGroup address records by GroupId.
    """

    page_size = 200

    def __init__(self, groups=None):
        self.groups = [dict(g) for g in (groups or [])]
        self.calls = []
        self._next_id = 1000001

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def ListGroups(self, request):
        self._record("ListGroups", request)
        start = (request.Page - 1) * self.page_size
        page = self.groups[start:start + self.page_size]
        return SimpleNamespace(
            GroupInfo=[FakeResource(dict(g)) for g in page],
            TotalNum=len(self.groups),
        )

    def CreateGroup(self, request):
        self._record("CreateGroup", request)
        group_id = self._next_id
        self._next_id += 1
        self.groups.append(_group(group_id, request.GroupName, request.Remark or ""))
        return SimpleNamespace(GroupId=group_id)

    def UpdateGroup(self, request):
        self._record("UpdateGroup", request)
        for group in self.groups:
            if group["GroupId"] == request.GroupId:
                group["GroupName"] = request.GroupName
                group["Remark"] = request.Remark or ""
        return SimpleNamespace()

    def DeleteGroup(self, request):
        self._record("DeleteGroup", request)
        self.groups = [g for g in self.groups if g["GroupId"] != request.GroupId]
        return SimpleNamespace()


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", _load_real_or_fake)
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


def _many_groups(count):
    return [_group(1000000 + i, "engineers-%d" % i) for i in range(count)]


# ---------------------------------------------------------------------------
# find helper tests
# ---------------------------------------------------------------------------


def test_find_matches_by_name():
    fake = FakeCamClient([_group(5, "platform-engineers"), _group(9, "other")])
    found = mod.find(FakeModule(), fake, FakeModels(), None, "platform-engineers")
    assert found["GroupId"] == 5
    request = [req for name, req in fake.calls if name == "ListGroups"][0]
    assert request.Keyword == "platform-engineers"  # keyword hint sent with name


def test_find_prefers_group_id_over_name():
    fake = FakeCamClient([_group(5, "platform-engineers"), _group(9, "other")])
    found = mod.find(FakeModule(), fake, FakeModels(), 9, "platform-engineers")
    assert found["GroupId"] == 9  # matched by id, name only used as keyword hint


def test_find_no_match_returns_none():
    fake = FakeCamClient([_group(5, "platform-engineers")])
    assert mod.find(FakeModule(), fake, FakeModels(), None, "missing") is None


def test_find_empty_store_returns_none():
    assert mod.find(FakeModule(), FakeCamClient(), FakeModels(), None, "platform-engineers") is None


def test_find_multiple_name_matches_fail():
    fake = FakeCamClient([_group(5, "dup"), _group(6, "dup")])
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(FakeModule(), fake, FakeModels(), None, "dup")
    payload = exc.value.args[0]
    assert payload["msg"] == "Multiple CAM groups have the requested name"
    assert payload["name"] == "dup"


def test_find_pages_to_second_page_for_target():
    fake = FakeCamClient(_many_groups(201))  # target at index 200 (page 2)
    found = mod.find(FakeModule(), fake, FakeModels(), 1000200, None)
    assert found["GroupId"] == 1000200
    pages = [req.Page for name, req in fake.calls if name == "ListGroups"]
    assert pages == [1, 2]


def test_find_no_match_pages_until_short_page():
    fake = FakeCamClient(_many_groups(250))
    assert mod.find(FakeModule(), fake, FakeModels(), 999999, None) is None
    pages = [req.Page for name, req in fake.calls if name == "ListGroups"]
    assert pages == [1, 2]  # page 2 short (< 200) stops the walk


# ---------------------------------------------------------------------------
# validation tests (no monkeypatch needed)
# ---------------------------------------------------------------------------


def test_present_requires_name():
    _run_args(group_id=5, name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "name is required when state=present"


def test_neither_group_id_nor_name_fails_required_one_of():
    _run_args(state="absent", group_id=None, name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    msg = exc.value.args[0]["msg"]
    assert "group_id" in msg and "name" in msg


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_present_creates_group_and_refinds(monkeypatch):
    fake = FakeCamClient()
    _make_module(monkeypatch, fake)
    _run_args(remark="Platform engineering team")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["GroupId"] == 1000001
    assert result["group"]["GroupName"] == "platform-engineers"
    assert result["group"]["Remark"] == "Platform engineering team"
    assert [name for name, request in fake.calls] == ["ListGroups", "CreateGroup", "ListGroups"]
    create = [req for name, req in fake.calls if name == "CreateGroup"][0]
    assert create.GroupName == "platform-engineers"
    assert create.Remark == "Platform engineering team"
    refind = [req for name, req in fake.calls if name == "ListGroups"][-1]
    # re-find by id sends no keyword hint; real SDK models pre-set fields to None
    assert getattr(refind, "Keyword", None) is None


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeCamClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"] is None
    assert result["diff"]["before"] is None
    # empty-string remark is stripped by the diff normalizer
    assert result["diff"]["after"] == {"GroupName": "platform-engineers"}
    assert not any(name == "CreateGroup" for name, request in fake.calls)


def test_present_unchanged_is_noop(monkeypatch):
    fake = FakeCamClient([_group(5, "platform-engineers")])
    _make_module(monkeypatch, fake)
    _run_args(group_id=5)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["group"]["GroupId"] == 5
    assert not any(name in ("CreateGroup", "UpdateGroup") for name, request in fake.calls)


def test_present_renames_group_by_id(monkeypatch):
    fake = FakeCamClient([_group(5, "old-name", "some remark")])
    _make_module(monkeypatch, fake)
    _run_args(group_id=5, name="new-name")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["GroupName"] == "new-name"  # re-find by id after update
    update = [req for name, req in fake.calls if name == "UpdateGroup"][0]
    assert update.GroupId == 5
    assert update.GroupName == "new-name"
    assert update.Remark == ""


def test_present_updates_remark_matched_by_name(monkeypatch):
    fake = FakeCamClient([_group(5, "platform-engineers", "old remark")])
    _make_module(monkeypatch, fake)
    _run_args(remark="new remark")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["Remark"] == "new remark"
    update = [req for name, req in fake.calls if name == "UpdateGroup"][0]
    assert update.GroupId == 5
    assert update.Remark == "new remark"


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeCamClient([_group(5, "old-name", "old remark")])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, group_id=5, name="new-name")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["GroupName"] == "old-name"  # pre-update current
    assert result["diff"]["before"] == {"GroupName": "old-name", "Remark": "old remark"}
    assert result["diff"]["after"] == {"GroupName": "new-name"}
    assert not any(name == "UpdateGroup" for name, request in fake.calls)


def test_absent_deletes_by_id(monkeypatch):
    fake = FakeCamClient([_group(5, "platform-engineers", "remark")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", group_id=5, name=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"] is None
    delete = [req for name, req in fake.calls if name == "DeleteGroup"][0]
    assert delete.GroupId == 5
    assert fake.groups == []  # record removed


def test_absent_deletes_group_matched_by_name(monkeypatch):
    fake = FakeCamClient([_group(5, "platform-engineers", "remark")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    delete = [req for name, req in fake.calls if name == "DeleteGroup"][0]
    assert delete.GroupId == 5  # id taken from the name-matched group


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCamClient([_group(5, "platform-engineers", "remark")])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["GroupId"] == 5  # current kept for preview
    assert result["diff"]["before"] == {"GroupId": 5, "GroupName": "platform-engineers", "Remark": "remark"}
    assert result["diff"]["after"] is None
    assert not any(name == "DeleteGroup" for name, request in fake.calls)
    assert len(fake.groups) == 1  # remote untouched


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeCamClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="missing-group")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["group"] is None
    assert not any(name == "DeleteGroup" for name, request in fake.calls)


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(CamClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: _BoomClient())
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeCamClient([_group(5, "platform-engineers")])
    _make_module(monkeypatch, fake)
    _run_args(group_id=5)
    result = run(mod.main)
    assert result["changed"] is False
    assert result["group"]["GroupId"] == 5
