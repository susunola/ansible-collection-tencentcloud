"""Unit tests for the tcb_environment write module (helpers + run_module).

Creates, renames and destroys Tencent CloudBase environments. Lookup is a
paginated DescribeEnvs walk that matches by ``env_id`` when given, otherwise
by ``alias``; multiple matches fail. ``state=absent`` destroys the matched
environment; a present run without a match validates the creation parameters
and calls CreateEnv. Check mode reports targets/diffs without any write.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tcb_environment as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)


class _HelperModels(object):
    """Models stand-in whose ExternalStorage supports from_json_string."""

    class Tag(object):
        pass

    class CreateEnvRequest(object):
        pass

    class ExternalStorage(object):
        def __init__(self):
            self.raw = None

        def from_json_string(self, text):
            self.raw = json.loads(text)


def _environment(**overrides):
    """API-shaped environment dict isolated from the shared constant."""
    item = {"EnvId": "env-1", "Alias": "prod-env"}
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "env_id": None,
        "alias": "prod-env",
        "package_id": "baas_package",
        "resources": ["flexdb", "storage"],
        "period": 1,
        "auto_voucher": None,
        "tags": None,
        "renew_flag": None,
        "external_storage": None,
        "enable_overrun": None,
        "force_destroy": False,
        "bypass_destroy_check": False,
    }
    params.update(overrides)
    return params


def _clean_params(**overrides):
    """_params() with None-valued keys dropped.

    Several parameters are no-default ``choices``/free parameters; Ansible
    treats an explicit None as not-specified, but dropping the keys keeps the
    injected args identical to a real playbook invocation.
    """
    return {key: value for key, value in _params(**overrides).items() if value is not None}


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    return module_args(**dict(_clean_params(), **extra))


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


class FakeTcbClient(object):
    """In-memory TcbClient stand-in storing environment dicts.

    DescribeEnvs honours Offset/Limit so the module's pagination loop can be
    exercised; each item is wrapped in a :class:`FakeResource` because the
    module calls ``item._serialize(allow_none=True)``.
    """

    def __init__(self, environments=None):
        self.environments = [copy.deepcopy(e) for e in (environments or [])]
        self.calls = []
        self.next_id = len(self.environments) + 1

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeEnvs(self, request):
        self._record("DescribeEnvs", request)
        offset = request.Offset
        page = self.environments[offset : offset + request.Limit]
        return SimpleNamespace(
            EnvList=[FakeResource(dict(e)) for e in page],
            Total=len(self.environments),
            RequestId="req-fake",
        )

    def CreateEnv(self, request):
        self._record("CreateEnv", request)
        env_id = "env-%d" % self.next_id
        self.next_id += 1
        self.environments.append({"EnvId": env_id, "Alias": request.Alias})
        return SimpleNamespace(EnvId=env_id, RequestId="req-fake")

    def ModifyEnv(self, request):
        self._record("ModifyEnv", request)
        for env in self.environments:
            if env["EnvId"] == request.EnvId:
                env["Alias"] = request.Alias
        return SimpleNamespace(RequestId="req-fake")

    def DestroyEnv(self, request):
        self._record("DestroyEnv", request)
        self.environments = [e for e in self.environments if e["EnvId"] != request.EnvId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TcbClient=object)),
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
# request-builder / helper tests
# ---------------------------------------------------------------------------


def test_model_none_returns_none():
    assert mod._model(_HelperModels.ExternalStorage, None) is None


def test_model_populates_from_json():
    value = mod._model(_HelperModels.ExternalStorage, {"size": 2, "flag": True})
    assert value.raw == {"size": 2, "flag": True}


def test_tags_none_returns_empty():
    assert mod._tags(FakeModels(), None) == []


def test_tags_sorted_and_coerced_to_string():
    tags = mod._tags(FakeModels(), {"z": 2, "a": "1"})
    assert [(tag.Key, tag.Value) for tag in tags] == [("a", "1"), ("z", "2")]


def test_describe_request_defaults():
    request = mod.describe_request(FakeModels())
    assert request.EnvId is None
    assert request.Offset == 0
    assert request.Limit == 100


def test_describe_request_with_env_id_and_offset():
    request = mod.describe_request(FakeModels(), env_id="env-9", offset=100)
    assert request.EnvId == "env-9"
    assert request.Offset == 100
    assert request.Limit == 100


def test_create_request_maps_all_fields():
    models = _HelperModels()
    request = mod.create_request(
        models,
        _params(
            auto_voucher=True,
            tags={"env": "prod"},
            renew_flag="NOTIFY_AND_MANUAL_RENEW",
            external_storage={"size": 1},
            enable_overrun="TRUE",
        ),
    )
    assert request.Alias == "prod-env"
    assert request.PackageId == "baas_package"
    assert request.Resources == ["flexdb", "storage"]
    assert request.Period == 1
    assert request.AutoVoucher is True
    assert request.RenewFlag == "NOTIFY_AND_MANUAL_RENEW"
    assert request.EnableOverrun == "TRUE"
    assert [(tag.Key, tag.Value) for tag in request.Tags] == [("env", "prod")]
    assert request.ExternalStorage.raw == {"size": 1}


def test_create_request_optional_fields_stay_none():
    request = mod.create_request(_HelperModels(), _params())
    assert request.AutoVoucher is None
    assert request.Tags == []
    assert request.ExternalStorage is None
    assert request.RenewFlag is None
    assert request.EnableOverrun is None


def test_update_request_fields():
    request = mod.update_request(FakeModels(), "env-9", "new-alias")
    assert request.EnvId == "env-9"
    assert request.Alias == "new-alias"


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params(force_destroy=True, bypass_destroy_check=True), "env-9")
    assert request.EnvId == "env-9"
    assert request.IsForce is True
    assert request.BypassCheck is True


def test_find_matches_by_env_id(monkeypatch):
    fake = FakeTcbClient([_environment(EnvId="env-1", Alias="a"), _environment(EnvId="env-2", Alias="b")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(env_id="env-2", alias=None))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["EnvId"] == "env-2"


def test_find_matches_by_alias_when_no_env_id(monkeypatch):
    fake = FakeTcbClient([_environment(EnvId="env-1", Alias="b"), _environment(EnvId="env-2", Alias="prod-env")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["EnvId"] == "env-2"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeTcbClient([_environment(Alias="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(alias="ghost"))
    assert mod.find(module, fake, FakeModels(), module.params) is None


def test_find_paginates_past_first_page(monkeypatch):
    environments = [{"EnvId": "env-%03d" % i, "Alias": "alias-%03d" % i} for i in range(150)]
    fake = FakeTcbClient(environments)
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(env_id="env-142", alias=None))
    value = mod.find(module, fake, FakeModels(), module.params)
    assert value["EnvId"] == "env-142"
    assert len([c for c in fake.calls if c[0] == "DescribeEnvs"]) == 2


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeTcbClient([_environment(EnvId="env-1"), _environment(EnvId="env-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params())
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, FakeModels(), module.params)
    assert "Multiple CloudBase environments matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_requires_env_id_or_alias():
    module_args(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    msg = exc.value.args[0]["msg"]
    assert "env_id" in msg and "alias" in msg


def test_present_creates_environment(monkeypatch):
    fake = FakeTcbClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["environment"]["EnvId"] == "env-1"
    assert result["environment"]["Alias"] == "prod-env"
    assert len([c for c in fake.calls if c[0] == "CreateEnv"]) == 1
    assert len([c for c in fake.calls if c[0] == "DescribeEnvs"]) == 2  # find + refetch


def test_present_missing_creation_parameters_fails(monkeypatch):
    fake = FakeTcbClient()
    _make_module(monkeypatch, fake)
    _run_args(env_id="env-ghost", alias=None, package_id=None, resources=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert sorted(payload["missing"]) == ["alias", "package_id", "resources"]


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeTcbClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **dict(_clean_params()))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["environment"] == {"Alias": "prod-env", "PackageId": "baas_package", "Resources": ["flexdb", "storage"]}
    assert not any(c[0] == "CreateEnv" for c in fake.calls)


def test_present_noop_when_alias_matches(monkeypatch):
    fake = FakeTcbClient([_environment(EnvId="env-9", Alias="prod-env")])
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["environment"]["EnvId"] == "env-9"
    assert not any(c[0] in ("CreateEnv", "ModifyEnv", "DestroyEnv") for c in fake.calls)


def test_present_noop_when_env_id_matches_without_alias(monkeypatch):
    fake = FakeTcbClient([_environment(EnvId="env-9", Alias="old-alias")])
    _make_module(monkeypatch, fake)
    _run_args(env_id="env-9", alias=None)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["environment"]["Alias"] == "old-alias"


def test_present_renames_environment(monkeypatch):
    fake = FakeTcbClient([_environment(EnvId="env-9", Alias="old-alias")])
    _make_module(monkeypatch, fake)
    _run_args(env_id="env-9", alias="prod-env")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["environment"]["Alias"] == "prod-env"
    rename = [c for c in fake.calls if c[0] == "ModifyEnv"][0][1]
    assert rename.EnvId == "env-9"
    assert rename.Alias == "prod-env"
    assert len([c for c in fake.calls if c[0] == "DescribeEnvs"]) == 2  # find + refetch


def test_present_check_mode_rename_is_dry_run(monkeypatch):
    fake = FakeTcbClient([_environment(EnvId="env-9", Alias="old-alias")])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **dict(_clean_params(env_id="env-9", alias="prod-env")))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["environment"] == {"Alias": "prod-env"}
    assert not any(c[0] == "ModifyEnv" for c in fake.calls)


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeTcbClient([_environment(Alias="other")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", alias="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["environment"] is None
    assert not any(c[0] == "DestroyEnv" for c in fake.calls)


def test_absent_destroys_environment(monkeypatch):
    fake = FakeTcbClient([_environment(EnvId="env-9", Alias="prod-env")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", force_destroy=True, bypass_destroy_check=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["environment"] is None
    destroy = [c for c in fake.calls if c[0] == "DestroyEnv"][0][1]
    assert destroy.EnvId == "env-9"
    assert destroy.IsForce is True
    assert destroy.BypassCheck is True
    assert fake.environments == []


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTcbClient([_environment(EnvId="env-9", Alias="prod-env")])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **dict(_clean_params(state="absent")))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["environment"] is None
    assert not any(c[0] == "DestroyEnv" for c in fake.calls)
    assert len(fake.environments) == 1


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(TcbClient=object)),
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
