"""Unit tests for the cvm_launch_template_version write module.

Creates, deletes and force-replaces immutable CVM launch-template
versions. A version is selected by number or by exact description;
version *data* is immutable, so configuration drift on an existing
version requires ``force_replace`` (create a new version from the
template data, optionally promote it to default, then delete the old
one). The module calls ``request._deserialize(template_data)`` in
``create_request``, so the request classes stand in here inherit a
``_deserialize`` that copies keys onto the instance. The fake CVM client
stores version dicts and synthesizes new ``LaunchTemplateVersionNumber``
values; ``ModifyLaunchTemplateDefaultVersion`` toggles the default flag
so the module's post-write refetches converge.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cvm_launch_template_version as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

TEMPLATE_DATA = {
    "ImageId": "img-1",
    "InstanceType": "S5.LARGE8",
    "Placement": {"Zone": "ap-guangzhou-3"},
}


class _Deserializable(object):
    """SDK request stand-in exposing ``_deserialize`` like the real models."""

    def _deserialize(self, data):
        for key, value in (data or {}).items():
            setattr(self, key, value)


class _CvmModels(object):
    """Models stand-in whose requests can ``_deserialize`` template data."""

    def __getattr__(self, name):
        return type(name, (_Deserializable,), {})


def _version(**overrides):
    """API-shaped launch-template version dict isolated from the constant."""
    item = {
        "LaunchTemplateId": "lt-abc",
        "LaunchTemplateVersion": 1,
        "LaunchTemplateVersionDescription": "web-v2",
        "LaunchTemplateVersionData": dict(TEMPLATE_DATA),
        "IsDefaultVersion": False,
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "template_id": "lt-abc",
        "version": None,
        "description": "web-v2",
        "template_data": dict(TEMPLATE_DATA),
        "base_version": None,
        "make_default": False,
        "force_replace": False,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    return module_args(**{k: v for k, v in _params(**extra).items() if v is not None})


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


class FakeCvmClient(object):
    """In-memory CvmClient stand-in storing launch-template versions.

    Describe filters by the request's LaunchTemplateVersions list when
    present (the module only ever asks for one version at a time).
    CreateLaunchTemplateVersion synthesizes the next version number and
    stores a version whose data mirrors the request's ``_deserialize``d
    template keys. ModifyLaunchTemplateDefaultVersion flips the
    ``IsDefaultVersion`` flags so a follow-up describe converges.
    """

    def __init__(self, versions=None):
        self.versions = [copy.deepcopy(v) for v in (versions or [])]
        self.calls = []
        self._next_version = 100

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeLaunchTemplateVersions(self, request):
        self._record("DescribeLaunchTemplateVersions", request)
        wanted = set(getattr(request, "LaunchTemplateVersions", None) or [])
        versions = self.versions
        if wanted:
            versions = [v for v in versions if v.get("LaunchTemplateVersion") in wanted]
        return SimpleNamespace(
            LaunchTemplateVersionSet=[FakeResource(dict(v)) for v in versions],
            RequestId="req-fake",
        )

    def CreateLaunchTemplateVersion(self, request):
        self._record("CreateLaunchTemplateVersion", request)
        number = self._next_version
        self._next_version += 1
        data = {
            key: value
            for key, value in vars(request).items()
            if key not in ("LaunchTemplateId", "LaunchTemplateVersionDescription", "LaunchTemplateVersion")
        }
        self.versions.append(
            {
                "LaunchTemplateId": request.LaunchTemplateId,
                "LaunchTemplateVersion": number,
                "LaunchTemplateVersionDescription": request.LaunchTemplateVersionDescription,
                "LaunchTemplateVersionData": data,
                "IsDefaultVersion": False,
            }
        )
        return SimpleNamespace(LaunchTemplateVersionNumber=number, RequestId="req-fake")

    def ModifyLaunchTemplateDefaultVersion(self, request):
        self._record("ModifyLaunchTemplateDefaultVersion", request)
        for stored in self.versions:
            stored["IsDefaultVersion"] = stored.get("LaunchTemplateVersion") == request.DefaultVersion
        return SimpleNamespace(RequestId="req-fake")

    def DeleteLaunchTemplateVersions(self, request):
        self._record("DeleteLaunchTemplateVersions", request)
        remove = set(request.LaunchTemplateVersions)
        self.versions = [v for v in self.versions if v.get("LaunchTemplateVersion") not in remove]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (_CvmModels(), SimpleNamespace(CvmClient=object)),
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


def test_describe_request_with_version():
    request = mod.describe_request(FakeModels(), _params(version=3))
    assert request.LaunchTemplateId == "lt-abc"
    assert request.Offset == 0
    assert request.Limit == 100
    assert request.LaunchTemplateVersions == [3]


def test_describe_request_without_version():
    request = mod.describe_request(FakeModels(), _params(version=None), offset=50)
    assert request.Offset == 50
    assert not hasattr(request, "LaunchTemplateVersions")


def test_create_request_deserializes_template_data():
    request = mod.create_request(_CvmModels(), _params(base_version=2, template_data={"ImageId": "img-x", "Placement": {"Zone": "ap-guangzhou-3"}}))
    assert request.LaunchTemplateId == "lt-abc"
    assert request.LaunchTemplateVersionDescription == "web-v2"
    assert request.LaunchTemplateVersion == 2  # base_version
    assert request.ImageId == "img-x"
    assert request.Placement == {"Zone": "ap-guangzhou-3"}


def test_create_request_without_base_version():
    request = mod.create_request(_CvmModels(), _params(base_version=None))
    assert request.LaunchTemplateVersion is None
    assert request.ImageId == "img-1"


def test_default_request_fields():
    request = mod.default_request(FakeModels(), _params(), 7)
    assert request.LaunchTemplateId == "lt-abc"
    assert request.DefaultVersion == 7


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params(), 4)
    assert request.LaunchTemplateId == "lt-abc"
    assert request.LaunchTemplateVersions == [4]


def test_subset_nested_dict_semantics():
    current = {"Placement": {"Zone": "ap-guangzhou-3", "Extra": 1}, "ImageId": "img-1"}
    assert mod._subset(current, {"Placement": {"Zone": "ap-guangzhou-3"}}) is True
    assert mod._subset(current, {"Placement": {"Zone": "ap-guangzhou-4"}}) is False
    assert mod._subset(current, {"ImageId": "img-1", "Placement": {"Zone": "ap-guangzhou-3"}}) is True
    assert mod._subset(current, {"Missing": 1}) is False
    assert mod._subset("not-a-dict", {"Placement": {"Zone": "x"}}) is False


def test_subset_list_and_scalar_equality():
    assert mod._subset([1, 2], [1, 2]) is True
    assert mod._subset([1, 2], [2, 1]) is False
    assert mod._subset("img-1", "img-1") is True
    assert mod._subset("img-1", "img-2") is False


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_matches_by_version(monkeypatch):
    fake = FakeCvmClient([_version(), _version(LaunchTemplateVersion=2, LaunchTemplateVersionDescription="other")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(version=2, description=None))
    value = mod.find(module, fake, _CvmModels(), module.params)
    assert value["LaunchTemplateVersion"] == 2


def test_find_matches_by_description(monkeypatch):
    fake = FakeCvmClient([_version(LaunchTemplateVersionDescription="legacy"), _version()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(version=None))
    value = mod.find(module, fake, _CvmModels(), module.params)
    assert value["LaunchTemplateVersion"] == 1


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeCvmClient([_version()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(version=None, description="ghost"))
    assert mod.find(module, fake, _CvmModels(), module.params) is None


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeCvmClient([_version(LaunchTemplateVersion=1), _version(LaunchTemplateVersion=9, LaunchTemplateVersionData=dict(TEMPLATE_DATA))])
    fake.versions[1]["LaunchTemplateVersionDescription"] = "web-v2"  # two versions share the description
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(version=None))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, _CvmModels(), module.params)
    assert "Multiple launch-template versions matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_requires_version_or_description():
    module_args(state="present", template_id="lt-abc")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    msg = exc.value.args[0]["msg"]
    assert "version" in msg and "description" in msg


def test_present_missing_description_or_data_fails_before_sdk():
    module_args(state="present", template_id="lt-abc", version=5)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "description and template_data are required when state=present"


def test_present_creates_new_version(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    version = result["launch_template_version"]
    assert version["LaunchTemplateVersion"] == 100
    assert version["LaunchTemplateVersionDescription"] == "web-v2"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeLaunchTemplateVersions") == 2  # find + post-create refetch
    assert names.count("CreateLaunchTemplateVersion") == 1
    assert "DeleteLaunchTemplateVersions" not in names
    assert len(fake.versions) == 1


def test_present_create_promotes_default(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    _run_args(make_default=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["launch_template_version"]["IsDefaultVersion"] is True
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyLaunchTemplateDefaultVersion") == 1
    default = [c for c in fake.calls if c[0] == "ModifyLaunchTemplateDefaultVersion"][0][1]
    assert default.DefaultVersion == 100


def test_present_noop_when_data_matches(monkeypatch):
    fake = FakeCvmClient([_version()])
    _make_module(monkeypatch, fake)
    _run_args(version=1)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["launch_template_version"]["LaunchTemplateVersion"] == 1
    assert [c[0] for c in fake.calls] == ["DescribeLaunchTemplateVersions"]  # find only


def test_present_noop_when_default_matches(monkeypatch):
    fake = FakeCvmClient([_version(IsDefaultVersion=True)])
    _make_module(monkeypatch, fake)
    _run_args(version=1, make_default=True)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert [c[0] for c in fake.calls] == ["DescribeLaunchTemplateVersions"]


def test_present_data_drift_without_force_fails(monkeypatch):
    fake = FakeCvmClient([_version()])
    _make_module(monkeypatch, fake)
    _run_args(version=1, template_data={"ImageId": "img-2", "InstanceType": "S5.LARGE8", "Placement": {"Zone": "ap-guangzhou-3"}})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "launch-template versions are immutable" in payload["msg"]
    assert payload["version"] == 1
    assert [c[0] for c in fake.calls] == ["DescribeLaunchTemplateVersions"]  # no write


def test_present_force_replace_creates_then_deletes_old(monkeypatch):
    fake = FakeCvmClient([_version()])
    _make_module(monkeypatch, fake)
    _run_args(
        version=1,
        template_data={"ImageId": "img-2", "InstanceType": "S5.LARGE8", "Placement": {"Zone": "ap-guangzhou-3"}},
        force_replace=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    version = result["launch_template_version"]
    assert version["LaunchTemplateVersion"] == 100
    names = [c[0] for c in fake.calls]
    assert names == [
        "DescribeLaunchTemplateVersions",  # initial find (version 1)
        "CreateLaunchTemplateVersion",  # new version 100
        "DescribeLaunchTemplateVersions",  # refetch version 100
        "DeleteLaunchTemplateVersions",  # drop old version 1
    ]
    delete = [c for c in fake.calls if c[0] == "DeleteLaunchTemplateVersions"][0][1]
    assert delete.LaunchTemplateVersions == [1]
    assert [v["LaunchTemplateVersion"] for v in fake.versions] == [100]


def test_present_force_replace_preserves_default(monkeypatch):
    fake = FakeCvmClient([_version(IsDefaultVersion=True)])
    _make_module(monkeypatch, fake)
    _run_args(
        version=1,
        make_default=True,
        template_data={"ImageId": "img-2", "InstanceType": "S5.LARGE8", "Placement": {"Zone": "ap-guangzhou-3"}},
        force_replace=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    version = result["launch_template_version"]
    assert version["LaunchTemplateVersion"] == 100
    assert version["IsDefaultVersion"] is True
    names = [c[0] for c in fake.calls]
    assert names.count("ModifyLaunchTemplateDefaultVersion") == 1
    assert names.count("DeleteLaunchTemplateVersions") == 1
    assert len(fake.versions) == 1
    assert fake.versions[0]["LaunchTemplateVersion"] == 100
    assert fake.versions[0]["IsDefaultVersion"] is True


def test_present_make_default_promotes_existing_non_default(monkeypatch):
    fake = FakeCvmClient([_version()])  # version 1 exists, not default
    _make_module(monkeypatch, fake)
    _run_args(version=1, make_default=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["launch_template_version"]["LaunchTemplateVersion"] == 1
    assert result["launch_template_version"]["IsDefaultVersion"] is True
    names = [c[0] for c in fake.calls]
    assert names == [
        "DescribeLaunchTemplateVersions",  # find
        "ModifyLaunchTemplateDefaultVersion",  # promote version 1
        "DescribeLaunchTemplateVersions",  # refetch
    ]
    assert "CreateLaunchTemplateVersion" not in names


def test_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeCvmClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["launch_template_version"] is None
    assert [c[0] for c in fake.calls] == ["DescribeLaunchTemplateVersions"]  # find only


def test_check_mode_force_replace_reports_old_version(monkeypatch):
    fake = FakeCvmClient([_version()])
    _make_module(monkeypatch, fake)
    module_args(
        _ansible_check_mode=True,
        **{
            k: v
            for k, v in _params(
                version=1,
                template_data={"ImageId": "img-2", "InstanceType": "S5.LARGE8", "Placement": {"Zone": "ap-guangzhou-3"}},
                force_replace=True,
            ).items()
            if v is not None
        }
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["launch_template_version"]["LaunchTemplateVersion"] == 1  # pre-change
    assert [c[0] for c in fake.calls] == ["DescribeLaunchTemplateVersions"]


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeCvmClient([_version()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", version=None, description="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["launch_template_version"] is None
    assert not any(c[0] == "DeleteLaunchTemplateVersions" for c in fake.calls)


def test_absent_deletes_version(monkeypatch):
    fake = FakeCvmClient([_version(), _version(LaunchTemplateVersion=2, LaunchTemplateVersionDescription="other")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", version=1, description=None)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["launch_template_version"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteLaunchTemplateVersions"][0][1]
    assert delete.LaunchTemplateVersions == [1]
    assert [v["LaunchTemplateVersion"] for v in fake.versions] == [2]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCvmClient([_version()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(state="absent", version=1, description=None).items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["launch_template_version"]["LaunchTemplateVersion"] == 1  # pre-change reported
    assert not any(c[0] == "DeleteLaunchTemplateVersions" for c in fake.calls)
    assert len(fake.versions) == 1


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (_CvmModels(), SimpleNamespace(CvmClient=object)),
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
