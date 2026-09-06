"""Unit tests for the cam_policy_attachment write module (helpers + run_module).

Idempotently attaches/detaches a CAM policy to a user, role or group. The
current state is read with a target-type-specific ListAttached*Policies
call (user/role read the ``List`` response field, group reads ``Policies``)
paged 200 at a time, and presence is decided by PolicyId membership. Attach
and detach are separate per-target-type mutation APIs; role mutations carry
target_id (coerced to str) and/or target_name. target_id is required for
user/group, target_id-or-target_name for role — validated before the SDK is
reached. run_module distinguishes three exit messages (up to date / would
change / updated).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cam_policy_attachment as mod
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


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "policy_id": 123456,
        "target_type": "user",
        "target_id": 1000000001,
        "target_name": None,
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


class FakeCamClient(object):
    """In-memory CamClient stand-in holding per-kind policy-id sets.

    ListAttached*Policies page over the sorted ids honouring Page/Rp (the
    user and role responses expose ``List``, the group response exposes
    ``Policies``); Attach/Detach*Policy add/remove the PolicyId.
    """

    def __init__(self, attached=None):
        self.attached = {kind: set(ids or []) for kind, ids in (attached or {}).items()}
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _list(self, kind, request, field):
        self._record("ListAttached%sPolicies" % kind.capitalize(), request)
        ids = sorted(self.attached.get(kind, []))
        start = (request.Page - 1) * request.Rp
        chunk = ids[start:start + request.Rp]
        items = [FakeResource({"PolicyId": pid}) for pid in chunk]
        response = {field: items, "TotalNum": len(ids), "RequestId": "req-fake"}
        return SimpleNamespace(**response)

    def ListAttachedUserPolicies(self, request):
        return self._list("user", request, "List")

    def ListAttachedRolePolicies(self, request):
        return self._list("role", request, "List")

    def ListAttachedGroupPolicies(self, request):
        return self._list("group", request, "Policies")

    def _mutate(self, kind, request, prefix):
        self._record("%s%sPolicy" % (prefix, kind.capitalize()), request)
        if prefix == "Attach":
            self.attached.setdefault(kind, set()).add(int(request.PolicyId))
        else:
            self.attached.get(kind, set()).discard(int(request.PolicyId))
        return SimpleNamespace(RequestId="req-fake")

    def AttachUserPolicy(self, request):
        return self._mutate("user", request, "Attach")

    def DetachUserPolicy(self, request):
        return self._mutate("user", request, "Detach")

    def AttachRolePolicy(self, request):
        return self._mutate("role", request, "Attach")

    def DetachRolePolicy(self, request):
        return self._mutate("role", request, "Detach")

    def AttachGroupPolicy(self, request):
        return self._mutate("group", request, "Attach")

    def DetachGroupPolicy(self, request):
        return self._mutate("group", request, "Detach")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load_cam",
        lambda: (FakeModels(), SimpleNamespace(CamClient=object)),
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


class _EmptyPageClient(object):
    """List calls return no items while TotalNum claims more pages."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def op(request):
            self.calls.append(name)
            return SimpleNamespace(List=[], TotalNum=500, RequestId="req-fake")

        return op


# ---------------------------------------------------------------------------
# helper tests
# ---------------------------------------------------------------------------


def test_list_request_user():
    request = mod.build_list_request(FakeModels(), _params(), page=1)
    assert request.TargetUin == 1000000001
    assert request.Page == 1
    assert request.Rp == 200
    assert not hasattr(request, "RoleName")


def test_list_request_role():
    params = _params(target_type="role", target_id=1000, target_name="deployment-role")
    request = mod.build_list_request(FakeModels(), params)
    assert request.RoleId == 1000
    assert request.RoleName == "deployment-role"
    assert request.Page == 1
    assert request.Rp == 200


def test_list_request_group():
    request = mod.build_list_request(FakeModels(), _params(target_type="group"), page=2)
    assert request.TargetGroupId == 1000000001
    assert request.Page == 2
    assert request.Rp == 200
    assert not hasattr(request, "TargetUin")


def test_list_request_respects_page_size():
    request = mod.build_list_request(FakeModels(), _params(), page=3, page_size=50)
    assert request.Page == 3
    assert request.Rp == 50


def test_mutation_request_user_attach():
    request = mod.build_mutation_request(FakeModels(), _params(), attach=True)
    assert request.PolicyId == 123456
    assert request.AttachUin == 1000000001
    assert not hasattr(request, "DetachUin")


def test_mutation_request_user_detach():
    request = mod.build_mutation_request(FakeModels(), _params(), attach=False)
    assert request.PolicyId == 123456
    assert request.DetachUin == 1000000001
    assert not hasattr(request, "AttachUin")


