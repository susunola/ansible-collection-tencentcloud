"""Unit tests for the lighthouse_instance write module (helpers + run_module).

Covers the create / start / stop / isolate / rename flows of
``plugins/modules/lighthouse_instance.py`` with an in-memory fake Lighthouse
client whose write operations mutate the store, so the module's waiters see
the converged state on their first poll (no sleeps in tests), following the
collection's module test harness (see harness.py).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import lighthouse_instance as lh
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE = {
    "InstanceId": "lhins-8b0a1c2d",
    "InstanceName": "blog-01",
    "InstanceState": "RUNNING",
    "BundleId": "bundle_2022_std_1c1g",
    "BlueprintId": "lhbp-abcdefgh",
}

WRITE_OPS = (
    "CreateInstances",
    "ModifyInstancesAttribute",
    "StartInstances",
    "StopInstances",
    "IsolateInstances",
)


def _instance(**overrides):
    """Return an instance fixture isolated from the shared INSTANCE constant."""
    instance = copy.deepcopy(INSTANCE)
    instance.update(overrides)
    return instance


class FakeLighthouseClient(object):
    """In-memory Lighthouse client that mutates a small instance store."""

    def __init__(self, instances=None):
        self.instances = [copy.deepcopy(instance) for instance in (instances or [])]
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def _by_id(self, instance_id):
        return next(item for item in self.instances if item["InstanceId"] == instance_id)

    def _match(self, request):
        items = self.instances
        if getattr(request, "InstanceIds", None):
            wanted = set(request.InstanceIds)
            items = [item for item in items if item["InstanceId"] in wanted]
        elif getattr(request, "Filters", None):
            wanted = set(request.Filters[0].Values)
            items = [item for item in items if item.get("InstanceName") in wanted]
        return items

    def DescribeInstances(self, request):
        self._record("DescribeInstances", request)
        return SimpleNamespace(InstanceSet=[FakeResource(dict(item)) for item in self._match(request)])

    def CreateInstances(self, request):
        self._record("CreateInstances", request)
        created = []
        for offset in range(request.InstanceCount):
            instance_id = "lhins-new-%d" % (len(self.instances) + offset + 1)
            self.instances.append(
                {
                    "InstanceId": instance_id,
                    "InstanceName": getattr(request, "InstanceName", None),
                    "InstanceState": "RUNNING",
                    "BundleId": request.BundleId,
                    "BlueprintId": request.BlueprintId,
                }
            )
            created.append(instance_id)
        return SimpleNamespace(InstanceIdSet=created)

    def ModifyInstancesAttribute(self, request):
        self._record("ModifyInstancesAttribute", request)
        for instance_id in request.InstanceIds:
            self._by_id(instance_id)["InstanceName"] = request.InstanceName
        return SimpleNamespace()

    def StartInstances(self, request):
        self._record("StartInstances", request)
        for instance_id in request.InstanceIds:
            self._by_id(instance_id)["InstanceState"] = "RUNNING"
        return SimpleNamespace()

    def StopInstances(self, request):
        self._record("StopInstances", request)
        for instance_id in request.InstanceIds:
            self._by_id(instance_id)["InstanceState"] = "STOPPED"
        return SimpleNamespace()

    def IsolateInstances(self, request):
        self._record("IsolateInstances", request)
        for instance_id in request.InstanceIds:
            self._by_id(instance_id)["InstanceState"] = "ISOLATED"
        return SimpleNamespace()


class FakeModule(object):
    """Minimal stand-in for helpers that only need sdk_call / waiter params."""

    def __init__(self, check_mode=False, params=None):
        self.check_mode = check_mode
        self.params = params or {"retries": 2, "waiter_timeout": 120, "waiter_delay": 5}

    def sdk_call(self, operation, request):
        return operation(request)


@pytest.fixture
def client(monkeypatch):
    fake = FakeLighthouseClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        lh,
        "_load_lighthouse",
        lambda: (FakeModels(), SimpleNamespace(LighthouseClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


def test_build_describe_request_by_id():
    request = lh.build_describe_request(FakeModels(), "lhins-1", None)
    assert request.InstanceIds == ["lhins-1"]
    assert request.Offset == 0
    assert request.Limit == 100
    assert not hasattr(request, "Filters") or request.Filters is None


def test_build_describe_request_by_name():
    request = lh.build_describe_request(FakeModels(), None, "blog-01")
    assert request.Filters[0].Name == "instance-name"
    assert request.Filters[0].Values == ["blog-01"]
    assert not hasattr(request, "InstanceIds") or request.InstanceIds is None


def test_build_describe_request_no_lookup_has_no_filters():
    request = lh.build_describe_request(FakeModels(), None, None)
    assert request.Offset == 0
    assert not hasattr(request, "InstanceIds")
    assert not hasattr(request, "Filters")


def test_find_instance_matches_by_name():
    module = FakeModule()
    client = FakeLighthouseClient(instances=[_instance()])
    found = lh.find_instance(module, client, FakeModels(), None, "blog-01")
    assert found["InstanceId"] == "lhins-8b0a1c2d"
    assert found["InstanceState"] == "RUNNING"
    assert [name for name, request in client.calls] == ["DescribeInstances"]


def test_find_instance_matches_by_id():
    module = FakeModule()
    client = FakeLighthouseClient(instances=[_instance()])
    found = lh.find_instance(module, client, FakeModels(), "lhins-8b0a1c2d", None)
    assert found["InstanceName"] == "blog-01"


def test_find_instance_missing_returns_none():
    module = FakeModule()
    client = FakeLighthouseClient()
    assert lh.find_instance(module, client, FakeModels(), "lhins-9", None) is None


def test_build_create_request_full():
    params = {
        "bundle_id": "bundle_2022_std_1c1g",
        "blueprint_id": "lhbp-1",
        "instance_count": 2,
        "instance_name": "blog-01",
        "zones": ["ap-guangzhou-3"],
        "password": "secret",
        "prepaid_period": 1,
    }
    request = lh.build_create_request(FakeModels(), params)
    assert request.BundleId == "bundle_2022_std_1c1g"
    assert request.BlueprintId == "lhbp-1"
    assert request.InstanceCount == 2
    assert request.InstanceName == "blog-01"
    assert request.Zones == ["ap-guangzhou-3"]
    assert request.LoginConfiguration.Password == "secret"
    assert request.InstanceChargePrepaid.Period == 1


def test_build_create_request_minimal():
    params = {
        "bundle_id": "bundle_x",
        "blueprint_id": "lhbp-1",
        "instance_count": 1,
        "instance_name": None,
        "zones": None,
        "password": None,
        "prepaid_period": None,
    }
    request = lh.build_create_request(FakeModels(), params)
    assert request.BundleId == "bundle_x"
    assert request.InstanceCount == 1
    assert not hasattr(request, "InstanceName")
    assert not hasattr(request, "Zones")
    assert not hasattr(request, "LoginConfiguration")
    assert not hasattr(request, "InstanceChargePrepaid")


def test_create_appends_instance_and_returns_ids():
    module = FakeModule()
    client = FakeLighthouseClient()
    params = {
        "bundle_id": "bundle_2022_std_1c1g",
        "blueprint_id": "lhbp-1",
        "instance_count": 1,
        "instance_name": "blog-01",
        "zones": None,
        "password": None,
        "prepaid_period": None,
    }
    response = lh._create(module, client, FakeModels(), params)
    assert response.InstanceIdSet == ["lhins-new-1"]
    assert client.calls[-1][0] == "CreateInstances"
    assert client.instances[0]["InstanceState"] == "RUNNING"


def test_start_mutates_instance_to_running():
    module = FakeModule()
    client = FakeLighthouseClient(instances=[_instance(InstanceState="STOPPED")])
    lh._start(module, client, FakeModels(), "lhins-8b0a1c2d")
    assert client.calls[-1][0] == "StartInstances"
    assert client.calls[-1][1].InstanceIds == ["lhins-8b0a1c2d"]
    assert client.instances[0]["InstanceState"] == "RUNNING"


def test_stop_mutates_instance_to_stopped():
    module = FakeModule()
    client = FakeLighthouseClient(instances=[_instance()])
    lh._stop(module, client, FakeModels(), "lhins-8b0a1c2d")
    assert client.calls[-1][0] == "StopInstances"
    assert client.instances[0]["InstanceState"] == "STOPPED"


def test_isolate_mutates_instance_to_isolated():
    module = FakeModule()
    client = FakeLighthouseClient(instances=[_instance()])
    lh._isolate(module, client, FakeModels(), "lhins-8b0a1c2d")
    assert client.calls[-1][0] == "IsolateInstances"
    assert client.instances[0]["InstanceState"] == "ISOLATED"


def test_update_name_mutates_instance_name():
    module = FakeModule()
    client = FakeLighthouseClient(instances=[_instance()])
    lh._update_name(module, client, FakeModels(), "lhins-8b0a1c2d", "blog-02")
    request = client.calls[-1][1]
    assert request.InstanceIds == ["lhins-8b0a1c2d"]
    assert request.InstanceName == "blog-02"
    assert client.instances[0]["InstanceName"] == "blog-02"


def test_immutable_drift_detects_changes():
    current = {"BundleId": "bundle_old", "BlueprintId": "lhbp-1"}
    params = {
        "bundle_id": "bundle_new",
        "blueprint_id": "lhbp-1",
        "password": "secret",
        "instance_count": 2,
    }
    drifted = lh._immutable_drift(current, params)
    assert "bundle_id" in drifted
    assert "blueprint_id" not in drifted
    assert "password" in drifted
    assert "instance_count" in drifted


def test_immutable_drift_empty_when_matching():
    current = {"BundleId": "bundle_2022_std_1c1g", "BlueprintId": "lhbp-abcdefgh"}
    params = {"bundle_id": "bundle_2022_std_1c1g", "blueprint_id": "lhbp-abcdefgh", "password": None, "instance_count": 1}
    assert lh._immutable_drift(current, params) == []


def test_state_poll_returns_current_state():
    module = FakeModule()
    client = FakeLighthouseClient(instances=[_instance(InstanceState="RUNNING")])
    poll = lh._state_poll(module, client, FakeModels(), "lhins-8b0a1c2d")
    assert poll() == "RUNNING"


def test_state_poll_returns_gone_when_instance_missing():
    module = FakeModule()
    client = FakeLighthouseClient()
    poll = lh._state_poll(module, client, FakeModels(), "lhins-9")
    assert poll() == "GONE"


def test_wait_state_returns_when_converged():
    module = FakeModule()
    client = FakeLighthouseClient(instances=[_instance(InstanceState="RUNNING")])
    result = lh._wait_state(module, client, FakeModels(), "lhins-8b0a1c2d", ["RUNNING"])
    assert result == "RUNNING"


def test_wait_state_check_mode_returns_none():
    module = FakeModule(check_mode=True)
    client = FakeLighthouseClient(instances=[_instance(InstanceState="STOPPED")])
    assert lh._wait_state(module, client, FakeModels(), "lhins-8b0a1c2d", ["RUNNING"]) is None


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_state_absent_requires_id_or_name(client):
    module_args(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lh.run_module)
    assert "instance_id or instance_name is required when state=absent" in exc.value.args[0]["msg"]


def test_state_running_requires_id_or_name(client):
    module_args(state="running")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lh.run_module)
    assert "instance_id or instance_name is required when state=running" in exc.value.args[0]["msg"]


def test_absent_missing_instance_is_unchanged(client):
    module_args(state="absent", instance_name="blog-01")
    result = run(lh.run_module)
    assert result["changed"] is False
    assert "already absent" in result["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_absent_isolated_instance_is_unchanged(client):
    client.instances = [_instance(InstanceState="ISOLATED")]
    module_args(state="absent", instance_id="lhins-8b0a1c2d")
    result = run(lh.run_module)
    assert result["changed"] is False
    assert "already absent" in result["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_absent_isolates_running_instance(client):
    client.instances = [_instance()]
    module_args(state="absent", instance_id="lhins-8b0a1c2d")
    result = run(lh.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Instance isolated"
    assert result["instance"] is None
    assert any(name == "IsolateInstances" for name, request in client.calls)
    assert client.instances[0]["InstanceState"] == "ISOLATED"


def test_check_mode_absent_makes_no_writes(client):
    client.instances = [_instance()]
    module_args(state="absent", instance_id="lhins-8b0a1c2d", _ansible_check_mode=True)
    result = run(lh.run_module)
    assert result["changed"] is True
    assert "Would isolate" in result["msg"]
    assert result["diff"]["before"]["InstanceState"] == "RUNNING"
    assert result["diff"]["after"] is None
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_running_missing_instance_fails(client):
    module_args(state="running", instance_name="blog-01")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lh.run_module)
    payload = exc.value.args[0]
    assert "Instance not found" in payload["msg"]
    assert "use state=present" in payload["msg"]


def test_running_already_running_is_unchanged(client):
    client.instances = [_instance()]
    module_args(state="running", instance_id="lhins-8b0a1c2d")
    result = run(lh.run_module)
    assert result["changed"] is False
    assert "already running" in result["msg"]
    assert result["instance"]["InstanceState"] == "RUNNING"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_running_starts_stopped_instance(client):
    client.instances = [_instance(InstanceState="STOPPED")]
    module_args(state="running", instance_id="lhins-8b0a1c2d")
    result = run(lh.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Instance started"
    assert any(name == "StartInstances" for name, request in client.calls)
    assert result["instance"]["InstanceState"] == "RUNNING"


def test_running_from_unsupported_state_fails(client):
    client.instances = [_instance(InstanceState="CREATING")]
    module_args(state="running", instance_id="lhins-8b0a1c2d")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lh.run_module)
    payload = exc.value.args[0]
    assert "must be STOPPED before starting" in payload["msg"]
    assert "CREATING" in payload["msg"]


def test_check_mode_running_makes_no_writes(client):
    client.instances = [_instance(InstanceState="STOPPED")]
    module_args(state="running", instance_id="lhins-8b0a1c2d", _ansible_check_mode=True)
    result = run(lh.run_module)
    assert result["changed"] is True
    assert "Would start" in result["msg"]
    assert result["diff"]["after"]["InstanceState"] == "RUNNING"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_stopped_already_stopped_is_unchanged(client):
    client.instances = [_instance(InstanceState="STOPPED")]
    module_args(state="stopped", instance_id="lhins-8b0a1c2d")
    result = run(lh.run_module)
    assert result["changed"] is False
    assert "already stopped" in result["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_stopped_stops_running_instance(client):
    client.instances = [_instance()]
    module_args(state="stopped", instance_id="lhins-8b0a1c2d")
    result = run(lh.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Instance stopped"
    assert any(name == "StopInstances" for name, request in client.calls)
    assert result["instance"]["InstanceState"] == "STOPPED"


def test_stopped_from_unsupported_state_fails(client):
    client.instances = [_instance(InstanceState="CREATING")]
    module_args(state="stopped", instance_id="lhins-8b0a1c2d")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lh.run_module)
    payload = exc.value.args[0]
    assert "must be RUNNING before stopping" in payload["msg"]
    assert "CREATING" in payload["msg"]


def test_check_mode_stopped_makes_no_writes(client):
    client.instances = [_instance()]
    module_args(state="stopped", instance_id="lhins-8b0a1c2d", _ansible_check_mode=True)
    result = run(lh.run_module)
    assert result["changed"] is True
    assert "Would stop" in result["msg"]
    assert result["diff"]["after"]["InstanceState"] == "STOPPED"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_create_requires_bundle_and_blueprint(client):
    module_args(state="present", instance_name="blog-01")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lh.run_module)
    assert "bundle_id and blueprint_id are required" in exc.value.args[0]["msg"]


def test_present_creates_instance(client):
    module_args(
        state="present",
        instance_name="blog-01",
        bundle_id="bundle_2022_std_1c1g",
        blueprint_id="lhbp-abcdefgh",
        zones=["ap-guangzhou-3"],
    )
    result = run(lh.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Instance created"
    assert any(name == "CreateInstances" for name, request in client.calls)
    assert len(client.instances) == 1
    assert client.instances[0]["InstanceId"] == "lhins-new-1"
    assert result["instance"]["InstanceState"] == "RUNNING"
    assert result["instance"]["InstanceId"] == "lhins-new-1"


def test_present_create_multiple_instances_uses_first_id(client):
    module_args(
        state="present",
        instance_name="blog-01",
        bundle_id="bundle_2022_std_1c1g",
        blueprint_id="lhbp-abcdefgh",
        instance_count=2,
    )
    result = run(lh.run_module)
    assert result["changed"] is True
    assert len(client.instances) == 2
    assert result["instance"]["InstanceId"] == "lhins-new-1"
    assert client.instances[1]["InstanceState"] == "RUNNING"


def test_check_mode_present_create_makes_no_writes(client):
    module_args(
        state="present",
        instance_name="blog-01",
        bundle_id="bundle_2022_std_1c1g",
        blueprint_id="lhbp-abcdefgh",
        _ansible_check_mode=True,
    )
    result = run(lh.run_module)
    assert result["changed"] is True
    assert "Would create" in result["msg"]
    assert result["diff"]["after"]["BundleId"] == "bundle_2022_std_1c1g"
    assert result["diff"]["after"]["BlueprintId"] == "lhbp-abcdefgh"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_create_no_returned_ids_fails(client):
    def no_ids(request):
        return SimpleNamespace(InstanceIdSet=[])

    client.CreateInstances = no_ids
    module_args(
        state="present",
        instance_name="blog-01",
        bundle_id="bundle_2022_std_1c1g",
        blueprint_id="lhbp-abcdefgh",
    )
    with pytest.raises(AnsibleFailJson) as exc:
        run(lh.run_module)
    assert "returned no instance IDs" in exc.value.args[0]["msg"]


def test_present_matching_instance_is_unchanged(client):
    client.instances = [_instance()]
    module_args(state="present", instance_name="blog-01")
    result = run(lh.run_module)
    assert result["changed"] is False
    assert "up to date" in result["msg"]
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_present_bundle_drift_fails(client):
    client.instances = [_instance()]
    module_args(state="present", instance_id="lhins-8b0a1c2d", bundle_id="bundle_new")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lh.run_module)
    payload = exc.value.args[0]
    assert "bundle_id" in payload["msg"]
    assert "cannot be changed on an existing instance" in payload["msg"]


def test_present_blueprint_drift_fails(client):
    client.instances = [_instance()]
    module_args(state="present", instance_id="lhins-8b0a1c2d", blueprint_id="lhbp-other")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lh.run_module)
    assert "blueprint_id" in exc.value.args[0]["msg"]


def test_present_password_drift_fails(client):
    client.instances = [_instance()]
    module_args(state="present", instance_id="lhins-8b0a1c2d", password="new-secret")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lh.run_module)
    assert "password" in exc.value.args[0]["msg"]


def test_present_instance_count_drift_fails(client):
    client.instances = [_instance()]
    module_args(state="present", instance_id="lhins-8b0a1c2d", instance_count=3)
    with pytest.raises(AnsibleFailJson) as exc:
        run(lh.run_module)
    assert "instance_count" in exc.value.args[0]["msg"]


def test_present_updates_instance_name(client):
    client.instances = [_instance()]
    module_args(state="present", instance_id="lhins-8b0a1c2d", instance_name="blog-02")
    result = run(lh.run_module)
    assert result["changed"] is True
    assert result["msg"] == "Instance name updated"
    assert any(name == "ModifyInstancesAttribute" for name, request in client.calls)
    assert client.instances[0]["InstanceName"] == "blog-02"
    assert result["instance"]["InstanceName"] == "blog-02"


def test_check_mode_present_name_update_makes_no_writes(client):
    client.instances = [_instance()]
    module_args(
        state="present",
        instance_id="lhins-8b0a1c2d",
        instance_name="blog-02",
        _ansible_check_mode=True,
    )
    result = run(lh.run_module)
    assert result["changed"] is True
    assert "Would update instance name" in result["msg"]
    assert result["diff"]["before"]["InstanceName"] == "blog-01"
    assert result["diff"]["after"]["InstanceName"] == "blog-02"
    assert not any(name in WRITE_OPS for name, request in client.calls)


def test_sdk_error_on_describe_is_reported(client):
    def boom(request):
        raise RuntimeError("lighthouse api exploded")

    client.DescribeInstances = boom
    module_args(state="present", instance_name="blog-01")
    with pytest.raises(AnsibleFailJson) as exc:
        run(lh.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "lighthouse api exploded" in payload["error"]
