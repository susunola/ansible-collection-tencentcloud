"""Unit tests for the teo_security_ip_group write module (helpers + run_module).

Creates, renames, exactly replaces and deletes EdgeOne security IP groups.
The zone-scoped lookup runs through two APIs: DescribeSecurityIPGroupInfo
pages the group metadata (client-side match on numeric group_id or exact
name; more than one match fails) and DescribeSecurityIPGroupContent pages
the full content list of the matched group. Content is compared as a
sorted set, so order and duplicates in the API never matter. Create
(GroupId 0 sent, real id read back), modify (Mode "update") and delete all
refind the group afterwards. name + non-empty content are validated before
the SDK is reached.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import teo_security_ip_group as mod
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


def _group_state(**overrides):
    """API-shaped stored group; fresh copy per call."""
    item = {
        "group_id": 2001,
        "name": "trusted-offices",
        "content": ["2001:db8::/48", "192.0.2.0/24"],
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "zone_id": "zone-1001",
        "group_id": None,
        "name": "trusted-offices",
        "content": ["192.0.2.0/24", "2001:db8::/48"],
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


class FakeTeoClient(object):
    """In-memory TeoClient stand-in storing zone-scoped group dicts.

    DescribeSecurityIPGroupInfo returns every group of the zone (the module
    applies its own id/name filtering and multi-match check);
    DescribeSecurityIPGroupContent pages the content of one group,
    chunking to ``page_size`` when set so the module's paging loop runs
    more than once; CreateSecurityIPGroup synthesises sequential numeric
    ids; ModifySecurityIPGroup rewrites the group selected by the request's
    nested IPGroup.GroupId; DeleteSecurityIPGroup removes by id.
    """

    def __init__(self, groups=None, page_size=None):
        self.groups = [dict(g) for g in (groups or [])]
        self.calls = []
        self._seq = 2000
        self.page_size = page_size

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _next_id(self):
        self._seq += 1
        return self._seq

    def DescribeSecurityIPGroupInfo(self, request):
        self._record("DescribeSecurityIPGroupInfo", request)
        values = [
            FakeResource({"GroupId": g["group_id"], "Name": g["name"]})
            for g in self.groups
            if g["name"] and g["group_id"] is not None
        ]
        return SimpleNamespace(IPGroups=values, TotalCount=len(values), RequestId="req-fake")

    def DescribeSecurityIPGroupContent(self, request):
        self._record("DescribeSecurityIPGroupContent", request)
        content = []
        for group in self.groups:
            if group["group_id"] == request.GroupId:
                content = list(group["content"])
        chunk = content
        if self.page_size is not None:
            chunk = content[getattr(request, "Offset", 0):getattr(request, "Offset", 0) + self.page_size]
        return SimpleNamespace(IPList=list(chunk), IPTotalCount=len(content), RequestId="req-fake")

    def CreateSecurityIPGroup(self, request):
        self._record("CreateSecurityIPGroup", request)
        group_id = self._next_id()
        ip_group = request.IPGroup
        self.groups.append({
            "group_id": group_id,
            "name": ip_group.Name,
            "content": list(ip_group.Content or []),
        })
        return SimpleNamespace(GroupId=group_id, RequestId="req-fake")

    def ModifySecurityIPGroup(self, request):
        self._record("ModifySecurityIPGroup", request)
        target = request.IPGroup.GroupId
        for group in self.groups:
            if group["group_id"] == target:
                group["name"] = request.IPGroup.Name
                group["content"] = list(request.IPGroup.Content or [])
        return SimpleNamespace(RequestId="req-fake")

    def DeleteSecurityIPGroup(self, request):
        self._record("DeleteSecurityIPGroup", request)
        self.groups = [g for g in self.groups if g["group_id"] != request.GroupId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TeoClient=object)),
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
# helper tests
# ---------------------------------------------------------------------------


def test_describe_request_sets_zone_and_paging():
    request = mod.describe_request(FakeModels(), _params())
    assert request.ZoneId == "zone-1001"
    assert request.Offset == 0
    assert request.Limit == 1000


def test_content_request_sets_group_and_paging():
    request = mod.content_request(FakeModels(), _params(), 2001, offset=100)
    assert request.ZoneId == "zone-1001"
    assert request.GroupId == 2001
    assert request.Offset == 100
    assert request.Limit == 100000


def test_group_builder_sets_fields():
    item = mod._group(FakeModels(), 7, "name-x", ["a"])
    assert item.GroupId == 7
    assert item.Name == "name-x"
    assert item.Content == ["a"]


def test_create_request_wraps_group():
    request = mod.create_request(FakeModels(), _params())
    assert request.ZoneId == "zone-1001"
    assert request.IPGroup.GroupId == 0
    assert request.IPGroup.Name == "trusted-offices"
    assert request.IPGroup.Content == ["192.0.2.0/24", "2001:db8::/48"]


def test_update_request_uses_update_mode():
    request = mod.update_request(FakeModels(), _params(), 2001)
    assert request.ZoneId == "zone-1001"
    assert request.Mode == "update"
    assert request.IPGroup.GroupId == 2001
    assert request.IPGroup.Name == "trusted-offices"


def test_delete_request_sets_group_id():
    request = mod.delete_request(FakeModels(), _params(), 2001)
    assert request.ZoneId == "zone-1001"
    assert request.GroupId == 2001


def test_desired_sorts_and_dedups_content():
    value = mod.desired(_params(content=["b", "a", "b"]))
    assert value == {"Name": "trusted-offices", "Content": ["a", "b"]}


def test_find_group_by_id_enriches_content():
    fake = FakeTeoClient([_group_state()])
    module = FakeModule(_params(group_id=2001, name="irrelevant"))
    value = mod.find_group(module, fake, FakeModels(), module.params)
    assert value["GroupId"] == 2001
    assert value["Name"] == "trusted-offices"
    assert value["Content"] == ["2001:db8::/48", "192.0.2.0/24"]
    assert [c[0].__name__ for c in module.sdk_calls] == [
        "DescribeSecurityIPGroupInfo",
        "DescribeSecurityIPGroupContent",
    ]
    assert module.sdk_calls[0][1].ZoneId == "zone-1001"
    assert module.sdk_calls[1][1].GroupId == 2001


def test_find_group_by_name_enriches_content():
    fake = FakeTeoClient([_group_state()])
    module = FakeModule(_params())
    value = mod.find_group(module, fake, FakeModels(), module.params)
    assert value["GroupId"] == 2001
    assert value["Content"] == ["2001:db8::/48", "192.0.2.0/24"]


def test_find_group_no_match_returns_none():
    fake = FakeTeoClient()
    module = FakeModule(_params(name="ghost"))
    assert mod.find_group(module, fake, FakeModels(), module.params) is None
    assert [c[0].__name__ for c in module.sdk_calls] == ["DescribeSecurityIPGroupInfo"]


def test_find_group_multi_match_fails():
    fake = FakeTeoClient([_group_state(), _group_state(group_id=2002)])
    module = FakeModule(_params())
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find_group(module, fake, FakeModels(), module.params)
    payload = exc.value.args[0]
    assert "Multiple EdgeOne security IP groups matched; specify group_id" in payload["msg"]


def test_find_group_pages_content():
    fake = FakeTeoClient([_group_state(content=["a", "b", "c"])], page_size=2)
    module = FakeModule(_params())
    value = mod.find_group(module, fake, FakeModels(), module.params)
    assert value["Content"] == ["a", "b", "c"]
    content_calls = [c for c in module.sdk_calls if c[0].__name__ == "DescribeSecurityIPGroupContent"]
    assert len(content_calls) == 2
    assert content_calls[1][1].Offset == 2


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_requires_either_group_id_or_name(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args(name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "one of the following is required" in exc.value.args[0]["msg"]
    assert fake.calls == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"group_id": 2001, "name": None},
        {"content": None},
        {"content": []},
    ],
)
def test_present_requires_name_and_content(monkeypatch, overrides):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args(**overrides)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "name and at least one content entry are required when state=present" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_content_duplicates_fail(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args(content=["192.0.2.0/24", "192.0.2.0/24"])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "content must not contain duplicate IP or CIDR entries" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_absent_noop_when_missing(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["ip_group"] is None
    assert [c[0] for c in fake.calls] == ["DescribeSecurityIPGroupInfo"]


def test_absent_check_mode_delete_is_dry_run(monkeypatch):
    fake = FakeTeoClient([_group_state()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ip_group"]["GroupId"] == 2001
    assert result["diff"]["before"]["GroupId"] == 2001
    assert result["diff"]["after"] is None
    assert [c[0] for c in fake.calls] == [
        "DescribeSecurityIPGroupInfo",
        "DescribeSecurityIPGroupContent",
    ]
    assert len(fake.groups) == 1


def test_absent_deletes_group(monkeypatch):
    fake = FakeTeoClient([_group_state()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ip_group"] is None
    assert [c[0] for c in fake.calls] == [
        "DescribeSecurityIPGroupInfo",
        "DescribeSecurityIPGroupContent",
        "DeleteSecurityIPGroup",
    ]
    deleted = fake.calls[2][1]
    assert deleted.ZoneId == "zone-1001"
    assert deleted.GroupId == 2001
    assert fake.groups == []


def test_present_noop_when_group_matches(monkeypatch):
    fake = FakeTeoClient([_group_state()])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["ip_group"]["GroupId"] == 2001
    assert result["ip_group"]["Content"] == ["2001:db8::/48", "192.0.2.0/24"]
    assert [c[0] for c in fake.calls] == [
        "DescribeSecurityIPGroupInfo",
        "DescribeSecurityIPGroupContent",
    ]


def test_present_content_drift_updates_group(monkeypatch):
    fake = FakeTeoClient([_group_state()])
    _make_module(monkeypatch, fake)
    _run_args(content=["192.0.2.0/24"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ip_group"]["Content"] == ["192.0.2.0/24"]
    assert [c[0] for c in fake.calls] == [
        "DescribeSecurityIPGroupInfo",
        "DescribeSecurityIPGroupContent",
        "ModifySecurityIPGroup",
        "DescribeSecurityIPGroupInfo",
        "DescribeSecurityIPGroupContent",
    ]
    updated = fake.calls[2][1]
    assert updated.ZoneId == "zone-1001"
    assert updated.Mode == "update"
    assert updated.IPGroup.GroupId == 2001
    assert updated.IPGroup.Content == ["192.0.2.0/24"]
    assert fake.groups[0]["content"] == ["192.0.2.0/24"]


def test_present_renames_via_group_id(monkeypatch):
    fake = FakeTeoClient([_group_state()])
    _make_module(monkeypatch, fake)
    _run_args(group_id=2001, name="renamed-offices")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ip_group"]["Name"] == "renamed-offices"
    updated = fake.calls[2][1]
    assert updated.IPGroup.GroupId == 2001
    assert updated.IPGroup.Name == "renamed-offices"
    assert fake.groups[0]["name"] == "renamed-offices"


def test_present_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeTeoClient([_group_state()])
    _make_module(monkeypatch, fake)
    _run_args(content=["192.0.2.0/24"], _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ip_group"]["Content"] == ["2001:db8::/48", "192.0.2.0/24"]
    assert result["diff"]["before"]["Content"] == ["192.0.2.0/24", "2001:db8::/48"]
    assert result["diff"]["after"]["Content"] == ["192.0.2.0/24"]
    assert [c[0] for c in fake.calls] == [
        "DescribeSecurityIPGroupInfo",
        "DescribeSecurityIPGroupContent",
    ]
    assert fake.groups[0]["content"] == ["2001:db8::/48", "192.0.2.0/24"]


def test_present_creates_group(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ip_group"]["GroupId"] == 2001
    assert result["ip_group"]["Name"] == "trusted-offices"
    assert result["ip_group"]["Content"] == ["192.0.2.0/24", "2001:db8::/48"]
    assert [c[0] for c in fake.calls] == [
        "DescribeSecurityIPGroupInfo",
        "CreateSecurityIPGroup",
        "DescribeSecurityIPGroupInfo",
        "DescribeSecurityIPGroupContent",
    ]
    created = fake.calls[1][1]
    assert created.ZoneId == "zone-1001"
    assert created.IPGroup.GroupId == 0
    assert created.IPGroup.Name == "trusted-offices"
    assert len(fake.groups) == 1
    assert fake.groups[0]["group_id"] == 2001


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["ip_group"] is None
    assert result["diff"]["before"] is None
    assert result["diff"]["after"] == {
        "Name": "trusted-offices",
        "Content": ["192.0.2.0/24", "2001:db8::/48"],
    }
    assert [c[0] for c in fake.calls] == ["DescribeSecurityIPGroupInfo"]
    assert fake.groups == []


def test_sdk_failure_reports_error_payload(monkeypatch):
    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "auth rejected"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeTeoClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent", name="ghost")
    result = run(mod.main)
    assert result["changed"] is False
    assert result["ip_group"] is None
