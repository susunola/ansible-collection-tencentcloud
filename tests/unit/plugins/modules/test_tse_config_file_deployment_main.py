"""Unit tests for the tse_config_file_deployment write module (run_module flows).

Drives ``run_module()`` against an in-memory fake TSE client whose
``CreateOrUpdateConfigFileAndRelease``/delete operations mutate the file and
release stores so the post-write release/file refetch converges on the first
poll.

Scenario matrix:

* content/format validation guard for ``state=present``
* absent on a missing deployment (idempotent no-op)
* absent with a matching release/file (check-mode dry run, real teardown)
* deployment when missing (happy path, check mode)
* no-op when release and config file already match
* drift updates (content change)
* an unsuccessful ``Result`` and the blanket SDK failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_config_file_deployment as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

RELEASE = {
    "Id": "rel-1",
    "Name": "production",
    "Version": "v3",
    "Namespace": "prod-ns",
    "Group": "application",
    "FileName": "orders.yaml",
    "Content": "server:\n  port: 8080\n",
    "Format": "YAML",
    "Comment": "release comment",
}

CONFIG_FILE = {
    "Id": "cfg-1",
    "Name": "orders.yaml",
    "Namespace": "prod-ns",
    "Group": "application",
    "Content": "server:\n  port: 8080\n",
    "Format": "YAML",
    "Comment": "release comment",
}


def _release(**overrides):
    item = copy.deepcopy(RELEASE)
    item.update(overrides)
    return item


def _config_file(**overrides):
    item = copy.deepcopy(CONFIG_FILE)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {
        "instance_id": "ins-abc",
        "namespace": "prod-ns",
        "group": "application",
        "name": "orders.yaml",
        "release_name": "production",
    }
    params.update(overrides)
    return module_args(**params)


class NotFound(Exception):
    """Stand-in for an SDK ResourceNotFound so describe helpers treat it as absent."""

    def get_code(self):
        return "ResourceNotFound"


class FakeTseClient(object):
    """In-memory TSE client mutating release and config-file stores."""

    def __init__(self, release=None, config_file=None, result=True):
        self.release = copy.deepcopy(release) if release else None
        self.config_file = copy.deepcopy(config_file) if config_file else None
        self.result = result
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeConfigFileRelease(self, request):
        self._record("DescribeConfigFileRelease", request)
        if self.release is None:
            raise NotFound()
        return SimpleNamespace(ConfigFileRelease=FakeResource(self.release))

    def DescribeConfigFile(self, request):
        self._record("DescribeConfigFile", request)
        if self.config_file is None:
            raise NotFound()
        return SimpleNamespace(ConfigFile=FakeResource(self.config_file))

    def CreateOrUpdateConfigFileAndRelease(self, request):
        self._record("CreateOrUpdateConfigFileAndRelease", request)
        self._next += 1
        info = getattr(request, "ConfigFilePublishInfo", None)
        data = dict(getattr(info, "_data", None) or getattr(info, "__dict__", {}) or {})
        self.release = {
            "Id": "rel-new-%03d" % self._next,
            "Name": data.get("ReleaseName", "production"),
            "Version": "v%d" % self._next,
            "Namespace": data.get("Namespace"),
            "Group": data.get("Group"),
            "FileName": data.get("FileName"),
            "Content": data.get("Content"),
            "Format": data.get("Format"),
            "Comment": data.get("Comment"),
        }
        self.config_file = {
            "Id": "cfg-new-%03d" % self._next,
            "Name": data.get("FileName"),
            "Namespace": data.get("Namespace"),
            "Group": data.get("Group"),
            "Content": data.get("Content"),
            "Format": data.get("Format"),
            "Comment": data.get("Comment"),
        }
        return SimpleNamespace(
            Result=self.result,
            ConfigFileId=self.config_file["Id"],
            ConfigFileReleaseId=self.release["Id"],
            RequestId="req-fake",
        )

    def DeleteConfigFileReleases(self, request):
        self._record("DeleteConfigFileReleases", request)
        self.release = None
        return SimpleNamespace(Result=self.result, RequestId="req-fake")

    def DeleteConfigFiles(self, request):
        self._record("DeleteConfigFiles", request)
        self.config_file = None
        return SimpleNamespace(Result=self.result, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# validation guards
# ---------------------------------------------------------------------------


def test_present_requires_content_and_format(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "content and format are required for a TSE configuration deployment"


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_deployment_is_idempotent(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["deployment"] is None
    ops = [c for c, unused in fake.calls]
    assert "DescribeConfigFileRelease" in ops
    assert "DescribeConfigFile" in ops


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient(release=_release(), config_file=_config_file())
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deployment"] is None
    assert fake.release is not None and fake.config_file is not None
    assert "DeleteConfigFileReleases" not in [c for c, unused in fake.calls]


def test_absent_deletes_release_then_file(monkeypatch):
    fake = FakeTseClient(release=_release(), config_file=_config_file())
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.release is None and fake.config_file is None
    ops = [c for c, unused in fake.calls]
    assert ops.index("DeleteConfigFileReleases") < ops.index("DeleteConfigFiles")


def test_absent_release_only_still_tears_down(monkeypatch):
    fake = FakeTseClient(release=_release())
    _make_module(monkeypatch, fake)
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    ops = [c for c, unused in fake.calls]
    assert "DeleteConfigFileReleases" in ops
    assert "DeleteConfigFiles" not in ops


# ---------------------------------------------------------------------------
# deployment flows
# ---------------------------------------------------------------------------


def test_deploy_when_missing(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        content="server:\n  port: 8080\n",
        format="YAML",
        comment="release comment",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deployment"]["release"]["Name"] == "production"
    assert result["deployment"]["config_file"]["Content"] == "server:\n  port: 8080\n"
    assert result["deployment"]["config_file_id"].startswith("cfg-new-")
    ops = [c for c, unused in fake.calls]
    assert "CreateOrUpdateConfigFileAndRelease" in ops


def test_deploy_check_mode_is_dry_run(monkeypatch):
    fake = FakeTseClient()
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        content="server:\n  port: 8080\n",
        format="YAML",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deployment"]["release"]["Name"] == "production"
    assert fake.release is None and fake.config_file is None
    assert "CreateOrUpdateConfigFileAndRelease" not in [c for c, unused in fake.calls]


def test_existing_deployment_no_drift_is_idempotent(monkeypatch):
    fake = FakeTseClient(release=_release(), config_file=_config_file())
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        content="server:\n  port: 8080\n",
        format="YAML",
        comment="release comment",
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["deployment"]["release"]["Name"] == "production"
    assert "CreateOrUpdateConfigFileAndRelease" not in [c for c, unused in fake.calls]


def test_content_drift_triggers_redeploy(monkeypatch):
    fake = FakeTseClient(release=_release(), config_file=_config_file())
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        content="server:\n  port: 9090\n",
        format="YAML",
        comment="release comment",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["deployment"]["config_file"]["Content"] == "server:\n  port: 9090\n"
    ops = [c for c, unused in fake.calls]
    assert "CreateOrUpdateConfigFileAndRelease" in ops


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_unsuccessful_result_fails(monkeypatch):
    fake = FakeTseClient(result=False)
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        content="server:\n  port: 8080\n",
        format="YAML",
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "unsuccessful result" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeConfigFileRelease(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", content="server:\n  port: 8080\n", format="YAML")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
