"""Unit tests for the tse_config_file_group write module (run_module flows).

``run_module()`` creates, updates and deletes a namespace-scoped TSE
configuration group with exact operator sets. It is driven end to end
against an in-memory fake client whose create/modify/delete operations
mutate a group store, so the post-write ``DescribeConfigFileGroups``
refetch converges immediately.

Scenario matrix:

* absent without a group (idempotent) / check-mode delete / real delete
* creation when missing (check mode and real create)
* idempotent no-op when the live group already matches the operator set
* operator-set drift: adding users, removing users, and mixed changes
* comment drift updates through the modify API
* duplicate-match and blanket ``sdk_error_payload`` failure paths
* legacy helper regression tests (folded from test_tse_config_file_group.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_config_file_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "ins-tse-abc"
NAMESPACE = "production"
GROUP_NAME = "application"


def _base(**overrides):
    params = {
        "state": "present",
        "instance_id": INSTANCE_ID,
        "namespace": NAMESPACE,
        "name": GROUP_NAME,
    }
    params.update(overrides)
    return module_args(**params)


def _group(extra=None):
    value = {"Name": GROUP_NAME, "Namespace": NAMESPACE, "Comment": "order service"}
    if extra:
        value.update(extra)
    return value


class FakeConfigFileGroupClient(object):
    """In-memory TSE client holding configuration groups by identity."""

    def __init__(self, groups=None):
        self.groups = {}
        for value in (groups or []):
            self.groups[self._key(value)] = copy.deepcopy(value)
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    @staticmethod
    def _key(value):
        return (value["Namespace"], value["Name"])

    def _values(self):
        return list(self.groups.values())

    def DescribeConfigFileGroups(self, request):
        self._record("DescribeConfigFileGroups", request)
        assert request.InstanceId == INSTANCE_ID
        return SimpleNamespace(
            ConfigFileGroups=[FakeResource(item) for item in self._values()],
            RequestId="req-fake",
        )

    def CreateConfigFileGroup(self, request):
        self._record("CreateConfigFileGroup", request)
        payload = dict(request.ConfigFileGroup.__dict__)
        self.groups[self._key(payload)] = payload
        return SimpleNamespace(RequestId="req-fake")

    def ModifyConfigFileGroup(self, request):
        self._record("ModifyConfigFileGroup", request)
        payload = dict(request.ConfigFileGroup.__dict__)
        old = dict(self.groups[self._key(payload)])
        result = dict(old)
        for key in ("UserIds", "GroupIds", "RemoveUserIds", "RemoveGroupIds"):
            result.pop(key, None)
        for key in payload:
            if key not in ("UserIds", "GroupIds", "RemoveUserIds", "RemoveGroupIds"):
                result[key] = payload[key]
        for keep_key, remove_key in (("UserIds", "RemoveUserIds"), ("GroupIds", "RemoveGroupIds")):
            kept = set(old.get(keep_key) or []) - set(payload.get(remove_key) or [])
            kept |= set(payload.get(keep_key) or [])
            result[keep_key] = sorted(kept)
        self.groups[self._key(payload)] = result
        return SimpleNamespace(RequestId="req-fake")

    def DeleteConfigFileGroup(self, request):
        self._record("DeleteConfigFileGroup", request)
        self.groups.pop((request.Namespace, request.Group), None)
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [name for name, unused in fake.calls]


def _payload_of(fake, operation):
    request = next(request for name, request in fake.calls if name == operation)
    return request.ConfigFileGroup.__dict__


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_without_group_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeConfigFileGroupClient())
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["group"] is None
    assert _names(fake) == ["DescribeConfigFileGroups"]


def test_absent_deletes_existing_group(monkeypatch):
    fake = _make_module(monkeypatch, FakeConfigFileGroupClient(groups=[_group()]))
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"] is None
    assert fake.groups == {}
    assert _names(fake) == ["DescribeConfigFileGroups", "DeleteConfigFileGroup"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeConfigFileGroupClient(groups=[_group()]))
    _base(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.groups) == 1
    assert "DeleteConfigFileGroup" not in _names(fake)


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_present_creates_missing_group(monkeypatch):
    fake = _make_module(monkeypatch, FakeConfigFileGroupClient())
    _base(comment="order service", user_ids=["u1", "u2"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["Name"] == GROUP_NAME
    assert result["group"]["UserIds"] == ["u1", "u2"]
    assert len(fake.groups) == 1
    payload = _payload_of(fake, "CreateConfigFileGroup")
    assert payload["UserIds"] == ["u1", "u2"]
    assert _names(fake) == ["DescribeConfigFileGroups", "CreateConfigFileGroup", "DescribeConfigFileGroups"]


def test_present_create_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeConfigFileGroupClient())
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"] == {"Name": GROUP_NAME, "Namespace": NAMESPACE}
    assert fake.groups == {}
    assert "CreateConfigFileGroup" not in _names(fake)


# ---------------------------------------------------------------------------
# idempotent and drift flows
# ---------------------------------------------------------------------------


def test_converged_identity_only_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeConfigFileGroupClient(groups=[_group()]))
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["group"]["Comment"] == "order service"
    assert _names(fake) == ["DescribeConfigFileGroups"]


def test_converged_operator_set_is_idempotent(monkeypatch):
    group = _group(extra={"UserIds": ["u1", "u2"], "GroupIds": ["g1"], "FileCount": 4})
    fake = _make_module(monkeypatch, FakeConfigFileGroupClient(groups=[group]))
    _base(user_ids=["u2", "u1"], group_ids=["g1"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert _names(fake) == ["DescribeConfigFileGroups"]


def test_user_removal_drift_updates_group(monkeypatch):
    group = _group(extra={"UserIds": ["u1", "u2"], "GroupIds": []})
    fake = _make_module(monkeypatch, FakeConfigFileGroupClient(groups=[group]))
    _base(user_ids=["u2"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["UserIds"] == ["u2"]
    payload = _payload_of(fake, "ModifyConfigFileGroup")
    assert payload["UserIds"] == []
    assert payload["RemoveUserIds"] == ["u1"]


def test_user_addition_drift_updates_group(monkeypatch):
    group = _group(extra={"UserIds": ["u1"], "GroupIds": []})
    fake = _make_module(monkeypatch, FakeConfigFileGroupClient(groups=[group]))
    _base(user_ids=["u1", "u2", "u3"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["UserIds"] == ["u1", "u2", "u3"]
    payload = _payload_of(fake, "ModifyConfigFileGroup")
    assert payload["UserIds"] == ["u2", "u3"]
    assert payload["RemoveUserIds"] == []


def test_mixed_user_delta_drift(monkeypatch):
    group = _group(extra={"UserIds": ["u1", "u2"], "GroupIds": []})
    fake = _make_module(monkeypatch, FakeConfigFileGroupClient(groups=[group]))
    _base(user_ids=["u2", "u3"], group_ids=["g9"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["UserIds"] == ["u2", "u3"]
    assert result["group"]["GroupIds"] == ["g9"]
    payload = _payload_of(fake, "ModifyConfigFileGroup")
    assert payload["UserIds"] == ["u3"]
    assert payload["RemoveUserIds"] == ["u1"]
    assert payload["GroupIds"] == ["g9"]
    assert payload["RemoveGroupIds"] == []


def test_comment_drift_updates_group(monkeypatch):
    fake = _make_module(monkeypatch, FakeConfigFileGroupClient(groups=[_group()]))
    _base(comment="reworded description")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["Comment"] == "reworded description"
    assert "ModifyConfigFileGroup" in _names(fake)


def test_drift_check_mode_is_dry_run(monkeypatch):
    group = _group(extra={"UserIds": ["u1", "u2"], "GroupIds": []})
    fake = _make_module(monkeypatch, FakeConfigFileGroupClient(groups=[group]))
    _base(user_ids=["u2"], _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["group"]["UserIds"] == ["u2"]
    assert "diff" in result
    assert fake.groups[(NAMESPACE, GROUP_NAME)]["UserIds"] == ["u1", "u2"]
    assert "ModifyConfigFileGroup" not in _names(fake)


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_multiple_matches_fail(monkeypatch):
    class DuplicateClient(object):
        def DescribeConfigFileGroups(self, request):
            assert request.InstanceId == INSTANCE_ID
            return SimpleNamespace(
                ConfigFileGroups=[FakeResource(_group(extra={"Id": "one"})), FakeResource(_group(extra={"Id": "dup"}))],
                RequestId="req-fake",
            )

    _make_module(monkeypatch, DuplicateClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Multiple TSE configuration groups matched" in payload["msg"]
    assert payload["name"] == GROUP_NAME


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeConfigFileGroups(self, request):
            raise Boom("tse endpoint unreachable")

    _make_module(monkeypatch, ExplodingClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "tse endpoint unreachable" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tse_config_file_group.py)
# ---------------------------------------------------------------------------


def test_desired_sorts_operator_sets_and_skips_none():
    p = {
        "name": "app",
        "namespace": "prod",
        "comment": None,
        "department": "platform",
        "business": None,
        "user_ids": ["u2", "u1"],
        "group_ids": [],
        "tags": None,
    }
    target = mod.desired(p)
    assert target["Name"] == "app"
    assert target["Namespace"] == "prod"
    assert target["Department"] == "platform"
    assert target["UserIds"] == ["u1", "u2"]
    assert target["GroupIds"] == []
    assert "Comment" not in target
    assert "Business" not in target


def test_mutation_calculates_exact_remove_deltas():
    target = mod.desired({"name": "app", "namespace": "prod", "user_ids": ["u2"], "group_ids": []})
    current = {"Name": "app", "Namespace": "prod", "UserIds": ["u1"], "GroupIds": [], "FileCount": 4}
    value = mod.mutation(current, target)
    assert value["UserIds"] == ["u2"]
    assert value["RemoveUserIds"] == ["u1"]
    assert value["RemoveGroupIds"] == []


def test_comparable_equals_target_after_reconciliation():
    target = mod.desired({"name": "app", "namespace": "prod", "user_ids": ["u2"], "group_ids": []})
    assert mod.comparable(dict(target, UserIds=["u2"]), target) == target
    assert mod.comparable(dict(target, UserIds=["u1"]), target) != target
