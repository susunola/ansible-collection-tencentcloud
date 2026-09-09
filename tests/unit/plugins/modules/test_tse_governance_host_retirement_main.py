"""Unit tests for the tse_governance_host_retirement write module.

Drives ``run_module()`` against an in-memory fake TSE governance client
whose paged describe returns a mutable instance list and whose host
retirement deletes the referenced instances so the convergence wait
resolves on the first poll.

Scenario matrix:

* argument guards (batch_size range)
* empty host: idempotent no-op
* retirement: single batch, multi-batch chunking, check-mode dry run
* failure paths: unsuccessful delete result, convergence timeout,
  blanket SDK failure
* legacy pure-helper assertions folded from the shallow test file
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tse_governance_host_retirement as mod
from ansible_collections.susunola.tencentcloud.plugins.modules.tse_governance_host_retirement import (
    batches,
    delete_request,
    describe_request,
)
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

INSTANCE_ID = "ins-1"
HOST = "10.0.0.30"


def _instance(port, host=HOST):
    return {"Host": host, "Port": port}


def _retire_args(**overrides):
    params = {"instance_id": INSTANCE_ID, "host": HOST, "state": "absent"}
    params.update(overrides)
    return module_args(**params)


class FakeGovernanceClient(object):
    """In-memory TSE governance client backed by a mutable instance list."""

    def __init__(self, instances=None, converge=True):
        self.instances = [dict(i) for i in instances or []]
        self.converge = converge
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeGovernanceInstances(self, request):
        self._record("DescribeGovernanceInstances", request)
        payload = [FakeResource(dict(i)) for i in self.instances]
        return SimpleNamespace(Content=payload, TotalCount=len(payload), RequestId="req-fake")

    def DeleteGovernanceInstancesByHost(self, request):
        self._record("DeleteGovernanceInstancesByHost", request)
        markers = [(getattr(item, "Host", None), getattr(item, "Port", None))
                   for item in getattr(request, "GovernanceInstances", None) or []]
        if self.converge:
            self.instances = [i for i in self.instances if (i["Host"], i["Port"]) not in markers]
        return SimpleNamespace(Result=True, RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(TseClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [c for c, unused in fake.calls]


def _delete_batch_sizes(fake):
    return [len(getattr(request, "GovernanceInstances", None) or [])
            for name, request in fake.calls if name == "DeleteGovernanceInstancesByHost"]


# ---------------------------------------------------------------------------
# argument guards
# ---------------------------------------------------------------------------


def test_batch_size_zero_fails():
    _retire_args(batch_size=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "batch_size must be between 1 and 100" in exc.value.args[0]["msg"]


def test_batch_size_over_100_fails():
    _retire_args(batch_size=101)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "batch_size must be between 1 and 100" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# retirement flows
# ---------------------------------------------------------------------------


def test_empty_host_is_idempotent(monkeypatch):
    fake = FakeGovernanceClient()
    _make_module(monkeypatch, fake)
    _retire_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["host"] == HOST
    assert result["removed_instances"] == []
    assert "DeleteGovernanceInstancesByHost" not in _names(fake)


def test_retire_removes_all_host_instances(monkeypatch):
    fake = FakeGovernanceClient(instances=[_instance(8080), _instance(8081)])
    _make_module(monkeypatch, fake)
    _retire_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["host"] == HOST
    assert len(result["removed_instances"]) == 2
    assert "DeleteGovernanceInstancesByHost" in _names(fake)
    assert fake.instances == []


def test_retire_chunks_instances_into_batches(monkeypatch):
    fake = FakeGovernanceClient(instances=[_instance(8000 + i) for i in range(5)])
    _make_module(monkeypatch, fake)
    _retire_args(batch_size=2)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(result["removed_instances"]) == 5
    assert _delete_batch_sizes(fake) == [2, 2, 1]
    assert fake.instances == []


def test_retire_only_targets_matching_host(monkeypatch):
    fake = FakeGovernanceClient(instances=[_instance(8080), _instance(9090, host="10.0.0.99")])
    _make_module(monkeypatch, fake)
    _retire_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["removed_instances"] == [_instance(8080)]
    assert fake.instances == [_instance(9090, host="10.0.0.99")]


def test_retire_check_mode_is_dry_run(monkeypatch):
    fake = FakeGovernanceClient(instances=[_instance(8080)])
    _make_module(monkeypatch, fake)
    _retire_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(result["removed_instances"]) == 1
    assert "DeleteGovernanceInstancesByHost" not in _names(fake)
    assert fake.instances == [_instance(8080)]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_unsuccessful_delete_result_fails(monkeypatch):
    class RejectingClient(FakeGovernanceClient):
        def DeleteGovernanceInstancesByHost(self, request):
            self._record("DeleteGovernanceInstancesByHost", request)
            return SimpleNamespace(Result=False, RequestId="req-fake")

    fake = RejectingClient(instances=[_instance(8080)])
    _make_module(monkeypatch, fake)
    _retire_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "returned an unsuccessful result" in exc.value.args[0]["msg"]


def test_convergence_timeout_fails(monkeypatch):
    fake = FakeGovernanceClient(instances=[_instance(8080)], converge=False)
    _make_module(monkeypatch, fake)
    _retire_args(waiter_timeout=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "Timed out waiting" in exc.value.args[0]["msg"]


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeGovernanceInstances(self, request):
            raise Boom("connection dropped")

    _make_module(monkeypatch, ExplodingClient())
    _retire_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


# ---------------------------------------------------------------------------
# legacy pure-helper assertions (folded from the shallow test file)
# ---------------------------------------------------------------------------


def test_legacy_retirement_requests_map_host_and_instances():
    models = FakeModels()
    describe = describe_request(models, {"instance_id": INSTANCE_ID, "host": HOST}, 20)
    deletion = delete_request(models, {"instance_id": INSTANCE_ID, "host": HOST}, [{"Host": HOST, "Port": 8080}])
    assert (describe.InstanceId, describe.Host, describe.Offset, describe.Limit) == (INSTANCE_ID, HOST, 20, 100)
    assert len(deletion.GovernanceInstances) == 1


def test_legacy_batches_preserve_every_instance():
    assert list(batches([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]
