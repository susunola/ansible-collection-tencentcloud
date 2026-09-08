"""Unit tests for the tse_governance_instance write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake TSE client
whose write operations mutate the governance-instance store, so the module's
``find`` refetches and ``wait()`` reconverge on the first poll.

Scenario matrix:

* absent (missing instance no-op, real delete, check-mode dry run, the
  unsuccessful-result guard and a delete that never converges)
* creation (missing instance, check mode, metadata supplied after create,
  unsuccessful result and a create that never becomes visible)
* existing (no-drift idempotency, mutable-drift modify, check-mode dry run,
  identity change via governance_instance_id)
* guards (multiple matches) and the blanket ``sdk_error_payload`` failure
  path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_governance_instance as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE = {
    "Id": "gov-001",
    "Namespace": "production",
    "Service": "orders",
    "Host": "10.0.0.30",
    "Port": 8080,
    "Protocol": "http",
    "Weight": 100,
}


def _instance(**overrides):
    item = copy.deepcopy(INSTANCE)
    item.update(overrides)
    return item


def _plain(value):
    """Recursively unwrap FakeRequest/model stand-ins into plain data."""
    if value is None or isinstance(value, bool) or isinstance(value, (str, int, float)):
        return value
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return {key: _plain(item) for key, item in vars(value).items()}


class FakeGovernanceClient(object):
    """In-memory TSE governance-service-instance client."""

    def __init__(self, instances=None, create_stores=True, create_result=True, delete_removes=True):
        self.instances = [copy.deepcopy(item) for item in (instances or [])]
        self.calls = []
        self._next = 0
        self.create_stores = create_stores
        self.create_result = create_result
        self.delete_removes = delete_removes

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _entry(self, request):
        source = request.GovernanceInstances[0]
        return {key: _plain(value) for key, value in vars(source).items()}

    def DescribeGovernanceInstances(self, request):
        self._record("DescribeGovernanceInstances", request)
        return SimpleNamespace(
            Content=[FakeResource(item) for item in self.instances],
            TotalCount=len(self.instances),
            RequestId="req-fake",
        )

    def CreateGovernanceInstances(self, request):
        self._record("CreateGovernanceInstances", request)
        if self.create_stores:
            self._next += 1
            item = self._entry(request)
            item["Id"] = "gov-%03d" % self._next
            self.instances.append(item)
        return SimpleNamespace(Result=self.create_result, RequestId="req-fake")

    def ModifyGovernanceInstances(self, request):
        self._record("ModifyGovernanceInstances", request)
        item = self._entry(request)
        for entry in self.instances:
            if entry.get("Id") == item.get("Id"):
                entry.update(item)
        return SimpleNamespace(Result=True, RequestId="req-fake")

    def DeleteGovernanceInstances(self, request):
        self._record("DeleteGovernanceInstances", request)
        item = self._entry(request)
        if self.delete_removes:
            self.instances = [entry for entry in self.instances if entry.get("Id") != item.get("Id")]
        return SimpleNamespace(Result=True, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _args(**overrides):
    params = {
        "instance_id": "ins-1",
        "namespace": "production",
        "service": "orders",
        "host": "10.0.0.30",
        "port": 8080,
        "protocol": "http",
        "weight": 100,
    }
    params.update(overrides)
    return module_args(**params)


def _ops(fake):
    return [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_instance_is_idempotent(monkeypatch):
    fake = FakeGovernanceClient(instances=[])
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["governance_instance"] is None
    assert "DeleteGovernanceInstances" not in _ops(fake)


def test_absent_deletes_instance(monkeypatch):
    fake = FakeGovernanceClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _args(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["governance_instance"] is None
    assert fake.instances == []
    assert "DeleteGovernanceInstances" in _ops(fake)


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeGovernanceClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, state="absent")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["governance_instance"] is None
    assert result["diff"]["after"] is None
    assert len(fake.instances) == 1
    assert "DeleteGovernanceInstances" not in _ops(fake)


def test_delete_rejected_when_result_false(monkeypatch):
    fake = FakeGovernanceClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _args(state="absent")
    fake.DeleteGovernanceInstances = lambda request: SimpleNamespace(Result=False, RequestId="req-fake")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "returned an unsuccessful result" in payload["msg"]
    assert payload["operation"] == "DeleteGovernanceInstances"


def test_delete_wait_timeout_when_instance_remains(monkeypatch):
    fake = FakeGovernanceClient(instances=[_instance()], delete_removes=False)
    _make_module(monkeypatch, fake)
    _args(state="absent", waiter_timeout=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Timed out waiting for TSE governance service instance convergence" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_missing_governance_instance(monkeypatch):
    fake = FakeGovernanceClient(instances=[])
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is True
    payload = result["governance_instance"]
    assert payload["Namespace"] == "production"
    assert payload["Service"] == "orders"
    assert payload["Host"] == "10.0.0.30"
    assert payload["Port"] == 8080
    assert payload["Weight"] == 100
    assert payload["Id"]
    assert len(fake.instances) == 1
    assert fake.instances[0]["Host"] == "10.0.0.30"
    ops = _ops(fake)
    assert "CreateGovernanceInstances" in ops
    assert "ModifyGovernanceInstances" not in ops
    assert ops[-1] == "DescribeGovernanceInstances"


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeGovernanceClient(instances=[])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"] is None
    assert result["governance_instance"]["Weight"] == 100
    assert fake.instances == []
    assert "CreateGovernanceInstances" not in _ops(fake)


def test_create_with_metadata_triggers_modify(monkeypatch):
    fake = FakeGovernanceClient(instances=[])
    _make_module(monkeypatch, fake)
    metadata = [{"Key": "environment", "Value": "production"}]
    _args(metadata=copy.deepcopy(metadata))
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["governance_instance"]["Metadatas"] == metadata
    assert fake.instances[0]["Metadatas"] == metadata
    ops = _ops(fake)
    assert "CreateGovernanceInstances" in ops
    assert "ModifyGovernanceInstances" in ops


def test_create_unsuccessful_result_fails(monkeypatch):
    fake = FakeGovernanceClient(instances=[], create_result=False)
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "returned an unsuccessful result" in payload["msg"]
    assert payload["operation"] == "CreateGovernanceInstances"


def test_create_wait_timeout_when_instance_invisible(monkeypatch):
    fake = FakeGovernanceClient(instances=[], create_stores=False)
    _make_module(monkeypatch, fake)
    _args(waiter_timeout=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Timed out waiting for TSE governance service instance convergence" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# existing-instance flows
# ---------------------------------------------------------------------------


def test_existing_no_drift_is_idempotent(monkeypatch):
    fake = FakeGovernanceClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["governance_instance"]["Id"] == "gov-001"
    ops = _ops(fake)
    assert "CreateGovernanceInstances" not in ops
    assert "ModifyGovernanceInstances" not in ops


def test_mutable_drift_updates_instance(monkeypatch):
    fake = FakeGovernanceClient(instances=[_instance(Weight=100)])
    _make_module(monkeypatch, fake)
    _args(weight=50)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["governance_instance"]["Weight"] == 50
    assert fake.instances[0]["Weight"] == 50
    ops = _ops(fake)
    assert "CreateGovernanceInstances" not in ops
    assert "ModifyGovernanceInstances" in ops


def test_mutable_drift_check_mode_is_dry_run(monkeypatch):
    fake = FakeGovernanceClient(instances=[_instance(Weight=100)])
    _make_module(monkeypatch, fake)
    _args(_ansible_check_mode=True, weight=50)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["governance_instance"]["Weight"] == 50
    assert fake.instances[0]["Weight"] == 100
    assert "ModifyGovernanceInstances" not in _ops(fake)


def test_identity_change_via_governance_instance_id(monkeypatch):
    fake = FakeGovernanceClient(instances=[_instance()])
    _make_module(monkeypatch, fake)
    _args(governance_instance_id="gov-001", host="10.0.0.99", port=9090)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["governance_instance"]["Host"] == "10.0.0.99"
    assert result["governance_instance"]["Port"] == 9090
    assert fake.instances[0]["Host"] == "10.0.0.99"
    ops = _ops(fake)
    assert "CreateGovernanceInstances" not in ops
    assert "ModifyGovernanceInstances" in ops


def test_multiple_matches_fail(monkeypatch):
    fake = FakeGovernanceClient(instances=[_instance(), _instance(Id="gov-002")])
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Multiple TSE governance service instances matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeGovernanceInstances(self, request):
            raise Boom("engine down")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "engine down" in payload["error"]
