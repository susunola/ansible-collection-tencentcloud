"""Unit tests for the cfs_permission_group write module (helpers + run_module).

Creates, updates and deletes CFS client permission groups. Lookup is a
single DescribeCfsPGroups call matched by permission_group_id (preferred)
or name, failing on multiple matches. present converges Name/DescInfo via
Update (existing) or Create (missing, then re-find); absent deletes by the
matched PGroupId. A pre-SDK guard requires name when state=present.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cfs_permission_group as mod
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
        "name": "prod-clients",
        "description": "",
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
        return FakeModels(), SimpleNamespace(CfsClient=object)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or {}

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


def _group(group_id, name, description=None):
    return {"PGroupId": group_id, "Name": name, "DescInfo": description}


class FakeCfsClient(object):
    """In-memory CfsClient stand-in storing permission-group records.

    DescribeCfsPGroups returns every stored record; CreateCfsPGroup assigns
    a fresh PGroupId and stores the request payload; UpdateCfsPGroup /
    DeleteCfsPGroup address records by PGroupId.
    """

    def __init__(self, groups=None):
        self.groups = [dict(g) for g in (groups or [])]
        self.calls = []
        self._next_id = 1

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeCfsPGroups(self, request):
        self._record("DescribeCfsPGroups", request)
        return SimpleNamespace(
            PGroupList=[FakeResource(dict(g)) for g in self.groups],
            TotalCount=len(self.groups),
            RequestId="req-fake",
        )

    def CreateCfsPGroup(self, request):
        self._record("CreateCfsPGroup", request)
        group_id = "pgroup-%d" % self._next_id
        self._next_id += 1
        self.groups.append(_group(group_id, request.Name, request.DescInfo or ""))
        return SimpleNamespace(PGroupId=group_id, RequestId="req-fake")

    def UpdateCfsPGroup(self, request):
        self._record("UpdateCfsPGroup", request)
        for group in self.groups:
            if group["PGroupId"] == request.PGroupId:
                group["Name"] = request.Name
                group["DescInfo"] = request.DescInfo or ""
        return SimpleNamespace(RequestId="req-fake")

    def DeleteCfsPGroup(self, request):
        self._record("DeleteCfsPGroup", request)
        self.groups = [g for g in self.groups if g["PGroupId"] != request.PGroupId]
        return SimpleNamespace(RequestId="req-fake")


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


# ---------------------------------------------------------------------------
# request-builder and mapping helper tests
# ---------------------------------------------------------------------------


def test_describe_request():
    request = mod.describe_request(FakeModels())
    assert type(request).__name__ == "DescribeCfsPGroupsRequest"


def test_create_request_fields():
    request = mod.create_request(FakeModels(), _params(description="prod subnets"))
    assert request.Name == "prod-clients"
    assert request.DescInfo == "prod subnets"


def test_update_request_fields():
    request = mod.update_request(FakeModels(), _params(description="prod subnets"), "pgroup-1")
    assert request.PGroupId == "pgroup-1"
    assert request.Name == "prod-clients"
    assert request.DescInfo == "prod subnets"


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), "pgroup-1")
    assert request.PGroupId == "pgroup-1"


def test_desired_maps_params():
    assert mod.desired(_params(name="a", description="b")) == {"Name": "a", "DescInfo": "b"}


def test_comparable_coerces_missing_description():
    assert mod.comparable({"Name": "a", "DescInfo": None}) == {"Name": "a", "DescInfo": ""}
    assert mod.comparable({"Name": "a", "DescInfo": "b"}) == {"Name": "a", "DescInfo": "b"}


# ---------------------------------------------------------------------------
# find helper tests
# ---------------------------------------------------------------------------


def _find_params(**overrides):
    params = {"permission_group_id": None, "name": "prod-clients"}
    params.update(overrides)
    return params


def test_find_matches_by_name():
    fake = FakeCfsClient([_group("pgroup-1", "prod-clients"), _group("pgroup-2", "other")])
    module = FakeModule(_find_params())
    found = mod.find(module, fake, FakeModels(), module.params)
    assert found["PGroupId"] == "pgroup-1"


def test_find_prefers_permission_group_id_over_name():
    fake = FakeCfsClient([_group("pgroup-1", "prod-clients"), _group("pgroup-2", "other")])
    module = FakeModule(_find_params(permission_group_id="pgroup-2"))
    found = mod.find(module, fake, FakeModels(), module.params)
    assert found["PGroupId"] == "pgroup-2"  # matched by id, name ignored


def test_find_no_match_returns_none():
    fake = FakeCfsClient([_group("pgroup-1", "other")])
    module = FakeModule(_find_params())
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_empty_store_returns_none():
    module = FakeModule(_find_params())
    assert mod.find(module, FakeCfsClient(), FakeModels(), module.params) is None


def test_find_multiple_name_matches_fail():
    fake = FakeCfsClient([_group("pgroup-1", "dup"), _group("pgroup-2", "dup")])
    module = FakeModule(_find_params(name="dup"))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    assert exc.value.args[0]["msg"] == "Multiple CFS permission groups matched; specify permission_group_id"


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_present_requires_name():
    _run_args(name=None, permission_group_id="pgroup-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "name is required when state=present"


def test_absent_requires_identifier():
    _run_args(state="absent", name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    msg = exc.value.args[0]["msg"]
    assert "permission_group_id" in msg and "name" in msg


def test_present_creates_group_and_refinds(monkeypatch):
    fake = FakeCfsClient()
    _make_module(monkeypatch, fake)
    _run_args(description="prod subnets")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission_group"]["PGroupId"] == "pgroup-1"
    assert result["permission_group"]["Name"] == "prod-clients"
    assert result["permission_group"]["DescInfo"] == "prod subnets"
    assert [name for name, _ in fake.calls] == ["DescribeCfsPGroups", "CreateCfsPGroup", "DescribeCfsPGroups"]
    create = [req for name, req in fake.calls if name == "CreateCfsPGroup"][0]
    assert create.Name == "prod-clients"
    assert create.DescInfo == "prod subnets"


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeCfsClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission_group"] is None
    assert result["diff"]["before"] is None
    # empty-string DescInfo is stripped by the diff normalizer
    assert result["diff"]["after"] == {"Name": "prod-clients"}
    assert not any(name == "CreateCfsPGroup" for name, _ in fake.calls)


def test_present_unchanged_is_noop(monkeypatch):
    fake = FakeCfsClient([_group("pgroup-1", "prod-clients", description=None)])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["permission_group"]["PGroupId"] == "pgroup-1"
    assert not any(name in ("CreateCfsPGroup", "UpdateCfsPGroup") for name, _ in fake.calls)


def test_present_updates_name_by_id(monkeypatch):
    fake = FakeCfsClient([_group("pgroup-1", "old-name", "desc")])
    _make_module(monkeypatch, fake)
    _run_args(permission_group_id="pgroup-1", name="new-name")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission_group"]["Name"] == "new-name"  # re-find after update
    update = [req for name, req in fake.calls if name == "UpdateCfsPGroup"][0]
    assert update.PGroupId == "pgroup-1"
    assert update.Name == "new-name"
    assert update.DescInfo == ""


def test_present_updates_description(monkeypatch):
    fake = FakeCfsClient([_group("pgroup-1", "prod-clients", "old-desc")])
    _make_module(monkeypatch, fake)
    _run_args(description="new-desc")
    result = run(mod.run_module)
    assert result["changed"] is True
    update = [req for name, req in fake.calls if name == "UpdateCfsPGroup"][0]
    assert update.DescInfo == "new-desc"


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeCfsClient([_group("pgroup-1", "old-name", "desc")])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, permission_group_id="pgroup-1", name="new-name")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission_group"]["Name"] == "old-name"  # pre-update current
    assert result["diff"]["before"] == {"Name": "old-name", "DescInfo": "desc"}
    assert result["diff"]["after"] == {"Name": "new-name"}  # empty DescInfo stripped
    assert not any(name == "UpdateCfsPGroup" for name, _ in fake.calls)


def test_absent_deletes_by_id(monkeypatch):
    fake = FakeCfsClient([_group("pgroup-1", "prod-clients", "desc")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", permission_group_id="pgroup-1", name=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission_group"] is None
    delete = [req for name, req in fake.calls if name == "DeleteCfsPGroup"][0]
    assert delete.PGroupId == "pgroup-1"
    assert fake.groups == []  # record removed


def test_absent_deletes_group_matched_by_name(monkeypatch):
    fake = FakeCfsClient([_group("pgroup-1", "prod-clients", "desc")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission_group"] is None
    delete = [req for name, req in fake.calls if name == "DeleteCfsPGroup"][0]
    assert delete.PGroupId == "pgroup-1"


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCfsClient([_group("pgroup-1", "prod-clients", "desc")])
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, state="absent", permission_group_id="pgroup-1", name=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["permission_group"]["PGroupId"] == "pgroup-1"  # current kept for preview
    assert result["diff"]["before"] == {"Name": "prod-clients", "DescInfo": "desc"}
    assert result["diff"]["after"] is None
    assert not any(name == "DeleteCfsPGroup" for name, _ in fake.calls)
    assert len(fake.groups) == 1  # remote untouched


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeCfsClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="missing-group")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["permission_group"] is None
    assert not any(name == "DeleteCfsPGroup" for name, _ in fake.calls)


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(CfsClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: _BoomClient())
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeCfsClient([_group("pgroup-1", "prod-clients", description=None)])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.main)
    assert result["changed"] is False
    assert result["permission_group"]["PGroupId"] == "pgroup-1"
