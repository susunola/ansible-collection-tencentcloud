"""Tests for the DNSPod routing-line writers: dnspod_custom_line and dnspod_line_group.

The file name says "line" because both modules manage one half of the same
DNSPod feature: a custom line (a named IP range) and a line group (an exact
set of those lines). Both are domain-scoped, both are keyed by name, and both
reconcile through ``run_module``.

The two request-shape tests came first and stay as they were. Everything below
drives ``run_module()`` against an in-memory fake ``DnspodClient`` whose write
operations mutate a store, so the module's find-then-create/update/delete
decisions are observable through the request it sends and the payload it
returns. The fixtures use the field names the API actually returns --
``CustomLineInfo`` (``DomainId``/``Name``/``Area``/``UseCount``/``MaxCount``)
and ``LineGroupItem`` (``DomainId``/``Id``/``Name``/``Lines``/``CreatedOn``/
``UpdatedOn``) with ``LineGroupSum`` (``NowTotal``/``Total``/``AvailableCount``)
as pagination metadata.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dnspod_custom_line, dnspod_line_group
from ansible_collections.susunola.tencentcloud.plugins.modules.dnspod_custom_line import describe_request as custom_request
from ansible_collections.susunola.tencentcloud.plugins.modules.dnspod_line_group import describe_request as group_request
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

DOMAIN = "example.com"
DOMAIN_ID = 7788
OTHER_DOMAIN_ID = 9911
CUSTOM_NAME = "office-network"
CUSTOM_AREA = "203.0.113.1-203.0.113.254"
GROUP_NAME = "corporate-networks"
GROUP_ID = 1001

#: One ``CustomLineInfo`` as ``DescribeDomainCustomLineList`` returns it, plus
#: the same name under a different domain: DNSPod names are domain-scoped, so
#: the module has to carry the domain through the lookup.
CUSTOM_LINE = {
    "DomainId": DOMAIN_ID,
    "Name": CUSTOM_NAME,
    "Area": CUSTOM_AREA,
    "UseCount": 1,
    "MaxCount": 10,
}
SAME_NAME_OTHER_DOMAIN = {
    "DomainId": OTHER_DOMAIN_ID,
    "Name": CUSTOM_NAME,
    "Area": "10.0.0.1-10.0.0.9",
    "UseCount": 1,
    "MaxCount": 10,
}

#: One ``LineGroupItem`` as ``DescribeLineGroupList`` returns it.
LINE_GROUP = {
    "DomainId": DOMAIN_ID,
    "Id": GROUP_ID,
    "Name": GROUP_NAME,
    "Lines": ["office-network", "vpn-network"],
    "CreatedOn": "2026-01-15 09:30:00",
    "UpdatedOn": "2026-01-20 14:05:00",
}


def test_group_request_sets_scope_and_pagination():
    request = group_request(FakeModels(), {"domain": "example.com", "domain_id": None}, 100)
    assert (request.Domain, request.Offset, request.Length) == ("example.com", 100, 100)


def test_custom_request_sets_domain_id_scope():
    assert custom_request(FakeModels(), {"domain": None, "domain_id": 42}).DomainId == 42


class FakeDnspodClientClass(object):
    """Stand-in for the SDK's ``DnspodClient`` class (both modules share it)."""


