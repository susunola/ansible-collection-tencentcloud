"""Unit tests for the tse_config_file_release write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TSE config
client whose write operations mutate the release store, so the module's
``wait()`` reconverges on the first poll.

Scenario matrix:

* rollback/publication field conflict before any SDK call
* absent on a missing release (idempotent no-op), the unsuccessful-result
  guard, check-mode dry run and the real delete path
* rollback (missing release, already-at-version no-op, real rollback)
* publish (missing content/format validation, happy path, check mode,
  no-drift idempotency, drift re-publish)
* the blanket ``sdk_error_payload`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_config_file_release as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

CONTENT = "server:\n  port: 8080\n"

RELEASE = {
    "Id": "rel-1",
    "Name": "production",
    "Namespace": "prod",
    "Group": "application",
    "FileName": "orders.yaml",
    "Version": "12",
    "Content": CONTENT,
    "Format": "YAML",
    "Comment": "orders config",
}


def _release(**overrides):
    item = copy.deepcopy(RELEASE)
    item.update(overrides)
    return item


class FakeTseConfigClient(object):
    """In-memory TSE configuration-release client."""

    def __init__(self, releases=None):
        self.releases = [copy.deepcopy(t) for t in (releases or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _current(self):
        return self.releases[0] if self.releases else None

    def DescribeConfigFileRelease(self, request):
        self._record("DescribeConfigFileRelease", request)
        item = self._current()
        return SimpleNamespace(ConfigFileRelease=FakeResource(item) if item else None)

    def PublishConfigFiles(self, request):
        self._record("PublishConfigFiles", request)
        payload = request.ConfigFileReleases.__dict__
        version = str(int((self._current() or {}).get("Version") or 0) + 1)
        item = {
            "Id": "rel-new",
            "Version": version,
            "Name": payload.get("Name"),
            "Namespace": payload.get("Namespace"),
            "Group": payload.get("Group"),
            "FileName": payload.get("FileName"),
        }
        for key in (
            "Content", "Format", "Comment", "ReleaseDescription",
            "ConfigFileSupportedClient", "ConfigFilePersistent",
            "BetaLabels", "ReleaseType",
        ):
            if payload.get(key) is not None:
                item[key] = payload[key]
        self.releases = [item]
        return SimpleNamespace(Result=True, ConfigFileReleaseId=item["Id"], RequestId="req-fake")

    def RollbackConfigFileReleases(self, request):
        self._record("RollbackConfigFileReleases", request)
        item = self._current()
        if item is not None:
            entry = request.RollbackConfigFileReleases[0]
            item["Version"] = entry.__dict__.get("Version")
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def DeleteConfigFileReleases(self, request):
        self._record("DeleteConfigFileReleases", request)
        self.releases = []
        return SimpleNamespace(Result=True, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _release_args(**overrides):
    params = {
        "instance_id": "ins-1",
        "namespace": "prod",
        "group": "application",
        "name": "orders.yaml",
        "release_name": "production",
        "content": CONTENT,
        "format": "YAML",
    }
    params.update(overrides)
    return module_args(**params)


# ---------------------------------------------------------------------------
# validation / absent flows
# ---------------------------------------------------------------------------


def test_rollback_conflicts_with_publication_fields(monkeypatch):
    fake = FakeTseConfigClient(releases=[])
    _make_module(monkeypatch, fake)
    _release_args(content=None, format=None, rollback_version="12", comment="nope")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "mutually exclusive" in payload["msg"]
    assert payload["conflicts"] == ["comment"]


def test_absent_missing_release_is_idempotent(monkeypatch):
    fake = FakeTseConfigClient(releases=[])
    _make_module(monkeypatch, fake)
    _release_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["release"] is None


def test_absent_deletes_release(monkeypatch):
    fake = FakeTseConfigClient(releases=[_release()])
    _make_module(monkeypatch, fake)
    _release_args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.releases == []
    assert "DeleteConfigFileReleases" in [c for c, unused in fake.calls]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseConfigClient(releases=[_release()])
    _make_module(monkeypatch, fake)
    _release_args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.releases) == 1
    assert "DeleteConfigFileReleases" not in [c for c, unused in fake.calls]


def test_delete_rejected_when_result_false(monkeypatch):
    class RejectingClient(FakeTseConfigClient):
        def DeleteConfigFileReleases(self, request):
            self._record("DeleteConfigFileReleases", request)
            return SimpleNamespace(Result=False, RequestId="req-fake")

    fake = RejectingClient(releases=[_release()])
    _make_module(monkeypatch, fake)
    _release_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "returned an unsuccessful result" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# rollback flows
# ---------------------------------------------------------------------------


def test_rollback_requires_existing_release(monkeypatch):
    fake = FakeTseConfigClient(releases=[])
    _make_module(monkeypatch, fake)
    _release_args(content=None, format=None, rollback_version="12")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "required for rollback" in exc.value.args[0]["msg"]


def test_rollback_same_version_is_idempotent(monkeypatch):
    fake = FakeTseConfigClient(releases=[_release()])
    _make_module(monkeypatch, fake)
    _release_args(content=None, format=None, rollback_version="12")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["release"]["Version"] == "12"
    assert "RollbackConfigFileReleases" not in [c for c, unused in fake.calls]


def test_rollback_to_historical_version(monkeypatch):
    fake = FakeTseConfigClient(releases=[_release()])
    _make_module(monkeypatch, fake)
    _release_args(content=None, format=None, rollback_version="9")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["release"]["Version"] == "9"
    assert "RollbackConfigFileReleases" in [c for c, unused in fake.calls]


def test_rollback_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseConfigClient(releases=[_release()])
    _make_module(monkeypatch, fake)
    _release_args(_ansible_check_mode=True, content=None, format=None, rollback_version="9")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["release"]["Version"] == "9"
    assert fake.releases[0]["Version"] == "12"
    assert "RollbackConfigFileReleases" not in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# publish flows
# ---------------------------------------------------------------------------


def test_publish_requires_content_and_format(monkeypatch):
    fake = FakeTseConfigClient(releases=[])
    _make_module(monkeypatch, fake)
    _release_args(content=None, format=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "content and format are required" in payload["msg"]
    assert payload["missing"] == ["content", "format"]


def test_publish_new_release(monkeypatch):
    fake = FakeTseConfigClient(releases=[])
    _make_module(monkeypatch, fake)
    _release_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["release"]["Content"] == CONTENT
    assert result["release"]["Format"] == "YAML"
    assert result["release"]["FileName"] == "orders.yaml"
    ops = [c for c, unused in fake.calls]
    assert "PublishConfigFiles" in ops
    assert fake.releases[0]["Version"] == "1"


def test_publish_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseConfigClient(releases=[])
    _make_module(monkeypatch, fake)
    _release_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["release"]["Format"] == "YAML"
    assert fake.releases == []
    assert "PublishConfigFiles" not in [c for c, unused in fake.calls]


def test_publish_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseConfigClient(releases=[_release()])
    _make_module(monkeypatch, fake)
    _release_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["release"]["Version"] == "12"
    assert "PublishConfigFiles" not in [c for c, unused in fake.calls]


def test_publish_drift_updates_release(monkeypatch):
    fake = FakeTseConfigClient(releases=[_release(Content="old content")])
    _make_module(monkeypatch, fake)
    _release_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["release"]["Content"] == CONTENT
    assert "PublishConfigFiles" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeConfigFileRelease(self, request):
            raise Boom("engine down")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _release_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "engine down" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from test_tse_config_file_release.py)
# ---------------------------------------------------------------------------


class LegacyValue(object):
    def from_json_string(self, raw):
        self.raw = raw


class LegacyRequest(object):
    pass


class LegacyModels(object):
    ConfigFileRelease = LegacyValue
    ConfigFileReleaseDeletion = LegacyValue
    PublishConfigFilesRequest = LegacyRequest
    RollbackConfigFileReleasesRequest = LegacyRequest
    DeleteConfigFileReleasesRequest = LegacyRequest


def test_config_release_requests_map_publish_rollback_and_delete():
    p = {
        "instance_id": "ins1",
        "namespace": "production",
        "group": "application",
        "name": "orders.yaml",
        "release_name": "stable",
        "strict_enable": True,
        "content": "port: 8080",
        "format": "YAML",
        "comment": None,
        "release_description": "deploy",
        "supported_client": None,
        "persistent": None,
        "beta_labels": None,
        "release_type": None,
        "rollback_version": "2",
    }
    target = mod.desired(p)
    publish = mod.publish_request(LegacyModels, p, target)
    assert publish.StrictEnable is True and json.loads(publish.ConfigFileReleases.raw)["Content"] == "port: 8080"
    current = dict(target, Id="release-1", Version="3")
    rollback = mod.rollback_request(LegacyModels, p, current)
    assert json.loads(rollback.RollbackConfigFileReleases[0].raw)["Version"] == "2"
    delete = mod.delete_request(LegacyModels, p, current)
    assert json.loads(delete.ConfigFileReleases[0].raw)["ReleaseVersion"] == "3"
