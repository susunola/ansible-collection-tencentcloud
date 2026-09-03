"""Unit tests for the cvm_instance_security_group write module (helpers + run_module).

Reconciles the security-group set bound to a CVM instance against the
desired list. ``state=present`` makes the bound set exactly equal to
``security_group_ids`` (binding missing groups with Associate and
unbinding extras with Disassociate, one group per API call);
``state=absent`` only unbinds the requested groups, leaving the rest.
The set is capped at five groups when present; an empty desired list and
an unknown instance id are both hard failures.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cvm_instance_security_group as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


def _instance(instance_id="ins-1", groups=None):
    """API-shaped instance dict; fresh copy per call."""
    return {
        "InstanceId": instance_id,
        "SecurityGroupIds": sorted(groups or []),
    }


def _run_args(**extra):
    """module_args() with the mandatory module parameters pre-filled."""
    args = {"instance_id": "ins-1", "security_group_ids": ["sg-a", "sg-b"]}
    args.update(extra)
    return module_args(**args)


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self):
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeCvmClient(object):
    """In-memory CvmClient stand-in storing one instance's groups.

    DescribeInstances filters by InstanceIds; Associate appends (one group
    per call, deduped) and Disassociate removes, so the module's per-group
    request loop is faithfully mirrored in the stored state.
    """

    def __init__(self, instance=None, hide_instance_id=False):
        self.instance = dict(instance) if instance else None
        self.hide_instance_id = hide_instance_id
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeInstances(self, request):
        self._record("DescribeInstances", request)
        if self.instance is None or self.instance.get("InstanceId") not in (request.InstanceIds or []):
            return SimpleNamespace(InstanceSet=[], RequestId="req-fake")
        payload = dict(self.instance)
        if self.hide_instance_id:
            payload.pop("InstanceId", None)
        return SimpleNamespace(
            InstanceSet=[FakeResource(payload)],
            RequestId="req-fake",
        )

    def AssociateSecurityGroups(self, request):
        self._record("AssociateSecurityGroups", request)
        for group in request.SecurityGroupIds or []:
            if group not in self.instance["SecurityGroupIds"]:
                self.instance["SecurityGroupIds"].append(group)
        self.instance["SecurityGroupIds"].sort()
        return SimpleNamespace(RequestId="req-fake")

    def DisassociateSecurityGroups(self, request):
        self._record("DisassociateSecurityGroups", request)
        self.instance["SecurityGroupIds"] = [
            g for g in self.instance["SecurityGroupIds"] if g not in (request.SecurityGroupIds or [])
        ]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load_cvm",
        lambda: (FakeModels(), SimpleNamespace(CvmClient=object)),
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
# find_instance tests
# ---------------------------------------------------------------------------


def test_find_instance_returns_normalized_groups(monkeypatch):
    fake = FakeCvmClient(_instance(groups=["sg-b", "sg-a", "sg-c"]))
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find_instance(module, fake, FakeModels(), "ins-1")
    assert value == {"InstanceId": "ins-1", "SecurityGroupIds": ["sg-a", "sg-b", "sg-c"]}


def test_find_instance_empty_instance_set_returns_none(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    module = FakeModule()
    assert mod.find_instance(module, fake, FakeModels(), "ins-1") is None


def test_find_instance_falls_back_to_requested_id(monkeypatch):
    # InstanceId missing in the serialized payload -> the requested id is used.
    fake = FakeCvmClient(_instance(instance_id="ins-1", groups=["sg-a"]), hide_instance_id=True)
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find_instance(module, fake, FakeModels(), "ins-1")
    assert value["InstanceId"] == "ins-1"
    assert value["SecurityGroupIds"] == ["sg-a"]


def test_find_instance_no_groups_returns_empty_list(monkeypatch):
    fake = FakeCvmClient(_instance(groups=[]))
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find_instance(module, fake, FakeModels(), "ins-1")
    assert value["SecurityGroupIds"] == []


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_empty_security_group_ids_fails():
    _run_args(security_group_ids=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "security_group_ids must not be empty" in exc.value.args[0]["msg"]


def test_more_than_five_groups_fails_when_present():
    _run_args(security_group_ids=["sg-%d" % i for i in range(6)])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "at most five security groups" in exc.value.args[0]["msg"]


def test_unknown_instance_fails(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "CVM instance was not found"
    assert payload["instance_id"] == "ins-1"


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeCvmClient(_instance(groups=["sg-a", "sg-b"]))
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["security_group_ids"] == ["sg-a", "sg-b"]
    assert result["msg"] == "Security group set is up to date"
    assert not any(c[0] in ("AssociateSecurityGroups", "DisassociateSecurityGroups") for c in fake.calls)


def test_present_binds_missing_groups(monkeypatch):
    fake = FakeCvmClient(_instance(groups=["sg-a"]))
    _make_module(monkeypatch, fake)
    _run_args(security_group_ids=["sg-a", "sg-b", "sg-c"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["security_group_ids"] == ["sg-a", "sg-b", "sg-c"]
    assert result["msg"] == "Security group set updated"
    binds = [c for c in fake.calls if c[0] == "AssociateSecurityGroups"]
    assert [c[1].SecurityGroupIds for c in binds] == [["sg-b"], ["sg-c"]]  # one group per call
    assert not any(c[0] == "DisassociateSecurityGroups" for c in fake.calls)


def test_present_unbinds_extra_groups(monkeypatch):
    fake = FakeCvmClient(_instance(groups=["sg-a", "sg-b", "sg-c"]))
    _make_module(monkeypatch, fake)
    _run_args(security_group_ids=["sg-a", "sg-c"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["security_group_ids"] == ["sg-a", "sg-c"]
    unbinds = [c for c in fake.calls if c[0] == "DisassociateSecurityGroups"]
    assert [c[1].SecurityGroupIds for c in unbinds] == [["sg-b"]]
    assert not any(c[0] == "AssociateSecurityGroups" for c in fake.calls)


def test_present_binds_and_unbinds_together(monkeypatch):
    fake = FakeCvmClient(_instance(groups=["sg-old", "sg-keep"]))
    _make_module(monkeypatch, fake)
    _run_args(security_group_ids=["sg-keep", "sg-new"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["security_group_ids"] == ["sg-keep", "sg-new"]
    assert [c[0] for c in fake.calls] == [
        "DescribeInstances",
        "AssociateSecurityGroups",
        "DisassociateSecurityGroups",
    ]


def test_present_duplicate_desired_ids_dedupe(monkeypatch):
    fake = FakeCvmClient(_instance(groups=["sg-a"]))
    _make_module(monkeypatch, fake)
    _run_args(security_group_ids=["sg-a", "sg-b", "sg-b"])
    result = run(mod.run_module)
    assert result["security_group_ids"] == ["sg-a", "sg-b"]
    binds = [c for c in fake.calls if c[0] == "AssociateSecurityGroups"]
    assert len(binds) == 1
    assert binds[0][1].SecurityGroupIds == ["sg-b"]


def test_present_check_mode_lists_actions(monkeypatch):
    fake = FakeCvmClient(_instance(groups=["sg-old"]))
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, security_group_ids=["sg-new"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["security_group_ids"] == ["sg-new"]
    assert result["msg"] == "Would bind ['sg-new'], unbind ['sg-old']"
    assert not any(c[0] in ("AssociateSecurityGroups", "DisassociateSecurityGroups") for c in fake.calls)
    assert fake.instance["SecurityGroupIds"] == ["sg-old"]


def test_present_check_mode_bind_only(monkeypatch):
    fake = FakeCvmClient(_instance(groups=["sg-a"]))
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, security_group_ids=["sg-a", "sg-b"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Would bind ['sg-b']"


def test_absent_noop_when_none_bound(monkeypatch):
    fake = FakeCvmClient(_instance(groups=["sg-x"]))
    _make_module(monkeypatch, fake)
    _run_args(state="absent", security_group_ids=["sg-a"])
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["security_group_ids"] == ["sg-x"]
    assert result["msg"] == "Security groups already absent"
    assert not any(c[0] == "DisassociateSecurityGroups" for c in fake.calls)


def test_absent_unbinds_intersection_only(monkeypatch):
    fake = FakeCvmClient(_instance(groups=["sg-a", "sg-b", "sg-c"]))
    _make_module(monkeypatch, fake)
    _run_args(state="absent", security_group_ids=["sg-a", "sg-ghost"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["security_group_ids"] == ["sg-b", "sg-c"]  # sg-ghost untouched, not an error
    assert result["msg"] == "Unbound ['sg-a']"
    unbinds = [c for c in fake.calls if c[0] == "DisassociateSecurityGroups"]
    assert [c[1].SecurityGroupIds for c in unbinds] == [["sg-a"]]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCvmClient(_instance(groups=["sg-a", "sg-b"]))
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True, state="absent", security_group_ids=["sg-a"])
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["security_group_ids"] == ["sg-b"]
    assert result["msg"] == "Would unbind ['sg-a']"
    assert not any(c[0] == "DisassociateSecurityGroups" for c in fake.calls)
    assert fake.instance["SecurityGroupIds"] == ["sg-a", "sg-b"]


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load_cvm",
        lambda: (FakeModels(), SimpleNamespace(CvmClient=object)),
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