class FakeDnspodClient(object):
    """In-memory DNSPod client for the custom-line and line-group APIs.

    Reads filter the store the way the API does (by ``DomainId`` when it is
    given) and writes mutate it, so a module that re-reads after a write sees
    its own change. Every call is recorded with its request object.
    """

    def __init__(self, custom_lines=None, line_groups=None, error=None, fail_on=None):
        self.custom_lines = [copy.deepcopy(line) for line in (custom_lines or [])]
        self.line_groups = [copy.deepcopy(group) for group in (line_groups or [])]
        self.error = error
        self.fail_on = fail_on
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        if self.error is not None and (self.fail_on is None or self.fail_on == name):
            raise self.error
        return request

    @property
    def operations(self):
        return [name for name, _request in self.calls]

    def _scoped(self, items, request):
        if getattr(request, "DomainId", None) is not None:
            return [item for item in items if item["DomainId"] == request.DomainId]
        return list(items)

    def DescribeDomainCustomLineList(self, request):
        self._record("DescribeDomainCustomLineList", request)
        lines = self._scoped(self.custom_lines, request)
        return SimpleNamespace(LineList=[FakeResource(line) for line in lines], AvailableCount=8, RequestId="req-line")

    def CreateDomainCustomLine(self, request):
        self._record("CreateDomainCustomLine", request)
        self.custom_lines.append({
            "DomainId": request.DomainId,
            "Name": request.Name,
            "Area": request.Area,
            "UseCount": 1,
            "MaxCount": 10,
        })
        return SimpleNamespace(RequestId="req-line")

    def ModifyDomainCustomLine(self, request):
        self._record("ModifyDomainCustomLine", request)
        for line in self._scoped(self.custom_lines, request):
            if line["Name"] == request.PreName:
                line["Name"], line["Area"] = request.Name, request.Area
        return SimpleNamespace(RequestId="req-line")

    def DeleteDomainCustomLine(self, request):
        self._record("DeleteDomainCustomLine", request)
        domain_id = getattr(request, "DomainId", None)
        self.custom_lines = [
            line for line in self.custom_lines
            if not ((domain_id is None or line["DomainId"] == domain_id) and line["Name"] == request.Name)
        ]
        return SimpleNamespace(RequestId="req-line")

    def DescribeLineGroupList(self, request):
        self._record("DescribeLineGroupList", request)
        groups = self._scoped(self.line_groups, request)
        offset, length = request.Offset or 0, request.Length or len(groups)
        page = groups[offset:offset + length]
        return SimpleNamespace(
            LineGroups=[FakeResource(group) for group in page],
            Info=SimpleNamespace(NowTotal=len(page), Total=len(groups), AvailableCount=100),
            RequestId="req-group",
        )

    def CreateLineGroup(self, request):
        self._record("CreateLineGroup", request)
        group_id = GROUP_ID + len(self.line_groups)
        self.line_groups.append({
            "DomainId": request.DomainId,
            "Id": group_id,
            "Name": request.Name,
            "Lines": request.Lines.split(",") if request.Lines else [],
            "CreatedOn": "2026-02-01 10:00:00",
            "UpdatedOn": "2026-02-01 10:00:00",
        })
        return SimpleNamespace(LineGroupId=group_id, RequestId="req-group")

    def ModifyLineGroup(self, request):
        self._record("ModifyLineGroup", request)
        for group in self.line_groups:
            if group["Id"] == request.LineGroupId:
                group["Name"] = request.Name
                group["Lines"] = request.Lines.split(",") if request.Lines else []
                group["UpdatedOn"] = "2026-02-02 09:15:00"
        return SimpleNamespace(RequestId="req-group")

    def DeleteLineGroup(self, request):
        self._record("DeleteLineGroup", request)
        self.line_groups = [group for group in self.line_groups if group["Id"] != request.LineGroupId]
        return SimpleNamespace(RequestId="req-group")


def _patch_module(monkeypatch, module, client):
    """Point ``module`` at ``client`` through its ``_load``/``create_client`` seams.

    Both modules resolve the SDK in ``_load()`` and build the client through
    the base class, so no real credential or SDK package is needed.
    """
    clients = []
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(module, "_load", lambda: (FakeModels(), SimpleNamespace(DnspodClient=FakeDnspodClientClass)))

    def create_client(self, client_class, endpoint):
        clients.append((client_class, endpoint))
        return client

    monkeypatch.setattr(TencentCloudModule, "create_client", create_client)
    return clients


def _custom_args(**extra):
    args = {"domain_id": DOMAIN_ID, "name": CUSTOM_NAME, "area": CUSTOM_AREA}
    args.update(extra)
    return module_args(**args)


