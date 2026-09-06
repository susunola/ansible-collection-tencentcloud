"""Unit tests for the tke_addon write module (helpers + run_module paths).

Covers values loading (JSON/YAML/auto), base64 values canonicalization,
install/update request building, version downgrade guard and the
run_module present/absent flows with an in-memory fake TKE client.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import base64
import json
import time
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tke_addon
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    module_args,
    run,
)

ADDON = {
    "AddonName": "cbs",
    "AddonVersion": "1.4.0",
    "Phase": "Succeeded",
    "RawValues": base64.b64encode(
        json.dumps({"replicaCount": 2}, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii"),
}


class JsonResource(object):
    """SDK-model stand-in exposing attributes plus ``to_json_string()``."""

    def __init__(self, data):
        self._data = dict(data)

    def __getattr__(self, name):
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name)

    def to_json_string(self):
        return json.dumps(self._data)


class FakeTkeClient(object):
    def __init__(self, addons=None):
        self.addons = [dict(a) for a in (addons or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))

    def DescribeAddon(self, request):
        self._record("DescribeAddon", request)
        matched = [a for a in self.addons if a["AddonName"] == request.AddonName]
        return SimpleNamespace(Addons=[JsonResource(a) for a in matched])

    def InstallAddon(self, request):
        self._record("InstallAddon", request)
        if getattr(request, "DryRun", False):
            return SimpleNamespace()
        self.addons.append({
            "AddonName": request.AddonName,
            "AddonVersion": request.AddonVersion,
            "RawValues": request.RawValues,
            "Phase": "Succeeded",
        })
        return SimpleNamespace()

    def UpdateAddon(self, request):
        self._record("UpdateAddon", request)
        if getattr(request, "DryRun", False):
            return SimpleNamespace()
        addon = next(a for a in self.addons if a["AddonName"] == request.AddonName)
        addon["AddonVersion"] = request.AddonVersion
        if getattr(request, "RawValues", None) is not None:
            addon["RawValues"] = request.RawValues
        addon["Phase"] = "Succeeded"
        return SimpleNamespace()

    def DeleteAddon(self, request):
        self._record("DeleteAddon", request)
        self.addons = [a for a in self.addons if a["AddonName"] != request.AddonName]
        return SimpleNamespace()


class FakeModule(object):
    def __init__(self, **params):
        self.params = dict(params)

    def sdk_call(self, operation, request):
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


@pytest.fixture
def client(monkeypatch):
    fake = FakeTkeClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        tke_addon, "_load_tke",
        lambda: (FakeModels(), SimpleNamespace(TkeClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    return fake


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_values_json_normalizes_mapping_and_string():
    assert tke_addon._values_json({"b": 1, "a": [1, 2]}) == '{"a":[1,2],"b":1}'
    assert tke_addon._values_json('{"a": 1}') == '{"a":1}'
    assert tke_addon._values_json("not-json") == "not-json"
    assert tke_addon._values_json(None) == "{}"


def test_safe_load_yaml_parses_and_rejects_bad_yaml():
    assert tke_addon._safe_load_yaml("a: 1") == {"a": 1}
    with pytest.raises(ValueError):
        tke_addon._safe_load_yaml("a: [unclosed")


def test_load_values_json_format():
    module = FakeModule(values='{"a": 1}', values_format="json")
    assert tke_addon.load_values(module.params) == {"a": 1}


def test_load_values_yaml_format():
    module = FakeModule(values="a: 1", values_format="yaml")
    assert tke_addon.load_values(module.params) == {"a": 1}


def test_load_values_auto_tries_json_then_yaml():
    assert tke_addon.load_values(FakeModule(values='{"a": 1}').params) == {"a": 1}
    assert tke_addon.load_values(FakeModule(values="a: 1").params) == {"a": 1}


def test_load_values_from_file(tmp_path):
    path = tmp_path / "values.yaml"
    path.write_text("replicaCount: 3", encoding="utf-8")
    params = {"values_file": str(path), "values_format": "yaml", "values": None}
    assert tke_addon.load_values(params) == {"replicaCount": 3}


def test_load_values_non_string_passthrough():
    assert tke_addon.load_values({"values": {"a": 1}}) == {"a": 1}


def test_raw_is_base64_canonical_json():
    raw = tke_addon._raw({"replicaCount": 2})
    assert raw == base64.b64encode(b'{"replicaCount":2}').decode("ascii")


def test_canonical_raw_compares_equivalent_values():
    assert tke_addon._canonical_raw(tke_addon._raw({"replicaCount": 2})) == '{"replicaCount":2}'
    assert tke_addon._canonical_raw(None) == "{}"
    assert tke_addon._canonical_raw("not-base64") == "not-base64"


def test_safe_redacts_raw_values():
    addon = dict(ADDON)
    safe = tke_addon._safe(addon)
    assert safe["RawValues"] == "<redacted>"
    assert tke_addon._safe(None) is None


def test_describe_addon_matches_by_name(client):
    client.addons = [dict(ADDON)]
    module = FakeModule(waiter_timeout=30, waiter_delay=0)
    result = tke_addon.describe_addon(module, client, FakeModels(), "cls-1", "cbs")
    assert result["AddonName"] == "cbs"
    assert result["RawValues"]  # raw (not redacted) on the way out


def test_build_install_request_embeds_values():
    params = {"cluster_id": "cls-1", "name": "cbs", "version": "1.4.0",
              "values": {"replicaCount": 2}}
    request = tke_addon.build_install_request(FakeModels(), params)
    assert request.ClusterId == "cls-1"
    assert request.AddonVersion == "1.4.0"
    assert request.RawValues == tke_addon._raw({"replicaCount": 2})


def test_build_update_request_keeps_current_version_when_unset():
    request = tke_addon.build_update_request(
        FakeModels(),
        {"cluster_id": "cls-1", "name": "cbs", "version": None,
         "values": None, "update_strategy": "merge"},
        {"AddonVersion": "1.4.0"},
    )
    assert request.AddonVersion == "1.4.0"
    assert not hasattr(request, "RawValues") or request.RawValues is None


def test_version_tuple_parses_and_ignores_garbage():
    assert tke_addon._version_tuple("v1.4.0") == (1, 4, 0)
    assert tke_addon._version_tuple("garbage") is None


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_install_reports_changed(client):
    module_args(state="present", cluster_id="cls-1", name="cbs", version="1.4.0",
                values={"replicaCount": 2})
    result = run(tke_addon.run_module)
    assert result["changed"] is True
    assert result["addon"]["AddonName"] == "cbs"
    assert any(name == "InstallAddon" for name, request in client.calls)


def test_install_requires_version(client):
    module_args(state="present", cluster_id="cls-1", name="cbs")
    with pytest.raises(AnsibleFailJson):
        run(tke_addon.run_module)


def test_second_run_is_idempotent(client):
    client.addons = [dict(ADDON)]
    module_args(state="present", cluster_id="cls-1", name="cbs", version="1.4.0",
                values={"replicaCount": 2})
    result = run(tke_addon.run_module)
    assert result["changed"] is False
    assert not any(name in ("InstallAddon", "UpdateAddon") for name, request in client.calls)


def test_values_drift_triggers_update(client):
    client.addons = [dict(ADDON)]
    module_args(state="present", cluster_id="cls-1", name="cbs", version="1.4.0",
                values={"replicaCount": 3})
    result = run(tke_addon.run_module)
    assert result["changed"] is True
    assert any(name == "UpdateAddon" for name, request in client.calls)


def test_version_downgrade_blocked_without_flag(client):
    client.addons = [dict(ADDON)]
    module_args(state="present", cluster_id="cls-1", name="cbs", version="1.3.0")
    with pytest.raises(AnsibleFailJson):
        run(tke_addon.run_module)


def test_version_downgrade_allowed_with_flag(client):
    client.addons = [dict(ADDON)]
    module_args(state="present", cluster_id="cls-1", name="cbs", version="1.3.0",
                allow_downgrade=True)
    result = run(tke_addon.run_module)
    assert result["changed"] is True
    assert any(name == "UpdateAddon" for name, request in client.calls)


def test_check_mode_install_makes_no_writes(client):
    module_args(state="present", cluster_id="cls-1", name="cbs", version="1.4.0",
                values={"replicaCount": 2}, _ansible_check_mode=True)
    result = run(tke_addon.run_module)
    assert result["changed"] is True
    assert not any(n in ("InstallAddon", "UpdateAddon", "DeleteAddon") for n, request in client.calls)


def test_absent_deletes_existing_addon(client):
    client.addons = [dict(ADDON)]
    module_args(state="absent", cluster_id="cls-1", name="cbs")
    result = run(tke_addon.run_module)
    assert result["changed"] is True
    assert any(name == "DeleteAddon" for name, request in client.calls)
    assert client.addons == []


def test_absent_on_missing_addon_is_unchanged(client):
    module_args(state="absent", cluster_id="cls-1", name="cbs")
    result = run(tke_addon.run_module)
    assert result["changed"] is False


def test_api_dry_run_install_validates_then_installs(client):
    module_args(state="present", cluster_id="cls-1", name="cbs", version="1.4.0",
                api_dry_run=True)
    result = run(tke_addon.run_module)
    assert result["changed"] is True
    dry = [r for n, r in client.calls if n == "InstallAddon"]
    assert len(dry) == 2
    assert getattr(dry[0], "DryRun", False) is True
    assert not hasattr(dry[1], "DryRun")