def test_mutation_request_group_attach():
    params = _params(target_type="group")
    request = mod.build_mutation_request(FakeModels(), params, attach=True)
    assert request.PolicyId == 123456
    assert request.AttachGroupId == 1000000001


def test_mutation_request_group_detach():
    params = _params(target_type="group")
    request = mod.build_mutation_request(FakeModels(), params, attach=False)
    assert request.PolicyId == 123456
    assert request.DetachGroupId == 1000000001


def test_mutation_request_role_attach_coerces_id_to_str():
    params = _params(target_type="role", target_id=1000, target_name="deployment-role")
    request = mod.build_mutation_request(FakeModels(), params, attach=True)
    assert request.PolicyId == 123456
    assert request.AttachRoleId == "1000"
    assert request.AttachRoleName == "deployment-role"


def test_mutation_request_role_detach_without_id():
    params = _params(target_type="role", target_id=None, target_name=None)
    request = mod.build_mutation_request(FakeModels(), params, attach=False)
    assert request.PolicyId == 123456
    assert request.DetachRoleId is None
    assert request.DetachRoleName is None


def test_is_attached_true_user_first_page():
    fake = FakeCamClient({"user": [123456]})
    module = FakeModule(_params())
    assert mod.is_attached(module, fake, FakeModels(), module.params) is True
    request = module.sdk_calls[0][1]
    assert request.TargetUin == 1000000001
    assert request.Page == 1


def test_is_attached_false_when_missing():
    fake = FakeCamClient()
    module = FakeModule(_params())
    assert mod.is_attached(module, fake, FakeModels(), module.params) is False
    assert len(module.sdk_calls) == 1


def test_is_attached_true_after_paging():
    fake = FakeCamClient({"user": list(range(101, 401))})
    module = FakeModule(_params(policy_id=350))
    assert mod.is_attached(module, fake, FakeModels(), module.params) is True
    assert len(module.sdk_calls) == 2
    assert module.sdk_calls[0][1].Page == 1
    assert module.sdk_calls[1][1].Page == 2


def test_is_attached_false_after_all_pages():
    fake = FakeCamClient({"user": list(range(101, 401))})
    module = FakeModule(_params(policy_id=999))
    assert mod.is_attached(module, fake, FakeModels(), module.params) is False
    assert len(module.sdk_calls) == 2


def test_is_attached_stops_when_page_empty():
    fake = _EmptyPageClient()
    module = FakeModule(_params())
    assert mod.is_attached(module, fake, FakeModels(), module.params) is False
    assert len(module.sdk_calls) == 1


def test_is_attached_role_uses_role_list_method():
    fake = FakeCamClient({"role": [123456]})
    params = _params(target_type="role", target_id=1000, target_name="deployment-role")
    module = FakeModule(params)
    assert mod.is_attached(module, fake, FakeModels(), params) is True
    assert module.sdk_calls[0][0].__name__ == "ListAttachedRolePolicies"
    request = module.sdk_calls[0][1]
    assert request.RoleId == 1000
    assert request.RoleName == "deployment-role"