def _group_args(**extra):
    args = {"domain_id": DOMAIN_ID, "name": GROUP_NAME, "lines": ["vpn-network", "office-network"]}
    args.update(extra)
    return module_args(**args)


def _operations(payload):
    """The SDK operations the module issued, in order, from the audit trail."""
    return [call["operation"] for call in payload["tc_api_calls"]]


def _recorded(client):
    """The SDK operations the fake client served, in order."""
    return [name for name, _request in client.calls]


# ---------------------------------------------------------------------------
# dnspod_custom_line: request builders
# ---------------------------------------------------------------------------


def test_custom_line_create_request_carries_the_scope_and_the_area():
    params = {"domain": None, "domain_id": DOMAIN_ID, "name": CUSTOM_NAME, "area": CUSTOM_AREA}
    request = dnspod_custom_line.create_request(FakeModels(), params)
    assert (request.DomainId, request.Name, request.Area) == (DOMAIN_ID, CUSTOM_NAME, CUSTOM_AREA)


def test_custom_line_update_request_keeps_the_name_as_pre_name():
    """``name`` is the immutable identity, so ``PreName`` is the same name."""
    params = {"domain": DOMAIN, "domain_id": None, "name": CUSTOM_NAME, "area": "198.51.100.1-198.51.100.9"}
    request = dnspod_custom_line.update_request(FakeModels(), params)
    assert (request.Name, request.PreName, request.Area) == (CUSTOM_NAME, CUSTOM_NAME, "198.51.100.1-198.51.100.9")
    assert (request.Domain, request.DomainId) == (DOMAIN, None)


def test_custom_line_delete_request_sets_the_name():
    request = dnspod_custom_line.delete_request(FakeModels(), {"domain": None, "domain_id": DOMAIN_ID, "name": CUSTOM_NAME})
    assert (request.DomainId, request.Name) == (DOMAIN_ID, CUSTOM_NAME)


# ---------------------------------------------------------------------------
# dnspod_custom_line: run_module
# ---------------------------------------------------------------------------


def test_custom_line_present_creates_a_missing_line(monkeypatch):
    client = FakeDnspodClient(custom_lines=[SAME_NAME_OTHER_DOMAIN])
    clients = _patch_module(monkeypatch, dnspod_custom_line, client)
    _custom_args()

    payload = run(dnspod_custom_line.run_module)

    assert payload.keys() == {"changed", "custom_line", "tc_api_calls"}
    assert payload["changed"] is True
    assert payload["custom_line"] == {
        "DomainId": DOMAIN_ID, "Name": CUSTOM_NAME, "Area": CUSTOM_AREA, "UseCount": 1, "MaxCount": 10,
    }
    assert _operations(payload) == ["DescribeDomainCustomLineList", "CreateDomainCustomLine", "DescribeDomainCustomLineList"]
    assert list(clients) == [
        (FakeDnspodClientClass, "dnspod.tencentcloudapi.com")
    ]
    create_request = [request for name, request in client.calls if name == "CreateDomainCustomLine"][0]
    assert (create_request.DomainId, create_request.Name, create_request.Area) == (DOMAIN_ID, CUSTOM_NAME, CUSTOM_AREA)


def test_custom_line_lookup_is_scoped_to_the_domain(monkeypatch):
    """A same-named line in another domain is not this domain's line."""
    client = FakeDnspodClient(custom_lines=[SAME_NAME_OTHER_DOMAIN, CUSTOM_LINE])
    _patch_module(monkeypatch, dnspod_custom_line, client)
    _custom_args(domain_id=DOMAIN_ID)

    payload = run(dnspod_custom_line.run_module)

    assert payload["changed"] is False
    assert payload["custom_line"]["Area"] == CUSTOM_AREA
    describe_request = client.calls[0][1]
    assert describe_request.DomainId == DOMAIN_ID


