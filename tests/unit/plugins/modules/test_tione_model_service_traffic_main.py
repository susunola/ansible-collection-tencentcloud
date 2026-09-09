"""Unit tests for the tione_model_service_traffic write module (run_module flows).

``run_module()`` reconciles a TIONE service group's authorization switch and
per-version traffic weights. It is driven end to end against an in-memory
fake client whose ``ModifyModelServiceAuthorization`` and
``ModifyServiceGroupWeights`` operations mutate a service-group store, so
the post-write ``DescribeModelServiceGroup`` refetch (and weight waiter)
converge immediately.

Scenario matrix:

* idempotent no-op when authorization and weights already match
* authorization drift (check mode and real update)
* weight drift waiting on convergence, and with ``wait=False``
* weight waiter ``update_failed`` and timeout failure paths
* argument validation before any SDK call (missing fields, malformed
  weights) including project_id propagation on the describe request
* missing service group and blanket ``sdk_error_payload`` failure paths
* legacy helper regression tests (folded from
  test_tione_model_service_traffic.py)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import tione_model_service_traffic as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

GROUP_ID = "ms-group-abc"
WEIGHTS = [{"ServiceId": "ms-v1", "Weight": 90}, {"ServiceId": "ms-v2", "Weight": 10}]
NORMALIZED = [{"ServiceId": "ms-v1", "Weight": 90}, {"ServiceId": "ms-v2", "Weight": 10}]


def _base(**overrides):
    params = {
        "service_group_id": GROUP_ID,
        "authorization_enable": True,
        "weights": WEIGHTS,
        "wait": True,
    }
    params.update(overrides)
    return module_args(**params)


def _group(authorization=True, services=None, weight_status=""):
    return {
        "ServiceGroupId": GROUP_ID,
        "AuthorizationEnable": authorization,
        "WeightUpdateStatus": weight_status,
        "Services": services
        if services is not None
        else [
            {"ServiceId": "ms-v1", "Weight": 90, "Status": "Normal"},
            {"ServiceId": "ms-v2", "Weight": 10, "Status": "Normal"},
        ],
    }


class FakeTioneClient(object):
    """In-memory TIONE client holding one service group's live state."""

    def __init__(self, group=None, weight_result="ok", weight_apply=True):
        self.group = copy.deepcopy(group) if group is not None else None
        self.weight_result = weight_result
        self.weight_apply = weight_apply
        self.calls = []
        self.last_group_request = None

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def DescribeModelServiceGroup(self, request):
        self._record("DescribeModelServiceGroup", request)
        self.last_group_request = request
        assert request.ServiceGroupId == GROUP_ID
        return SimpleNamespace(
            ServiceGroup=FakeResource(self.group) if self.group is not None else None,
            RequestId="req-fake",
        )

    def ModifyModelServiceAuthorization(self, request):
        self._record("ModifyModelServiceAuthorization", request)
        if self.group is not None:
            self.group["AuthorizationEnable"] = bool(request.AuthorizationEnable)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyServiceGroupWeights(self, request):
        self._record("ModifyServiceGroupWeights", request)
        self.last_weights_request = request
        if self.weight_apply:
            self.group["Services"] = [dict(item.__dict__) for item in request.Weights]
        if self.weight_result == "failed":
            self.group["WeightUpdateStatus"] = "update_failed"
        elif self.weight_result == "stuck":
            self.group["WeightUpdateStatus"] = "updating"
        else:
            self.group["WeightUpdateStatus"] = ""
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (FakeModels(), SimpleNamespace(TioneClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _names(fake):
    return [name for name, unused in fake.calls]


# ---------------------------------------------------------------------------
# idempotent no-op flows
# ---------------------------------------------------------------------------


def test_converged_group_is_idempotent(monkeypatch):
    fake = _make_module(monkeypatch, FakeTioneClient(group=_group()))
    _base()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["service_group"]["AuthorizationEnable"] is True
    assert _names(fake) == ["DescribeModelServiceGroup"]


def test_omitted_sections_do_not_drift(monkeypatch):
    fake = _make_module(monkeypatch, FakeTioneClient(group=_group()))
    _base(authorization_enable=None, weights=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "authorization_enable or weights is required" in exc.value.args[0]["msg"]
    assert fake.calls == []


# ---------------------------------------------------------------------------
# authorization drift flows
# ---------------------------------------------------------------------------


def test_authorization_drift_updates_switch(monkeypatch):
    fake = _make_module(monkeypatch, FakeTioneClient(group=_group(authorization=True)))
    _base(authorization_enable=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service_group"]["AuthorizationEnable"] is False
    assert fake.group["AuthorizationEnable"] is False
    assert _names(fake) == ["DescribeModelServiceGroup", "ModifyModelServiceAuthorization", "DescribeModelServiceGroup"]


def test_authorization_drift_check_mode_is_dry_run(monkeypatch):
    fake = _make_module(monkeypatch, FakeTioneClient(group=_group(authorization=True)))
    _base(authorization_enable=False, _ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service_group"]["AuthorizationEnable"] is False
    assert "diff" in result
    assert fake.group["AuthorizationEnable"] is True
    assert "ModifyModelServiceAuthorization" not in _names(fake)


# ---------------------------------------------------------------------------
# weight drift flows
# ---------------------------------------------------------------------------


def test_weight_drift_updates_and_waits(monkeypatch):
    group = _group(services=[{"ServiceId": "ms-v1", "Weight": 50}, {"ServiceId": "ms-v2", "Weight": 50}])
    fake = _make_module(monkeypatch, FakeTioneClient(group=group))
    _base()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service_group"]["WeightUpdateStatus"] == ""
    weights = result["service_group"]["Services"]
    assert sorted(item["ServiceId"] for item in weights) == ["ms-v1", "ms-v2"]
    assert fake.last_weights_request.ServiceGroupId == GROUP_ID
    assert [item.__dict__["Weight"] for item in fake.last_weights_request.Weights] == [90, 10]
    assert _names(fake) == [
        "DescribeModelServiceGroup",
        "ModifyServiceGroupWeights",
        "DescribeModelServiceGroup",
        "DescribeModelServiceGroup",
    ]


def test_weight_drift_with_wait_disabled_skips_waiter(monkeypatch):
    group = _group(services=[{"ServiceId": "ms-v1", "Weight": 50}, {"ServiceId": "ms-v2", "Weight": 50}])
    fake = _make_module(monkeypatch, FakeTioneClient(group=group))
    _base(wait=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert _names(fake) == [
        "DescribeModelServiceGroup",
        "ModifyServiceGroupWeights",
        "DescribeModelServiceGroup",
    ]


def test_weight_drift_check_mode_is_dry_run(monkeypatch):
    group = _group(services=[{"ServiceId": "ms-v1", "Weight": 50}, {"ServiceId": "ms-v2", "Weight": 50}])
    fake = _make_module(monkeypatch, FakeTioneClient(group=group))
    _base(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["service_group"]["Services"] == NORMALIZED
    assert "ModifyServiceGroupWeights" not in _names(fake)


# ---------------------------------------------------------------------------
# weight waiter failure paths
# ---------------------------------------------------------------------------


def test_weight_update_failed_state_fails(monkeypatch):
    group = _group(services=[{"ServiceId": "ms-v1", "Weight": 50}, {"ServiceId": "ms-v2", "Weight": 50}])
    fake = _make_module(monkeypatch, FakeTioneClient(group=group, weight_result="failed"))
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "weight update failed" in exc.value.args[0]["msg"]


def test_weight_wait_times_out(monkeypatch):
    group = _group(services=[{"ServiceId": "ms-v1", "Weight": 50}, {"ServiceId": "ms-v2", "Weight": 50}])
    fake = _make_module(monkeypatch, FakeTioneClient(group=group, weight_result="stuck"))
    _base(waiter_timeout=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Timed out waiting for resource state" in payload["msg"]
    assert payload["last_state"] == "updating"


# ---------------------------------------------------------------------------
# argument validation and failure paths
# ---------------------------------------------------------------------------


def test_project_id_is_forwarded_to_describe(monkeypatch):
    fake = _make_module(monkeypatch, FakeTioneClient(group=_group()))
    _base(project_id="prj-workspace-1")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert fake.last_group_request.TiProjectId == "prj-workspace-1"


def test_weights_total_must_be_100(monkeypatch):
    fake = _make_module(monkeypatch, FakeTioneClient(group=_group()))
    _base(weights=[{"ServiceId": "ms-v1", "Weight": 50}])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["total"] == 50
    assert fake.calls == []


def test_duplicate_weight_service_ids_fail(monkeypatch):
    fake = _make_module(monkeypatch, FakeTioneClient(group=_group()))
    _base(weights=[{"ServiceId": "ms-v1", "Weight": 50}, {"ServiceId": "ms-v1", "Weight": 50}])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "must be unique" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_missing_weight_service_id_or_value_fails(monkeypatch):
    fake = _make_module(monkeypatch, FakeTioneClient(group=_group()))
    _base(weights=[{"Weight": 100}])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "requires ServiceId and Weight" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_negative_or_non_integer_weights_fail(monkeypatch):
    fake = _make_module(monkeypatch, FakeTioneClient(group=_group()))
    _base(weights=[{"ServiceId": "ms-v1", "Weight": -10}, {"ServiceId": "ms-v2", "Weight": 110}])
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "non-negative integers" in exc.value.args[0]["msg"]
    assert fake.calls == []


def test_missing_service_group_fails(monkeypatch):
    fake = _make_module(monkeypatch, FakeTioneClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "service group does not exist" in payload["msg"]
    assert payload["service_group_id"] == GROUP_ID


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeModelServiceGroup(self, request):
            raise Boom("tione endpoint unreachable")

    fake = _make_module(monkeypatch, ExplodingClient())
    _base()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "tione endpoint unreachable" in payload["error"]


# ---------------------------------------------------------------------------
# legacy helper regression tests (folded from
# test_tione_model_service_traffic.py)
# ---------------------------------------------------------------------------


class _FailingModule(object):
    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


def _legacy_params():
    return {"service_group_id": "g1", "authorization_enable": True, "weights": [{"ServiceId": "s2", "Weight": 10}, {"ServiceId": "s1", "Weight": 90}]}


def test_requests_map_authorization_and_sorted_weights():
    auth = mod.authorization_request(FakeModels(), _legacy_params())
    assert auth.ServiceGroupId == "g1"
    assert auth.AuthorizationEnable is True
    weights = mod.weights_request(FakeModels(), _legacy_params())
    assert weights.ServiceGroupId == "g1"
    assert [item.__dict__["ServiceId"] for item in weights.Weights] == ["s1", "s2"]
    assert weights.Weights[0].__dict__["Weight"] == 90


def test_current_weights_ignores_unrelated_service_fields():
    group = {"Services": [{"ServiceId": "s2", "Weight": 10, "Status": "Normal"}, {"ServiceId": "s1", "Weight": 90}]}
    assert mod.current_weights(group) == mod.normalized_weights(_legacy_params()["weights"])


def test_normalized_weights_sort_and_filter_entries():
    values = [{"ServiceId": "s2", "Weight": 10, "Status": "Normal"}, {"ServiceId": "s1", "Weight": 90}]
    assert mod.normalized_weights(values) == [{"ServiceId": "s1", "Weight": 90}, {"ServiceId": "s2", "Weight": 10}]
    assert mod.normalized_weights(None) == []


def test_validate_weights_accepts_exact_distribution():
    mod.validate_weights(_FailingModule(), _legacy_params()["weights"])
    mod.validate_weights(_FailingModule(), None)


def test_validate_weights_rejects_invalid_totals_and_duplicate_ids():
    for value in (
        [{"ServiceId": "s1", "Weight": 99}],
        [{"ServiceId": "s1", "Weight": 50}, {"ServiceId": "s1", "Weight": 50}],
    ):
        with pytest.raises(AnsibleFailJson):
            mod.validate_weights(_FailingModule(), value)