def test_is_attached_group_reads_policies_field():
    fake = FakeCamClient({"group": [123456]})
    params = _params(target_type="group")
    module = FakeModule(params)
    assert mod.is_attached(module, fake, FakeModels(), params) is True
    assert module.sdk_calls[0][0].__name__ == "ListAttachedGroupPolicies"


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_user_target_id_required(monkeypatch):
    fake = FakeCamClient()
    _make_module(monkeypatch, fake)
    _run_args(target_id=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "target_id is required for user and group attachments" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_group_target_id_required(monkeypatch):
    fake = FakeCamClient()
    _make_module(monkeypatch, fake)
    _run_args(target_type="group", target_id=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "target_id is required for user and group attachments" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_role_requires_id_or_name(monkeypatch):
    fake = FakeCamClient()
    _make_module(monkeypatch, fake)
    _run_args(target_type="role", target_id=None, target_name=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "target_id or target_name is required for role attachments" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_missing_policy_id_fails(monkeypatch):
    fake = FakeCamClient()
    _make_module(monkeypatch, fake)
    _run_args(policy_id=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "policy_id" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_missing_target_type_fails(monkeypatch):
    fake = FakeCamClient()
    _make_module(monkeypatch, fake)
    _run_args(target_type=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "target_type" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_present_noop_when_attached(monkeypatch):
    fake = FakeCamClient({"user": [123456]})
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["attachment"] == {
        "policy_id": 123456,
        "target_type": "user",
        "target_id": 1000000001,
        "target_name": None,
    }
    assert result["msg"] == "CAM policy attachment is up to date"
    assert [c[0] for c in fake.calls] == ["ListAttachedUserPolicies"]


def test_absent_noop_when_detached(monkeypatch):
    fake = FakeCamClient()
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["attachment"] is None
    assert result["msg"] == "CAM policy attachment is up to date"
    assert [c[0] for c in fake.calls] == ["ListAttachedUserPolicies"]


def test_present_attaches_user(monkeypatch):
    fake = FakeCamClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["attachment"]["policy_id"] == 123456
    assert result["msg"] == "CAM policy attachment updated"
    assert [c[0] for c in fake.calls] == [
        "ListAttachedUserPolicies",
        "AttachUserPolicy",
    ]
    attached = fake.calls[1][1]
    assert attached.AttachUin == 1000000001
    assert attached.PolicyId == 123456
    assert 123456 in fake.attached["user"]


def test_present_check_mode_attach_is_dry_run(monkeypatch):
    fake = FakeCamClient()
    _make_module(monkeypatch, fake)
    _run_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["attachment"] is None
    assert result["msg"] == "Would change CAM policy attachment"
    assert result["diff"]["after"]["policy_id"] == 123456
    assert [c[0] for c in fake.calls] == ["ListAttachedUserPolicies"]
    assert 123456 not in fake.attached.get("user", set())


def test_absent_detaches_user(monkeypatch):
    fake = FakeCamClient({"user": [123456]})
    _make_module(monkeypatch, fake)
    _run_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["attachment"] is None
    assert result["msg"] == "CAM policy attachment updated"
    assert [c[0] for c in fake.calls] == [
        "ListAttachedUserPolicies",
        "DetachUserPolicy",
    ]
    detached = fake.calls[1][1]
    assert detached.DetachUin == 1000000001
    assert 123456 not in fake.attached["user"]


def test_absent_check_mode_detach_is_dry_run(monkeypatch):
    fake = FakeCamClient({"user": [123456]})
    _make_module(monkeypatch, fake)
    _run_args(state="absent", _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["attachment"]["policy_id"] == 123456
    assert result["msg"] == "Would change CAM policy attachment"
    assert result["diff"]["before"]["target_id"] == 1000000001
    assert result["diff"]["after"] is None
    assert [c[0] for c in fake.calls] == ["ListAttachedUserPolicies"]
    assert 123456 in fake.attached["user"]


def test_present_attaches_role_by_name(monkeypatch):
    fake = FakeCamClient()
    _make_module(monkeypatch, fake)
    _run_args(target_type="role", target_id=None, target_name="deployment-role")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["attachment"]["target_name"] == "deployment-role"
    assert result["msg"] == "CAM policy attachment updated"
    assert [c[0] for c in fake.calls] == [
        "ListAttachedRolePolicies",
        "AttachRolePolicy",
    ]
    attached = fake.calls[1][1]
    assert attached.AttachRoleId is None
    assert attached.AttachRoleName == "deployment-role"
    assert 123456 in fake.attached["role"]


def test_present_attaches_group(monkeypatch):
    fake = FakeCamClient()
    _make_module(monkeypatch, fake)
    _run_args(target_type="group")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["msg"] == "CAM policy attachment updated"
    assert [c[0] for c in fake.calls] == [
        "ListAttachedGroupPolicies",
        "AttachGroupPolicy",
    ]
    attached = fake.calls[1][1]
    assert attached.AttachGroupId == 1000000001
    assert 123456 in fake.attached["group"]


def test_absent_detaches_role(monkeypatch):
    fake = FakeCamClient({"role": [123456]})
    _make_module(monkeypatch, fake)
    _run_args(state="absent", target_type="role", target_id=1000, target_name="deployment-role")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["attachment"] is None
    assert result["msg"] == "CAM policy attachment updated"
    assert [c[0] for c in fake.calls] == [
        "ListAttachedRolePolicies",
        "DetachRolePolicy",
    ]
    detached = fake.calls[1][1]
    assert detached.DetachRoleId == "1000"
    assert detached.DetachRoleName == "deployment-role"
    assert 123456 not in fake.attached["role"]


def test_sdk_failure_reports_error_payload(monkeypatch):
    fake = _BoomClient()
    _make_module(monkeypatch, fake)
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "auth rejected"
    assert payload["error_code"] == "AuthFailure"
    assert payload["request_id"] == "req-err"


def test_main_entrypoint_runs_module(monkeypatch):
    fake = FakeCamClient({"user": [123456]})
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.main)
    assert result["changed"] is False
    assert result["attachment"]["policy_id"] == 123456