def test_custom_line_present_is_idempotent(monkeypatch):
    client = FakeDnspodClient(custom_lines=[CUSTOM_LINE])
    _patch_module(monkeypatch, dnspod_custom_line, client)
    _custom_args()

    payload = run(dnspod_custom_line.run_module)

    assert payload["changed"] is False
    assert payload["custom_line"] == CUSTOM_LINE
    assert payload.keys() == {"changed", "custom_line", "tc_api_calls"}
    assert _operations(payload) == ["DescribeDomainCustomLineList"]


def test_custom_line_present_updates_a_changed_area(monkeypatch):
    client = FakeDnspodClient(custom_lines=[CUSTOM_LINE])
    _patch_module(monkeypatch, dnspod_custom_line, client)
    _custom_args(area="198.51.100.1-198.51.100.9")

    payload = run(dnspod_custom_line.run_module)

    assert payload["changed"] is True
    assert payload["custom_line"]["Area"] == "198.51.100.1-198.51.100.9"
    assert _operations(payload) == ["DescribeDomainCustomLineList", "ModifyDomainCustomLine", "DescribeDomainCustomLineList"]
    modify_request = [request for name, request in client.calls if name == "ModifyDomainCustomLine"][0]
    assert (modify_request.Name, modify_request.PreName) == (CUSTOM_NAME, CUSTOM_NAME)


def test_custom_line_absent_deletes_an_existing_line(monkeypatch):
    client = FakeDnspodClient(custom_lines=[CUSTOM_LINE])
    _patch_module(monkeypatch, dnspod_custom_line, client)
    _custom_args(state="absent")

    payload = run(dnspod_custom_line.run_module)

    assert payload.keys() == {"changed", "custom_line", "tc_api_calls"}
    assert payload["changed"] is True
    assert payload["custom_line"] is None
    assert client.custom_lines == []
    delete_request = [request for name, request in client.calls if name == "DeleteDomainCustomLine"][0]
    assert (delete_request.DomainId, delete_request.Name) == (DOMAIN_ID, CUSTOM_NAME)


def test_custom_line_absent_missing_line_is_unchanged(monkeypatch):
    client = FakeDnspodClient()
    _patch_module(monkeypatch, dnspod_custom_line, client)
    _custom_args(state="absent")

    payload = run(dnspod_custom_line.run_module)

    assert payload.keys() == {"changed", "custom_line", "tc_api_calls"}
    assert payload["changed"] is False
    assert payload["custom_line"] is None
    assert _operations(payload) == ["DescribeDomainCustomLineList"]


def test_custom_line_check_mode_never_writes(monkeypatch):
    """A create is reported but not issued, and the diff shows both sides."""
    client = FakeDnspodClient()
    _patch_module(monkeypatch, dnspod_custom_line, client)
    _custom_args(_ansible_check_mode=True)

    payload = run(dnspod_custom_line.run_module)

    assert payload["changed"] is True
    assert payload["custom_line"] is None
    assert payload["diff"] == {"before": None, "after": {"Name": CUSTOM_NAME, "Area": CUSTOM_AREA}}
    assert _operations(payload) == ["DescribeDomainCustomLineList"]


def test_custom_line_check_mode_absent_keeps_the_line(monkeypatch):
    client = FakeDnspodClient(custom_lines=[CUSTOM_LINE])
    _patch_module(monkeypatch, dnspod_custom_line, client)
    _custom_args(state="absent", _ansible_check_mode=True)

    payload = run(dnspod_custom_line.run_module)

    assert payload["changed"] is True
    assert payload["custom_line"] == CUSTOM_LINE
    assert payload["diff"]["before"]["Name"] == CUSTOM_NAME
    assert payload["diff"]["after"] is None
    assert client.custom_lines == [CUSTOM_LINE]
    assert _operations(payload) == ["DescribeDomainCustomLineList"]


