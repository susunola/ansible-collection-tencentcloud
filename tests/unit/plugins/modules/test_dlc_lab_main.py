"""Unit tests for the dlc_lab write module (run_module flows)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import dlc_lab as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

LAB = {
    "Id": "lab-000001",
    "Name": "analytics-notebook",
    "Type": "WORKSPACE",
    "Status": "RUNNING",
    "ResourcePartitionId": "rp-1",
    "Queue": "default",
    "LabImage": "ccr.ccs.tencentyun.com/dlc/jupyter:latest",
    "ImagePullType": "BuiltIn",
    "LabImagePullType": "BuiltIn",
    "Description": "Analytics lab",
    "Priority": 5,
    "EnableToken": True,
    "Tags": [],
}


def _lab(**overrides):
    item = copy.deepcopy(LAB)
    item.update(overrides)
    return item


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(DlcClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


class FakeDlcClient(object):
    """In-memory DLC client mutating a data-laboratory store."""

    def __init__(self, labs=None):
        self.labs = [copy.deepcopy(t) for t in (labs or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_name(self, name):
        for item in self.labs:
            if item.get("Name") == name and item.get("Type") in (None, "WORKSPACE"):
                return item
        return None

    def ListLabs(self, request):
        self._record("ListLabs", request)
        return SimpleNamespace(Items=[FakeResource(t) for t in self.labs], TotalPages=1)

    def CreateLab(self, request):
        self._record("CreateLab", request)
        self._next += 1
        item = dict(getattr(request, "__dict__", {}) or {})
        item.setdefault("Name", getattr(request, "Name", None))
        item["Id"] = "lab-new-%03d" % self._next
        item["Type"] = "WORKSPACE"
        item["Status"] = "RUNNING"
        self.labs.append(item)
        return SimpleNamespace(Id=item["Id"], RequestId="req-fake")

    def UpdateLab(self, request):
        self._record("UpdateLab", request)
        item = self._by_name(getattr(request, "Name", None))
        if item is None:
            return SimpleNamespace(RequestId="req-fake")
        for attr in (
            "ResourcePartitionId", "Queue", "LabImage", "Image", "Description",
            "ImagePullPolicy", "LabImagePullPolicy", "ImagePullType",
            "LabImagePullType", "ResourceConfigId", "GroupId",
            "EnableToken", "ExampleId", "CodeArchiveUrl", "Tags", "PersistentWorkDir",
        ):
            value = getattr(request, attr, None)
            if value is not None:
                item[attr] = value
        return SimpleNamespace(RequestId="req-fake")

    def ModifyLabPriority(self, request):
        self._record("ModifyLabPriority", request)
        for item in self.labs:
            if item.get("Id") == getattr(request, "Id", None):
                item["Priority"] = getattr(request, "Priority", None)
        return SimpleNamespace(RequestId="req-fake")

    def DeleteLab(self, request):
        self._record("DeleteLab", request)
        self.labs = [t for t in self.labs if t.get("Id") != getattr(request, "Id", None)]
        return SimpleNamespace(RequestId="req-fake")


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_lab_is_idempotent(monkeypatch):
    fake = FakeDlcClient(labs=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ghost-lab")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["lab"] is None
    assert result["lab_id"] is None
    assert [c for c, unused in fake.calls] == ["ListLabs"]


def test_absent_requires_allow_delete(monkeypatch):
    fake = FakeDlcClient(labs=[_lab()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="analytics-notebook")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "allow_delete=true" in exc.value.args[0]["msg"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(labs=[_lab()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", name="analytics-notebook", allow_delete=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.labs) == 1
    assert "DeleteLab" not in [c for c, unused in fake.calls]


def test_absent_deletes_lab(monkeypatch):
    fake = FakeDlcClient(labs=[_lab()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="analytics-notebook", allow_delete=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.labs == []
    assert "DeleteLab" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_creation_parameters(monkeypatch):
    fake = FakeDlcClient(labs=[])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="brand-new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert payload["missing"] == ["resource_partition_id", "queue", "lab_image"]


def test_create_lab(monkeypatch):
    fake = FakeDlcClient(labs=[])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="analytics-notebook",
        resource_partition_id="rp-1",
        queue="default",
        lab_image="ccr.ccs.tencentyun.com/dlc/jupyter:latest",
        description="Analytics lab",
        priority=5,
        enable_token=True,
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lab_id"].startswith("lab-new-")
    assert result["lab"]["Name"] == "analytics-notebook"
    assert result["lab"]["Description"] == "Analytics lab"
    assert len(fake.labs) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "ListLabs"
    assert "CreateLab" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeDlcClient(labs=[])
    _make_module(monkeypatch, fake)
    module_args(
        _ansible_check_mode=True,
        state="present",
        name="analytics-notebook",
        resource_partition_id="rp-1",
        queue="default",
        lab_image="ccr.ccs.tencentyun.com/dlc/jupyter:latest",
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lab_id"] is None
    assert result["lab"]["Name"] == "analytics-notebook"
    assert fake.labs == []
    assert "CreateLab" not in [c for c, unused in fake.calls]


def test_create_includes_tags_and_immutable_json(monkeypatch):
    fake = FakeDlcClient(labs=[])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="analytics-notebook",
        resource_partition_id="rp-1",
        queue="default",
        lab_image="img",
        tags=[{"key": "environment", "value": "production"}],
        resource_config='{"maxWorkers": 10}',
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lab"]["Tags"] == [{"TagKey": "environment", "TagValue": "production"}]
    assert result["lab"]["ResourceConfig"] == '{"maxWorkers":10}'


# ---------------------------------------------------------------------------
# existing-lab flows
# ---------------------------------------------------------------------------


def test_existing_lab_no_drift_is_idempotent(monkeypatch):
    fake = FakeDlcClient(labs=[_lab()])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="analytics-notebook",
        resource_partition_id="rp-1",
        queue="default",
        lab_image="ccr.ccs.tencentyun.com/dlc/jupyter:latest",
        description="Analytics lab",
        priority=5,
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["lab"]["Id"] == "lab-000001"


def test_update_description_drift(monkeypatch):
    fake = FakeDlcClient(labs=[_lab()])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="analytics-notebook",
        resource_partition_id="rp-1",
        queue="default",
        lab_image="ccr.ccs.tencentyun.com/dlc/jupyter:latest",
        description="Renamed description",
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lab"]["Description"] == "Renamed description"
    ops = [c for c, unused in fake.calls]
    assert "UpdateLab" in ops
    assert "ModifyLabPriority" not in ops


def test_update_priority_only_uses_modify_lab_priority(monkeypatch):
    fake = FakeDlcClient(labs=[_lab()])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="analytics-notebook",
        resource_partition_id="rp-1",
        queue="default",
        lab_image="ccr.ccs.tencentyun.com/dlc/jupyter:latest",
        description="Analytics lab",
        priority=9,
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lab"]["Priority"] == 9
    ops = [c for c, unused in fake.calls]
    assert "ModifyLabPriority" in ops
    assert "UpdateLab" not in ops


def test_immutable_drift_fails(monkeypatch):
    fake = FakeDlcClient(labs=[_lab()])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="analytics-notebook", resource_config='{"maxWorkers": 20}')
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "resource configuration, catalog and advanced options are immutable" in payload["msg"]
    assert "ResourceConfig" in payload["immutable_drift"]


def test_multiple_labs_fail(monkeypatch):
    fake = FakeDlcClient(labs=[_lab(), _lab(Id="lab-000002")])
    _make_module(monkeypatch, fake)
    module_args(state="present", name="analytics-notebook")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple DLC laboratories matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# validation / failure paths
# ---------------------------------------------------------------------------


def test_priority_out_of_range_fails(monkeypatch):
    fake = FakeDlcClient(labs=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ghost", priority=10)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "priority must be between 1 and 9" in exc.value.args[0]["msg"]


def test_invalid_resource_config_json_fails(monkeypatch):
    fake = FakeDlcClient(labs=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ghost", resource_config="not-json")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "resource_config must be valid JSON" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def ListLabs(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    module_args(state="present", name="analytics-notebook")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# extra convergence paths
# ---------------------------------------------------------------------------


class PaginatingClient(FakeDlcClient):
    """ListLabs reports two pages: the matching lab only on page one."""

    def ListLabs(self, request):
        self._record("ListLabs", request)
        page = getattr(request, "Page", 1)
        if page == 1:
            return SimpleNamespace(Items=[FakeResource(t) for t in self.labs], TotalPages=2)
        return SimpleNamespace(Items=[], TotalPages=2)


class LagClient(FakeDlcClient):
    """Mutations are only visible from the second read after a write."""

    def __init__(self, labs=None):
        super(LagClient, self).__init__(labs)
        self._staged = None
        self._staged_served = False

    def _stage(self, operation):
        self._staged = operation
        self._staged_served = False

    def CreateLab(self, request):
        self._record("CreateLab", request)
        self._next += 1
        item = dict(getattr(request, "__dict__", {}) or {})
        item["Id"] = "lab-new-%03d" % self._next
        item["Type"] = "WORKSPACE"
        item["Status"] = "RUNNING"
        self._stage(("create", item))
        return SimpleNamespace(Id=item["Id"], RequestId="req-fake")

    def UpdateLab(self, request):
        self._record("UpdateLab", request)
        attrs = {attr: getattr(request, attr) for attr in ("Name", "Description") if getattr(request, attr, None) is not None}
        self._stage(("update", attrs))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteLab(self, request):
        self._record("DeleteLab", request)
        self._stage(("delete", getattr(request, "Id", None)))
        return SimpleNamespace(RequestId="req-fake")

    def ListLabs(self, request):
        if self._staged is not None:
            if not self._staged_served:
                self._staged_served = True
            else:
                operation, payload = self._staged
                if operation == "create":
                    self.labs.append(payload)
                elif operation == "delete":
                    self.labs = [t for t in self.labs if t.get("Id") != payload]
                else:
                    for item in self.labs:
                        if item.get("Name") == payload.get("Name"):
                            item.update({k: v for k, v in payload.items() if k != "Name"})
                self._staged = None
        return super(LagClient, self).ListLabs(request)


def test_find_iterates_pages(monkeypatch):
    fake = PaginatingClient(labs=[_lab()])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="analytics-notebook",
        resource_partition_id="rp-1",
        queue="default",
        lab_image="ccr.ccs.tencentyun.com/dlc/jupyter:latest",
        description="Analytics lab",
        priority=5,
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert len([c for c, unused in fake.calls if c == "ListLabs"]) == 2


def test_create_waits_until_lab_visible(monkeypatch):
    import time

    monkeypatch.setattr(time, "sleep", lambda *args: None)
    fake = LagClient(labs=[])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="analytics-notebook",
        resource_partition_id="rp-1",
        queue="default",
        lab_image="ccr.ccs.tencentyun.com/dlc/jupyter:latest",
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lab"]["Name"] == "analytics-notebook"


def test_update_waits_for_description_convergence(monkeypatch):
    import time

    monkeypatch.setattr(time, "sleep", lambda *args: None)
    fake = LagClient(labs=[_lab()])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="analytics-notebook",
        resource_partition_id="rp-1",
        queue="default",
        lab_image="ccr.ccs.tencentyun.com/dlc/jupyter:latest",
        description="Renamed description",
        wait=True,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["lab"]["Description"] == "Renamed description"


def test_delete_waits_until_lab_absent(monkeypatch):
    import time

    monkeypatch.setattr(time, "sleep", lambda *args: None)
    fake = LagClient(labs=[_lab()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="analytics-notebook", allow_delete=True, wait=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.labs == []


def test_wait_fails_when_lab_enters_failed_status(monkeypatch):
    class FailingLabClient(FakeDlcClient):
        def CreateLab(self, request):
            self._record("CreateLab", request)
            item = dict(getattr(request, "__dict__", {}) or {})
            item["Id"] = "lab-failing"
            item["Type"] = "WORKSPACE"
            item["Status"] = "FAILED"
            self.labs.append(item)
            return SimpleNamespace(Id=item["Id"], RequestId="req-fake")

    fake = FailingLabClient(labs=[])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="analytics-notebook",
        resource_partition_id="rp-1",
        queue="default",
        lab_image="img",
        wait=True,
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "entered a failed state" in exc.value.args[0]["msg"]


def test_normalize_handles_none_immutable_fields(monkeypatch):
    fake = FakeDlcClient(labs=[_lab(ResourceConfig=None, Catalog=None, AdvancedOptions=None)])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="analytics-notebook",
        resource_partition_id="rp-1",
        queue="default",
        lab_image="ccr.ccs.tencentyun.com/dlc/jupyter:latest",
        description="Analytics lab",
        priority=5,
    )
    result = run(mod.run_module)
    assert result["changed"] is False


def test_normalize_keeps_non_json_strings(monkeypatch):
    fake = FakeDlcClient(labs=[_lab(ResourceConfig="not-json")])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="analytics-notebook",
        resource_partition_id="rp-1",
        queue="default",
        lab_image="ccr.ccs.tencentyun.com/dlc/jupyter:latest",
        description="Analytics lab",
        priority=5,
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["lab"]["ResourceConfig"] == "not-json"


def test_normalize_keeps_dict_immutable_fields(monkeypatch):
    fake = FakeDlcClient(labs=[_lab(AdvancedOptions={"alpha": True})])
    _make_module(monkeypatch, fake)
    module_args(
        state="present",
        name="analytics-notebook",
        resource_partition_id="rp-1",
        queue="default",
        lab_image="ccr.ccs.tencentyun.com/dlc/jupyter:latest",
        description="Analytics lab",
        priority=5,
    )
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["lab"]["AdvancedOptions"] == {"alpha": True}
