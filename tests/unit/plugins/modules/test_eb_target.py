"""Unit tests for the eb_target write module (helpers + run_module).

Creates, updates and destroys EventBridge rule targets. Lookup lists the
rule's targets and filters by ``target_id`` or by ``type`` +
``target_description`` (dict-to-dict equality); multiple matches fail.
``Type`` and ``TargetDescription`` are immutable after creation
(require_immutable_unchanged), while the batch-delivery knobs are the
only updatable fields — ``update_request`` carries exactly those three.
``create_request`` builds the nested SDK ``TargetDescription`` through
``cls().from_json_string(...)``, so the models stand-in exposes a real
``from_json_string`` that keeps the parsed payload readable by the fake
client.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import eb_target as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

TARGET_DESCRIPTION = {"ResourceDescription": '{"Region":"ap-guangzhou","FunctionName":"consume"}'}


class _TargetDescription(object):
    """SDK TargetDescription stand-in with a working from_json_string."""

    def __init__(self):
        self.raw = None

    def from_json_string(self, text):
        self.raw = json.loads(text)


class _EbModels(object):
    """Models stand-in whose TargetDescription supports from_json_string."""

    def __getattr__(self, name):
        if name == "TargetDescription":
            return _TargetDescription
        return type(name, (object,), {})


def _target(**overrides):
    """API-shaped target dict isolated from the shared constant."""
    item = {
        "TargetId": "tgt-1",
        "Type": "scf",
        "TargetDescription": dict(TARGET_DESCRIPTION),
        "EnableBatchDelivery": None,
        "BatchTimeout": None,
        "BatchEventCount": None,
    }
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "state": "present",
        "event_bus_id": "eb-1",
        "rule_id": "rule-1",
        "target_id": None,
        "target_type": "scf",
        "target_description": dict(TARGET_DESCRIPTION),
        "enable_batch_delivery": None,
        "batch_timeout": None,
        "batch_event_count": None,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every non-None module parameter."""
    return module_args(**{k: v for k, v in _params(**extra).items() if v is not None})


class FakeModule(object):
    """Minimal stand-in for helpers that need sdk_call / fail_json."""

    def __init__(self, params=None):
        self.params = params or _params()
        self.sdk_calls = []

    def sdk_call(self, operation, request):
        self.sdk_calls.append((operation, request))
        return operation(request)

    def fail_json(self, **kwargs):
        raise AnsibleFailJson(kwargs)