def test_custom_line_requires_the_name(monkeypatch):
    _patch_module(monkeypatch, dnspod_custom_line, FakeDnspodClient())
    module_args(domain_id=DOMAIN_ID, area=CUSTOM_AREA)

    with pytest.raises(AnsibleFailJson) as failure:
        run(dnspod_custom_line.run_module)

    assert failure.value.args[0]["msg"] == "missing required arguments: name"


def test_custom_line_requires_a_domain_scope(monkeypatch):
    _patch_module(monkeypatch, dnspod_custom_line, FakeDnspodClient())
    module_args(name=CUSTOM_NAME, area=CUSTOM_AREA)

    with pytest.raises(AnsibleFailJson) as failure:
        run(dnspod_custom_line.run_module)

    assert failure.value.args[0]["msg"] == "one of the following is required: domain, domain_id"


def test_custom_line_requires_the_area_when_present(monkeypatch):
    _patch_module(monkeypatch, dnspod_custom_line, FakeDnspodClient())
    module_args(domain_id=DOMAIN_ID, name=CUSTOM_NAME)

    with pytest.raises(AnsibleFailJson) as failure:
        run(dnspod_custom_line.run_module)

    assert failure.value.args[0]["msg"] == "state is present but all of the following are missing: area"


def test_custom_line_maps_an_sdk_error_to_the_failure_envelope(monkeypatch):
    class FakeSdkException(Exception):
        def get_code(self):
            return "UnauthorizedOperation"

        def get_request_id(self):
            return "req-line-err"

    client = FakeDnspodClient(error=FakeSdkException("not allowed to list custom lines"))
    _patch_module(monkeypatch, dnspod_custom_line, client)
    _custom_args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(dnspod_custom_line.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "not allowed to list custom lines"
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-line-err"
    assert payload["error_kind"] == "unauthorized"
    assert payload["failed"] is True


# ---------------------------------------------------------------------------
# dnspod_line_group: request builders
# ---------------------------------------------------------------------------


def test_group_create_request_joins_sorted_unique_lines():
    params = {"domain": None, "domain_id": DOMAIN_ID, "name": GROUP_NAME, "lines": ["vpn-network", "office-network", "vpn-network"]}
    request = dnspod_line_group.create_request(FakeModels(), params)
    assert (request.DomainId, request.Name) == (DOMAIN_ID, GROUP_NAME)
    assert request.Lines == "office-network,vpn-network"


def test_group_update_request_sets_the_group_id_and_exact_lines():
    params = {"domain": None, "domain_id": DOMAIN_ID, "name": GROUP_NAME, "lines": ["vpn-network", "office-network"]}
    request = dnspod_line_group.update_request(FakeModels(), params, GROUP_ID)
    assert (request.LineGroupId, request.Name) == (GROUP_ID, GROUP_NAME)
    assert request.Lines == "office-network,vpn-network"


def test_group_delete_request_sets_the_group_id():
    request = dnspod_line_group.delete_request(FakeModels(), {"domain": None, "domain_id": DOMAIN_ID}, GROUP_ID)
    assert (request.DomainId, request.LineGroupId) == (DOMAIN_ID, GROUP_ID)


# ---------------------------------------------------------------------------
# dnspod_line_group: run_module
# ---------------------------------------------------------------------------


def test_group_present_creates_a_missing_group(monkeypatch):
    client = FakeDnspodClient()
    _patch_module(monkeypatch, dnspod_line_group, client)
    _group_args()

    payload = run(dnspod_line_group.run_module)

    assert payload.keys() == {"changed", "line_group", "tc_api_calls"}
    assert payload["changed"] is True
    assert payload["line_group"]["Name"] == GROUP_NAME
    assert payload["line_group"]["Lines"] == ["office-network", "vpn-network"]
    assert _operations(payload) == ["DescribeLineGroupList", "CreateLineGroup", "DescribeLineGroupList"]
    create_request = [request for name, request in client.calls if name == "CreateLineGroup"][0]
    assert create_request.Lines == "office-network,vpn-network"


def test_group_present_is_idempotent(monkeypatch):
    client = FakeDnspodClient(line_groups=[LINE_GROUP])
    _patch_module(monkeypatch, dnspod_line_group, client)
    _group_args()

    payload = run(dnspod_line_group.run_module)

    assert payload.keys() == {"changed", "line_group", "tc_api_calls"}
    assert payload["changed"] is False
    assert payload["line_group"] == LINE_GROUP
    assert _operations(payload) == ["DescribeLineGroupList"]


def test_group_present_updates_a_changed_membership(monkeypatch):
    """The name is unchanged, so no ``line_group_id`` is needed for a modify."""
    client = FakeDnspodClient(line_groups=[LINE_GROUP])
    _patch_module(monkeypatch, dnspod_line_group, client)
    _group_args(lines=["office-network", "vpn-network", "legacy-network"])

    payload = run(dnspod_line_group.run_module)

    assert payload["changed"] is True
    assert payload["line_group"]["Lines"] == ["legacy-network", "office-network", "vpn-network"]
    assert _operations(payload) == ["DescribeLineGroupList", "ModifyLineGroup", "DescribeLineGroupList"]
    modify_request = [request for name, request in client.calls if name == "ModifyLineGroup"][0]
    assert modify_request.LineGroupId == GROUP_ID


def test_group_present_renames_only_with_the_group_id(monkeypatch):
    client = FakeDnspodClient(line_groups=[LINE_GROUP])
    _patch_module(monkeypatch, dnspod_line_group, client)
    _group_args(line_group_id=GROUP_ID, name="core-networks")

    payload = run(dnspod_line_group.run_module)

    assert payload["changed"] is True
    assert payload["line_group"]["Name"] == "core-networks"
    modify_request = [request for name, request in client.calls if name == "ModifyLineGroup"][0]
    assert (modify_request.LineGroupId, modify_request.Name) == (GROUP_ID, "core-networks")


def test_group_present_changed_name_without_the_group_id_creates_a_second_group(monkeypatch):
    """Without ``line_group_id`` the name *is* the lookup key.

    ``find`` matches on ``Name`` when no id is given, so a task that changes
    ``name`` does not find the old group: it creates another one and leaves the
    first in place. A rename is therefore always an explicit ``line_group_id``
    operation (see the test above); this pins the create-on-unknown-name
    behaviour that makes the module's own rename guard unreachable.
    """
    client = FakeDnspodClient(line_groups=[LINE_GROUP])
    _patch_module(monkeypatch, dnspod_line_group, client)
    _group_args(name="core-networks")

    payload = run(dnspod_line_group.run_module)

    assert payload["changed"] is True
    assert payload["line_group"]["Name"] == "core-networks"
    assert _recorded(client) == ["DescribeLineGroupList", "CreateLineGroup", "DescribeLineGroupList"]
    assert sorted(group["Name"] for group in client.line_groups) == ["core-networks", GROUP_NAME]


def test_group_present_fails_when_the_group_id_is_unknown(monkeypatch):
    client = FakeDnspodClient()
    _patch_module(monkeypatch, dnspod_line_group, client)
    _group_args(line_group_id=GROUP_ID)

    with pytest.raises(AnsibleFailJson) as failure:
        run(dnspod_line_group.run_module)

    assert failure.value.args[0]["msg"] == "DNSPod line_group_id was not found; omit it to create a new line group"


def test_group_find_fails_on_an_ambiguous_name(monkeypatch):
    duplicate = dict(LINE_GROUP, Id=GROUP_ID + 1)
    client = FakeDnspodClient(line_groups=[LINE_GROUP, duplicate])
    _patch_module(monkeypatch, dnspod_line_group, client)
    _group_args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(dnspod_line_group.run_module)

    assert failure.value.args[0]["msg"] == "multiple DNSPod line groups matched name; specify line_group_id"


def test_group_find_paginates_by_offset_until_total(monkeypatch):
    """101 groups: the wanted one is only on the second page."""
    groups = [dict(LINE_GROUP, Id=2000 + index, Name="group-%03d" % index) for index in range(100)]
    groups.append(dict(LINE_GROUP, Id=GROUP_ID, Name=GROUP_NAME))
    client = FakeDnspodClient(line_groups=groups)
    _patch_module(monkeypatch, dnspod_line_group, client)
    _group_args()

    payload = run(dnspod_line_group.run_module)

    assert payload["changed"] is False
    assert payload["line_group"]["Id"] == GROUP_ID
    assert [request.Offset for name, request in client.calls if name == "DescribeLineGroupList"] == [0, 100]
    assert all(request.Length == 100 for name, request in client.calls if name == "DescribeLineGroupList")


def test_group_absent_deletes_by_id(monkeypatch):
    client = FakeDnspodClient(line_groups=[LINE_GROUP])
    _patch_module(monkeypatch, dnspod_line_group, client)
    _group_args(state="absent")

    payload = run(dnspod_line_group.run_module)

    assert payload.keys() == {"changed", "line_group", "tc_api_calls"}
    assert payload["changed"] is True
    assert payload["line_group"] is None
    assert client.line_groups == []
    delete_request = [request for name, request in client.calls if name == "DeleteLineGroup"][0]
    assert (delete_request.DomainId, delete_request.LineGroupId) == (DOMAIN_ID, GROUP_ID)


def test_group_absent_missing_group_is_unchanged(monkeypatch):
    client = FakeDnspodClient()
    _patch_module(monkeypatch, dnspod_line_group, client)
    _group_args(state="absent")

    payload = run(dnspod_line_group.run_module)

    assert payload["changed"] is False
    assert payload["line_group"] is None
    assert _operations(payload) == ["DescribeLineGroupList"]


def test_group_check_mode_never_writes(monkeypatch):
    client = FakeDnspodClient()
    _patch_module(monkeypatch, dnspod_line_group, client)
    _group_args(_ansible_check_mode=True)

    payload = run(dnspod_line_group.run_module)

    assert payload["changed"] is True
    assert payload["line_group"] is None
    assert payload["diff"] == {
        "before": None,
        "after": {"Name": GROUP_NAME, "Lines": ["office-network", "vpn-network"]},
    }
    assert _operations(payload) == ["DescribeLineGroupList"]


def test_group_requires_the_lines_when_present(monkeypatch):
    _patch_module(monkeypatch, dnspod_line_group, FakeDnspodClient())
    module_args(domain_id=DOMAIN_ID, name=GROUP_NAME)

    with pytest.raises(AnsibleFailJson) as failure:
        run(dnspod_line_group.run_module)

    assert failure.value.args[0]["msg"] == "state is present but all of the following are missing: lines"


def test_group_requires_a_domain_scope(monkeypatch):
    _patch_module(monkeypatch, dnspod_line_group, FakeDnspodClient())
    module_args(name=GROUP_NAME, lines=["office-network"])

    with pytest.raises(AnsibleFailJson) as failure:
        run(dnspod_line_group.run_module)

    assert failure.value.args[0]["msg"] == "one of the following is required: domain, domain_id"


def test_group_maps_an_sdk_error_to_the_failure_envelope(monkeypatch):
    class FakeSdkException(Exception):
        def get_code(self):
            return "FailedOperation"

        def get_request_id(self):
            return "req-group-err"

    client = FakeDnspodClient(error=FakeSdkException("line group write failed"), fail_on="CreateLineGroup")
    _patch_module(monkeypatch, dnspod_line_group, client)
    _group_args()

    with pytest.raises(AnsibleFailJson) as failure:
        run(dnspod_line_group.run_module)

    payload = failure.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "line group write failed"
    assert payload["error_code"] == "FailedOperation"
    assert payload["request_id"] == "req-group-err"
