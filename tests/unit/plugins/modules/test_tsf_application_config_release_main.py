"""Unit tests for the tsf_application_config_release write module.

Drives ``run_module()`` against an in-memory fake TSF client whose config
release describe / release / revoke calls mutate a (config_id, group_id)-
keyed release list so post-write describes converge immediately.

Release semantics: a published release is immutable. Re-running ``present``
for the same (config_id, group_id) is a no-op; drift on release metadata is
rejected instead of silently re-releasing.

Scenario matrix:

* present: publish, idempotent re-release, metadata drift rejection,
  check-mode dry run
* absent: no-op, revoke, check mode, rejected revoke
* lookup ambiguity guard and the blanket SDK failure path
* legacy pure-helper assertions folded from the shallow test file
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tsf_application_config_release as mod
from ansible_collections.susunola.tencentcloud.plugins.modules.tsf_application_config_release import desired
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CONFIG_ID = "config-a"
GROUP_ID = "group-a"


def _release(release_id, **overrides):
    value = {"ConfigReleaseId": release_id, "ConfigId": CONFIG_ID,
             "GroupId": GROUP_ID, "ReleaseDesc": "production"}
    value.update(overrides)
    return value


def _release_args(**overrides):
    params = {"config_id": CONFIG_ID, "group_id": GROUP_ID,
              "release_description": "production", "state": "present"}
    params.update(overrides)
    return module_args(**params)


class FakeTsfClient(object):
    """In-memory TSF client backed by a mutable (config_id, group_id) release list."""

    def __init__(self, releases=None):
        self.releases = [dict(r) for r in releases or []]
        self.calls = []
        self._next_id = 1

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _new_id(self):
        value = "release-%d" % self._next_id
        self._next_id += 1
        return value

    def DescribeConfigReleases(self, request):
        self._record("DescribeConfigReleases", request)
        matches = [r for r in self.releases
                   if r["ConfigId"] == getattr(request, "ConfigId", None)
                   and r["GroupId"] == getattr(request, "GroupId", None)]
        payload = [FakeResource(dict(r)) for r in matches]
        return SimpleNamespace(Result=SimpleNamespace(Content=payload), RequestId="req-fake")

    def ReleaseConfig(self, request):
        self._record("ReleaseConfig", request)
        release = {"ConfigReleaseId": self._new_id(),
                   "ConfigId": getattr(request, "ConfigId", None),
                   "GroupId": getattr(request, "GroupId", None),
                   "ReleaseDesc": getattr(request, "ReleaseDesc", None)}
        self.releases.append(release)
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def RevocationConfig(self, request):
        self._record("RevocationConfig", request)
        self.releases = [r for r in self.releases
                         if r["ConfigReleaseId"] != getattr(request, "ConfigReleaseId", None)]
        return SimpleNamespace(Result=True, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TsfClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_present_publishes_release(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _release_args(release_description="Production settings")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["release"]["ConfigReleaseId"] == "release-1"
    assert result["release"]["ConfigId"] == CONFIG_ID
    assert result["release"]["GroupId"] == GROUP_ID
    assert result["release"]["ReleaseDesc"] == "Production settings"
    assert "ReleaseConfig" in _names(fake)
    assert len(fake.releases) == 1


def test_present_same_release_is_idempotent(monkeypatch):
    fake = FakeTsfClient(releases=[_release("release-7")])
    _make_module(monkeypatch, fake)
    _release_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["release"]["ConfigReleaseId"] == "release-7"
    assert "ReleaseConfig" not in _names(fake)


def test_present_release_drift_is_rejected_as_immutable(monkeypatch):
    fake = FakeTsfClient(releases=[_release("release-7", ReleaseDesc="old")])
    _make_module(monkeypatch, fake)
    _release_args(release_description="new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed on an existing" in payload["msg"]
    assert "ReleaseDesc" in payload["immutable_changes"]
    assert "ReleaseConfig" not in _names(fake)


def test_present_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _release_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["release"]["ConfigId"] == CONFIG_ID
    assert "ConfigReleaseId" not in result["release"]
    assert "ReleaseConfig" not in _names(fake)
    assert fake.releases == []


# ---------------------------------------------------------------------------
# lookup semantics
# ---------------------------------------------------------------------------


def test_multiple_matching_releases_fail(monkeypatch):
    fake = FakeTsfClient(releases=[_release("release-1", ReleaseDesc="a"), _release("release-2", ReleaseDesc="b")])
    _make_module(monkeypatch, fake)
    _release_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSF configuration releases matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_unpublished_is_idempotent(monkeypatch):
    fake = FakeTsfClient()
    _make_module(monkeypatch, fake)
    _release_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["release"] is None
    assert "RevocationConfig" not in _names(fake)


def test_absent_revokes_release(monkeypatch):
    fake = FakeTsfClient(releases=[_release("release-7")])
    _make_module(monkeypatch, fake)
    _release_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["release"] is None
    assert "RevocationConfig" in _names(fake)
    assert fake.releases == []


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTsfClient(releases=[_release("release-7")])
    _make_module(monkeypatch, fake)
    _release_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["release"] is None
    assert "RevocationConfig" not in _names(fake)
    assert len(fake.releases) == 1


def test_rejected_revocation_fails(monkeypatch):
    class RejectingClient(FakeTsfClient):
        def RevocationConfig(self, request):
            self._record("RevocationConfig", request)
            return SimpleNamespace(Result=False, RequestId="req-err")

    fake = RejectingClient(releases=[_release("release-7")])
    _make_module(monkeypatch, fake)
    _release_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "rejected the TSF configuration release revocation" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeConfigReleases(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _release_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy pure-helper assertions (folded from the shallow test file)
# ---------------------------------------------------------------------------


def test_legacy_desired_maps_identity_and_description():
    params = {"config_id": "config-a", "group_id": "group-a", "release_description": "production"}
    assert desired(params) == {"ConfigId": "config-a", "GroupId": "group-a", "ReleaseDesc": "production"}
