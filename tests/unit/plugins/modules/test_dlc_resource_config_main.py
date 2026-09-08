"""Unit tests for the dlc_resource_config write module (run_module flows)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_resource_config as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

HEAD = {
    "Name": "head",
    "PodCpu": 4,
    "PodMem": 16,
    "PodNum": 1,
    "ResourceType": "CPU",
    "Spec": 4,
    "BillingItem": "sv_dlc_standard_cu_standard_cu",
}
WORKERS = [
    {
        "Name": "workers",
        "PodCpu": 4,
        "PodMem": 16,
        "MinPodNum": 1,
        "MaxPodNum": 8,
        "EnableAutoScaling": True,
        "ResourceType": "CPU",
        "Spec": 4,
        "BillingItem": "sv_dlc_standard_cu_standard_cu",
    }
]
CONFIG = {
    "Id": "rc-8b0a1c2d",
    "Name": "analytics-ray-small",
    "Type": "Ray",
    "Description": "Shared notebook and Ray template",
    "Head": HEAD,
    "Worker": WORKERS,
}


def _config(**overrides):
    item = copy.deepcopy(CONFIG)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {"name": "analytics-ray-small"}
    params.update(overrides)
    return module_args(**params)


class FakeDlcClient(object):
    """In-memory DLC client mutating a small resource-template store."""

    def __init__(self, configs=None, labs=None, ray_clusters=None):
        self.configs = [copy.deepcopy(t) for t in (configs or [])]
        self.labs = [copy.deepcopy(t) for t in (labs or [])]
        self.ray_clusters = [copy.deepcopy(t) for t in (ray_clusters or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find(self, name):
        for item in self.configs:
            if item.get("Name") == name:
                return item
        return None

    def ListResourceConfigs(self, request):
        self._record("ListResourceConfigs", request)
        return SimpleNamespace(Items=[FakeResource(dict(t)) for t in self.configs], TotalPages=1)

    def ListLabs(self, request):
        self._record("ListLabs", request)
        return SimpleNamespace(Items=[FakeResource(dict(t)) for t in self.labs], TotalPages=1)

    def ListRayClusters(self, request):
        self._record("ListRayClusters", request)
        return SimpleNamespace(Items=[FakeResource(dict(t)) for t in self.ray_clusters], TotalPages=1)

    def CreateResourceConfig(self, request):
        self._record("CreateResourceConfig", request)
        self._next += 1
        item = {"Id": "rc-new-%03d" % self._next, "Name": request.Name}
        for attr in ("Description", "Type", "Head", "Worker"):
            if hasattr(request, attr):
                item[attr] = getattr(request, attr)
        self.configs.append(item)
        return SimpleNamespace(Id=item["Id"], RequestId="req-fake")

    def UpdateResourceConfig(self, request):
        self._record("UpdateResourceConfig", request)
        item = None
        for candidate in self.configs:
            if candidate.get("Id") == getattr(request, "Id", None):
                item = candidate
                break
        if item is None:
            item = self._find(getattr(request, "Name", None))
        if item is not None:
            for attr in ("Description", "Type", "Head", "Worker"):
                if hasattr(request, attr):
                    item[attr] = getattr(request, attr)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteResourceConfig(self, request):
        self._record("DeleteResourceConfig", request)
        self.configs = [t for t in self.configs if t.get("Id") != request.Id]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _head_params():
    return {
        "name": "head",
        "pod_cpu": 4,
        "pod_mem": 16,
        "pod_num": 1,
        "resource_type": "CPU",
        "spec": 4,
        "billing_item": "sv_dlc_standard_cu_standard_cu",
    }


def _worker_params():
    return [
        {
            "name": "workers",
            "pod_cpu": 4,
            "pod_mem": 16,
            "min_pod_num": 1,
            "max_pod_num": 8,
            "enable_auto_scaling": True,
            "resource_type": "CPU",
            "spec": 4,
            "billing_item": "sv_dlc_standard_cu_standard_cu",
        }
    ]


# ---------------------------------------------------------------------------
# pre-SDK validation
# ---------------------------------------------------------------------------


def test_worker_without_unique_name_fails(monkeypatch):
    fake = FakeDlcClient(configs=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", workers=[{"pod_cpu": 4}, {"pod_cpu": 4}])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "each worker requires a unique name" in exc.value.args[0]["msg"]


def test_duplicate_worker_names_fail(monkeypatch):
    fake = FakeDlcClient(configs=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", workers=[{"name": "a"}, {"name": "a"}])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "each worker requires a unique name" in exc.value.args[0]["msg"]


def test_worker_min_above_max_fails(monkeypatch):
    fake = FakeDlcClient(configs=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", workers=[{"name": "a", "min_pod_num": 8, "max_pod_num": 2}])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "min_pod_num must not exceed max_pod_num" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeDlcClient(configs=[])
    _make_module(monkeypatch, fake)
    _base(state="present", name="ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["template_type", "head", "workers"]


def test_create_config(monkeypatch):
    fake = FakeDlcClient(configs=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        template_type="Ray",
        description="Shared notebook and Ray template",
        head=_head_params(),
        workers=_worker_params(),
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource_config"]["Name"] == "analytics-ray-small"
    assert result["resource_config"]["Head"]["PodCpu"] == 4
    assert result["resource_config"]["Worker"][0]["Name"] == "workers"
    assert result["resource_config_id"].startswith("rc-new-")
    assert len(fake.configs) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "ListResourceConfigs"
    assert "CreateResourceConfig" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(configs=[])
    _make_module(monkeypatch, fake)
    _base(
        _ansible_check_mode=True,
        state="present",
        template_type="Ray",
        head=_head_params(),
        workers=_worker_params(),
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource_config"]["Name"] == "analytics-ray-small"
    assert result["resource_config_id"] is None
    assert fake.configs == []
    assert "CreateResourceConfig" not in [c for c, unused in fake.calls]


def test_create_config_without_wait(monkeypatch):
    fake = FakeDlcClient(configs=[])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        template_type="ray",
        head=_head_params(),
        workers=_worker_params(),
        wait=False,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource_config_id"].startswith("rc-new-")


# ---------------------------------------------------------------------------
# existing-config flows
# ---------------------------------------------------------------------------


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcClient(configs=[_config()])
    _make_module(monkeypatch, fake)
    _base(
        state="present",
        template_type="Ray",
        description="Shared notebook and Ray template",
        head=_head_params(),
        workers=_worker_params(),
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["resource_config"]["Id"] == "rc-8b0a1c2d"
    assert result["resource_config_id"] == "rc-8b0a1c2d"
    ops = [c for c, unused in fake.calls]
    assert ops == ["ListResourceConfigs"]


def test_update_description(monkeypatch):
    fake = FakeDlcClient(configs=[_config()])
    _make_module(monkeypatch, fake)
    _base(state="present", description="renamed template", wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource_config"]["Description"] == "renamed template"
    ops = [c for c, unused in fake.calls]
    assert "UpdateResourceConfig" in ops


def test_head_scale_up_applies(monkeypatch):
    fake = FakeDlcClient(configs=[_config()])
    _make_module(monkeypatch, fake)
    head = _head_params()
    head["pod_num"] = 4
    _base(state="present", head=head, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource_config"]["Head"]["PodNum"] == 4


def test_head_scale_down_requires_allow_scale_down(monkeypatch):
    fake = FakeDlcClient(configs=[_config()])
    _make_module(monkeypatch, fake)
    head = _head_params()
    head["pod_cpu"] = 2
    _base(state="present", head=head)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "allow_scale_down=true" in payload["msg"]
    assert "Head" in payload["capacity_drift"]


def test_head_scale_down_authorized_applies(monkeypatch):
    fake = FakeDlcClient(configs=[_config()])
    _make_module(monkeypatch, fake)
    head = _head_params()
    head["pod_cpu"] = 2
    _base(state="present", head=head, allow_scale_down=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource_config"]["Head"]["PodCpu"] == 2


def test_worker_removal_requires_allow_scale_down(monkeypatch):
    fake = FakeDlcClient(configs=[_config()])
    _make_module(monkeypatch, fake)
    _base(state="present", workers=[])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "allow_scale_down=true" in payload["msg"]
    assert "Worker" in payload["capacity_drift"]


def test_worker_removal_authorized_applies(monkeypatch):
    fake = FakeDlcClient(configs=[_config()])
    _make_module(monkeypatch, fake)
    _base(state="present", workers=[], allow_scale_down=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource_config"]["Worker"] == []
    assert "UpdateResourceConfig" in [c for c, unused in fake.calls]


def test_multiple_matches_fail(monkeypatch):
    fake = FakeDlcClient(configs=[_config(), _config(Id="rc-dup")])
    _make_module(monkeypatch, fake)
    _base(state="present")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DLC resource templates matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# deletion flows
# ---------------------------------------------------------------------------


def test_absent_missing_is_idempotent(monkeypatch):
    fake = FakeDlcClient(configs=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", name="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["resource_config"] is None
    assert result["resource_config_id"] is None
    assert [c for c, unused in fake.calls] == ["ListResourceConfigs"]


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeDlcClient(configs=[_config()])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]


def test_absent_blocked_by_references(monkeypatch):
    lab = {"Id": "lab-1", "Name": "notebook-lab", "ResourceConfigId": "rc-8b0a1c2d"}
    fake = FakeDlcClient(configs=[_config()], labs=[lab])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "allow_delete_in_use=true" in payload["msg"]
    assert payload["references"][0]["id"] == "lab-1"


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(configs=[_config()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.configs) == 1
    assert "DeleteResourceConfig" not in [c for c, unused in fake.calls]


def test_absent_deletes_config(monkeypatch):
    fake = FakeDlcClient(configs=[_config()])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["resource_config"] is None
    assert fake.configs == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteResourceConfig" in ops


def test_absent_in_use_authorized_deletes(monkeypatch):
    lab = {"Id": "lab-1", "Name": "notebook-lab", "ResourceConfigId": "rc-8b0a1c2d"}
    ray = {"Id": "rc-9", "Name": "ray-cluster", "ResourceConfigId": "rc-8b0a1c2d"}
    fake = FakeDlcClient(configs=[_config()], labs=[lab], ray_clusters=[ray])
    _make_module(monkeypatch, fake)
    _base(state="absent", allow_delete=True, allow_delete_in_use=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.configs == []
    ops = [c for c, unused in fake.calls]
    assert "DeleteResourceConfig" in ops
    assert "ListLabs" in ops
    assert "ListRayClusters" in ops


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def ListResourceConfigs(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", name="ghost")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