class FakeEbClient(object):
    """In-memory EbClient stand-in storing target dicts per rule.

    ListTargets returns every stored target for the bus/rule as
    :class:`FakeResource` items (the module applies its own identity
    filter). CreateTarget synthesises a TargetId and stores the raw
    ``TargetDescription`` read from the request model; UpdateTarget only
    touches the batch-delivery knobs, mirroring the module's update
    request.
    """

    def __init__(self, targets=None):
        self.targets = [copy.deepcopy(t) for t in (targets or [])]
        self.calls = []
        self._next_id = 100

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def ListTargets(self, request):
        self._record("ListTargets", request)
        items = [
            t for t in self.targets
            if t.get("EventBusId") == request.EventBusId or t.get("EventBusId") is None
        ]
        return SimpleNamespace(Targets=[FakeResource(dict(t)) for t in items], RequestId="req-fake")

    def CreateTarget(self, request):
        self._record("CreateTarget", request)
        target_id = "tgt-new%d" % self._next_id
        self._next_id += 1
        self.targets.append(
            {
                "EventBusId": request.EventBusId,
                "RuleId": request.RuleId,
                "TargetId": target_id,
                "Type": request.Type,
                "TargetDescription": request.TargetDescription.raw,
                "EnableBatchDelivery": request.EnableBatchDelivery,
                "BatchTimeout": request.BatchTimeout,
                "BatchEventCount": request.BatchEventCount,
            }
        )
        return SimpleNamespace(TargetId=target_id, RequestId="req-fake")

    def UpdateTarget(self, request):
        self._record("UpdateTarget", request)
        # SDK semantics: a None field is not sent, so it stays unchanged.
        for stored in self.targets:
            if stored.get("TargetId") == request.TargetId:
                if request.EnableBatchDelivery is not None:
                    stored["EnableBatchDelivery"] = request.EnableBatchDelivery
                if request.BatchTimeout is not None:
                    stored["BatchTimeout"] = request.BatchTimeout
                if request.BatchEventCount is not None:
                    stored["BatchEventCount"] = request.BatchEventCount
        return SimpleNamespace(RequestId="req-fake")

    def DeleteTarget(self, request):
        self._record("DeleteTarget", request)
        self.targets = [t for t in self.targets if t.get("TargetId") != request.TargetId]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (_EbModels(), SimpleNamespace(EbClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


class _BoomClient(object):
    """Every SDK call raises, so the module's wrapped error path is hit."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise RuntimeError("service exploded")

        return boom


# ---------------------------------------------------------------------------
# request-builder / helper tests
# ---------------------------------------------------------------------------


def test_model_none_returns_none():
    assert mod._model(_TargetDescription, None) is None


def test_model_populates_from_json():
    value = mod._model(_TargetDescription, {"ResourceDescription": "scf://fn"})
    assert value.raw == {"ResourceDescription": "scf://fn"}


def test_list_request_fields():
    request = mod.list_request(FakeModels(), _params())
    assert request.EventBusId == "eb-1"
    assert request.RuleId == "rule-1"
    assert request.Offset == 0
    assert request.Limit == 100


def test_create_request_maps_fields():
    request = mod.create_request(
        _EbModels(),
        _params(enable_batch_delivery=True, batch_timeout=20, batch_event_count=10),
    )
    assert request.EventBusId == "eb-1"
    assert request.RuleId == "rule-1"
    assert request.Type == "scf"
    assert request.TargetDescription.raw == TARGET_DESCRIPTION
    assert request.EnableBatchDelivery is True
    assert request.BatchTimeout == 20
    assert request.BatchEventCount == 10


def test_update_request_carries_only_batch_fields():
    request = mod.update_request(FakeModels(), _params(enable_batch_delivery=True, batch_timeout=15), "tgt-9")
    assert request.EventBusId == "eb-1"
    assert request.RuleId == "rule-1"
    assert request.TargetId == "tgt-9"
    assert request.EnableBatchDelivery is True
    assert request.BatchTimeout == 15
    assert request.BatchEventCount is None
    assert not hasattr(request, "Type")
    assert not hasattr(request, "TargetDescription")


def test_delete_request_fields():
    request = mod.delete_request(FakeModels(), _params(), "tgt-9")
    assert request.EventBusId == "eb-1"
    assert request.RuleId == "rule-1"
    assert request.TargetId == "tgt-9"


# ---------------------------------------------------------------------------
# find tests
# ---------------------------------------------------------------------------


def test_find_matches_by_target_id(monkeypatch):
    fake = FakeEbClient([_target(TargetId="tgt-1", Type="ckafka"), _target(TargetId="tgt-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(target_id="tgt-2"))
    value = mod.find(module, fake, _EbModels(), module.params)
    assert value["TargetId"] == "tgt-2"


def test_find_matches_by_type_and_description(monkeypatch):
    fake = FakeEbClient([_target(Type="ckafka", TargetDescription={"ResourceDescription": "other"}), _target()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(target_id=None))
    value = mod.find(module, fake, _EbModels(), module.params)
    assert value["TargetId"] == "tgt-1"


def test_find_no_match_returns_none(monkeypatch):
    fake = FakeEbClient([_target()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(target_id=None, target_type="ckafka", target_description={"ResourceDescription": "other"}))
    assert mod.find(module, fake, _EbModels(), module.params) is None


def test_find_without_identity_returns_none(monkeypatch):
    fake = FakeEbClient([_target()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(target_id=None, target_type=None, target_description=None))
    assert mod.find(module, fake, _EbModels(), module.params) is None


def test_find_type_only_returns_none(monkeypatch):
    fake = FakeEbClient([_target()])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(target_id=None, target_description=None))
    assert mod.find(module, fake, _EbModels(), module.params) is None


def test_find_multiple_matches_fails(monkeypatch):
    fake = FakeEbClient([_target(), _target(TargetId="tgt-2")])
    _make_module(monkeypatch, fake)
    module = FakeModule(_params(target_id=None))
    with pytest.raises(AnsibleFailJson) as exc:
        mod.find(module, fake, _EbModels(), module.params)
    assert "Multiple EventBridge targets matched" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_requires_target_id_or_type():
    module_args(state="present", event_bus_id="eb-1", rule_id="rule-1")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    msg = exc.value.args[0]["msg"]
    assert "target_id" in msg and "target_type" in msg


def test_present_creates_target(monkeypatch):
    fake = FakeEbClient()
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    target = result["target"]
    assert target["TargetId"] == "tgt-new100"
    assert target["Type"] == "scf"
    assert target["TargetDescription"] == TARGET_DESCRIPTION
    assert [c[0] for c in fake.calls].count("ListTargets") == 2  # find + refetch
    assert [c[0] for c in fake.calls].count("CreateTarget") == 1
    create = [c for c in fake.calls if c[0] == "CreateTarget"][0][1]
    assert create.TargetDescription.raw == TARGET_DESCRIPTION


def test_present_creation_parameters_missing_fails(monkeypatch):
    fake = FakeEbClient()
    _make_module(monkeypatch, fake)
    _run_args(target_id="ghost", target_type=None, target_description=None)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "creation parameters are required" in payload["msg"]
    assert sorted(payload["missing"]) == ["target_description", "target_type"]


def test_present_check_mode_create_is_dry_run(monkeypatch):
    fake = FakeEbClient()
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["target"] == {
        "Type": "scf",
        "TargetDescription": TARGET_DESCRIPTION,
        "EnableBatchDelivery": None,
        "BatchTimeout": None,
        "BatchEventCount": None,
    }
    assert not any(c[0] == "CreateTarget" for c in fake.calls)


def test_present_noop_returns_unchanged(monkeypatch):
    fake = FakeEbClient([_target()])
    _make_module(monkeypatch, fake)
    _run_args(target_id="tgt-1")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["target"]["TargetId"] == "tgt-1"
    assert not any(c[0] in ("CreateTarget", "UpdateTarget", "DeleteTarget") for c in fake.calls)


def test_present_batch_drift_triggers_update(monkeypatch):
    fake = FakeEbClient([_target(EnableBatchDelivery=True, BatchTimeout=10, BatchEventCount=5)])
    _make_module(monkeypatch, fake)
    _run_args(target_id="tgt-1", batch_timeout=30)
    result = run(mod.run_module)
    assert result["changed"] is True
    target = result["target"]
    assert target["BatchTimeout"] == 30
    assert target["EnableBatchDelivery"] is True  # untouched, kept from current
    update = [c for c in fake.calls if c[0] == "UpdateTarget"][0][1]
    assert update.TargetId == "tgt-1"
    assert update.BatchTimeout == 30
    assert not hasattr(update, "Type")
    assert "CreateTarget" not in [c[0] for c in fake.calls]


def test_present_type_immutable_fails(monkeypatch):
    fake = FakeEbClient([_target()])
    _make_module(monkeypatch, fake)
    _run_args(target_id="tgt-1", target_type="ckafka")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "Immutable fields cannot be changed" in payload["msg"]
    assert payload["replacement_required"] is True
    assert payload["immutable_changes"] == {"Type": {"before": "scf", "after": "ckafka"}}
    assert not any(c[0] == "UpdateTarget" for c in fake.calls)


def test_present_target_description_immutable_fails(monkeypatch):
    fake = FakeEbClient([_target()])
    _make_module(monkeypatch, fake)
    _run_args(target_id="tgt-1", target_description={"ResourceDescription": "other"})
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["immutable_changes"] == {
        "TargetDescription": {"before": TARGET_DESCRIPTION, "after": {"ResourceDescription": "other"}}
    }


def test_check_mode_update_is_dry_run(monkeypatch):
    fake = FakeEbClient([_target(BatchTimeout=10)])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(target_id="tgt-1", batch_timeout=30).items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["target"]["BatchTimeout"] == 10  # pre-change reported
    assert not any(c[0] == "UpdateTarget" for c in fake.calls)


def test_absent_not_found_is_noop(monkeypatch):
    fake = FakeEbClient([_target()])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", target_id="ghost")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["target"] is None
    assert not any(c[0] == "DeleteTarget" for c in fake.calls)


def test_absent_deletes_target(monkeypatch):
    fake = FakeEbClient([_target(), _target(TargetId="tgt-2")])
    _make_module(monkeypatch, fake)
    _run_args(state="absent", target_id="tgt-1")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["target"] is None
    delete = [c for c in fake.calls if c[0] == "DeleteTarget"][0][1]
    assert delete.TargetId == "tgt-1"
    assert [t["TargetId"] for t in fake.targets] == ["tgt-2"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeEbClient([_target()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params(state="absent", target_id="tgt-1").items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["target"] is None  # absent always reports None
    assert not any(c[0] == "DeleteTarget" for c in fake.calls)
    assert len(fake.targets) == 1


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (_EbModels(), SimpleNamespace(EbClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule,
        "create_client",
        lambda self, client_class, endpoint: _BoomClient(),
    )
    _run_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert payload["error"] == "service exploded"
