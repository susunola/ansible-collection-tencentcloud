"""Unit tests for the cloudaudit_audit write module (helpers + run_module).

Covers the reconcile-only flow of ``plugins/modules/cloudaudit_audit.py``
with an in-memory fake CloudAudit client whose write operations mutate the
stored audit, so the module's post-write ``find_audit`` refetch converges
immediately. The audit is located by name through a single ``DescribeAudit``
call; configuration drift over the compared keys is applied with
``UpdateAudit`` while the running state is reconciled separately through
``StartLogging``/``StopLogging``, so a pause-only change never sends an
update. The module has no ``state`` parameter — it always reconciles an
existing named audit. In check mode a would-be change reports the pre-change
audit and never writes.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cloudaudit_audit as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

AUDIT = {
    "AuditName": "default",
    "AuditStatus": "1",
    "ReadWriteAttribute": 3,
    "CosRegion": "ap-guangzhou",
    "CosBucketName": "audit-logs-1250000000",
    "IsCreateNewBucket": 0,
    "LogFilePrefix": "CloudAudit",
    "IsEnableCmqNotify": 0,
    "CmqRegion": None,
    "CmqQueueName": None,
    "IsCreateNewQueue": 0,
    "IsEnableKmsEncry": 0,
    "KmsRegion": None,
    "KeyId": None,
    "RequestId": "req-fake",
}


def _audit(**overrides):
    """API-shaped audit dict isolated from the shared constant."""
    item = copy.deepcopy(AUDIT)
    item.update(overrides)
    return item


def _params(**overrides):
    """Module parameters pre-filled from the argument spec defaults."""
    params = {
        "audit_name": "default",
        "enabled": True,
        "read_write_attribute": 3,
        "cos_region": "ap-guangzhou",
        "cos_bucket_name": "audit-logs-1250000000",
        "create_new_bucket": False,
        "log_file_prefix": "CloudAudit",
        "cmq_notify": False,
        "cmq_region": None,
        "cmq_queue_name": None,
        "create_new_queue": False,
        "kms_encryption": False,
        "kms_region": None,
        "key_id": None,
    }
    params.update(overrides)
    return params


def _run_args(**extra):
    """module_args() pre-filled with every module parameter (None dropped)."""
    args = dict(_params())
    args.update(extra)
    return module_args(**{k: v for k, v in args.items() if v is not None})


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


class FakeCloudAuditClient(object):
    """In-memory CloudAuditClient stand-in for one named audit.

    ``DescribeAudit`` returns the stored audit (with its top-level
    RequestId, which the module strips); ``UpdateAudit`` applies the
    mutable configuration fields and ``StartLogging``/``StopLogging`` flip
    ``AuditStatus`` so post-write refetches converge.
    """

    def __init__(self, audit=None):
        self.audit = copy.deepcopy(audit) if audit is not None else None
        self.calls = []

    def _record(self, name, request):
        self.calls.append((name, request))
        return request

    def DescribeAudit(self, request):
        self._record("DescribeAudit", request)
        return FakeResource(dict(self.audit or {}))

    def UpdateAudit(self, request):
        self._record("UpdateAudit", request)
        self.audit["ReadWriteAttribute"] = request.ReadWriteAttribute
        self.audit["CosRegion"] = request.CosRegion
        self.audit["CosBucketName"] = request.CosBucketName
        self.audit["IsCreateNewBucket"] = request.IsCreateNewBucket
        self.audit["LogFilePrefix"] = request.LogFilePrefix
        self.audit["IsEnableCmqNotify"] = request.IsEnableCmqNotify
        self.audit["IsCreateNewQueue"] = request.IsCreateNewQueue
        self.audit["IsEnableKmsEncry"] = request.IsEnableKmsEncry
        for name in ("CmqRegion", "CmqQueueName", "KmsRegion", "KeyId"):
            if hasattr(request, name):
                self.audit[name] = getattr(request, name)
        return SimpleNamespace(RequestId="req-fake")

    def StartLogging(self, request):
        self._record("StartLogging", request)
        self.audit["AuditStatus"] = "1"
        return SimpleNamespace(RequestId="req-fake")

    def StopLogging(self, request):
        self._record("StopLogging", request)
        self.audit["AuditStatus"] = "0"
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake):
    """Wire the shared monkeypatches and return the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(CloudauditClient=object)),
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
# request-builder / normalisation helper tests
# ---------------------------------------------------------------------------


def test_describe_request_sets_audit_name():
    request = mod.describe_request(FakeModels(), "default")
    assert request.AuditName == "default"


def test_update_request_maps_core_fields():
    request = mod.update_request(FakeModels(), _params())
    assert request.AuditName == "default"
    assert request.ReadWriteAttribute == 3
    assert request.CosRegion == "ap-guangzhou"
    assert request.CosBucketName == "audit-logs-1250000000"
    assert request.LogFilePrefix == "CloudAudit"


def test_update_request_coerces_booleans_to_int():
    request = mod.update_request(
        FakeModels(),
        _params(create_new_bucket=True, cmq_notify=True, create_new_queue=True, kms_encryption=True),
    )
    assert request.IsCreateNewBucket == 1
    assert request.IsEnableCmqNotify == 1
    assert request.IsCreateNewQueue == 1
    assert request.IsEnableKmsEncry == 1


def test_update_request_sets_optional_fields_when_given():
    request = mod.update_request(
        FakeModels(),
        _params(cmq_notify=True, cmq_region="ap-shanghai", cmq_queue_name="queue-audit", kms_encryption=True, kms_region="ap-shanghai", key_id="key-abc"),
    )
    assert request.CmqRegion == "ap-shanghai"
    assert request.CmqQueueName == "queue-audit"
    assert request.KmsRegion == "ap-shanghai"
    assert request.KeyId == "key-abc"


def test_update_request_omits_unset_optional_fields():
    request = mod.update_request(FakeModels(), _params())
    assert not hasattr(request, "CmqRegion")
    assert not hasattr(request, "CmqQueueName")
    assert not hasattr(request, "KmsRegion")
    assert not hasattr(request, "KeyId")


def test_start_request_fields():
    request = mod.start_request(FakeModels(), "default")
    assert request.AuditName == "default"


def test_stop_request_fields():
    request = mod.stop_request(FakeModels(), "default")
    assert request.AuditName == "default"


def test_desired_maps_params():
    target = mod.desired(_params())
    assert target["AuditName"] == "default"
    assert target["ReadWriteAttribute"] == 3
    assert target["CosRegion"] == "ap-guangzhou"
    assert target["CosBucketName"] == "audit-logs-1250000000"
    assert target["LogFilePrefix"] == "CloudAudit"
    assert target["IsEnableCmqNotify"] == 0
    assert target["IsEnableKmsEncry"] == 0


def test_desired_coerces_booleans_to_int():
    target = mod.desired(_params(cmq_notify=True, kms_encryption=True))
    assert target["IsEnableCmqNotify"] == 1
    assert target["IsEnableKmsEncry"] == 1


def test_desired_includes_optional_fields_when_set():
    target = mod.desired(_params(cmq_notify=True, cmq_region="ap-shanghai", cmq_queue_name="queue-audit",
                                 kms_encryption=True, kms_region="ap-shanghai", key_id="key-abc"))
    assert target["CmqRegion"] == "ap-shanghai"
    assert target["CmqQueueName"] == "queue-audit"
    assert target["KmsRegion"] == "ap-shanghai"
    assert target["KeyId"] == "key-abc"


def test_desired_omits_optional_fields_when_unset():
    target = mod.desired(_params())
    assert "CmqRegion" not in target
    assert "CmqQueueName" not in target
    assert "KmsRegion" not in target
    assert "KeyId" not in target


def test_find_audit_returns_serialized_audit(monkeypatch):
    fake = FakeCloudAuditClient(_audit())
    _make_module(monkeypatch, fake)
    module = FakeModule()
    value = mod.find_audit(module, fake, FakeModels(), "default")
    assert value["AuditName"] == "default"
    assert value["AuditStatus"] == "1"
    assert "RequestId" not in value  # stripped by find_audit


# ---------------------------------------------------------------------------
# run_module main-path tests
# ---------------------------------------------------------------------------


def test_cmq_notify_requires_region_and_queue():
    module_args(audit_name="default", cos_region="ap-guangzhou", cos_bucket_name="b", cmq_notify=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "cmq_region and cmq_queue_name are required when cmq_notify=true"


def test_kms_encryption_requires_region():
    module_args(audit_name="default", cos_region="ap-guangzhou", cos_bucket_name="b", kms_encryption=True)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert exc.value.args[0]["msg"] == "kms_region is required when kms_encryption=true"


def test_noop_returns_unchanged(monkeypatch):
    fake = FakeCloudAuditClient(_audit())
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["audit"]["AuditName"] == "default"
    assert result["audit"]["AuditStatus"] == "1"
    assert [c[0] for c in fake.calls] == ["DescribeAudit"]


def test_stopped_audit_with_disabled_param_is_noop(monkeypatch):
    fake = FakeCloudAuditClient(_audit(AuditStatus="0"))
    _make_module(monkeypatch, fake)
    _run_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert [c[0] for c in fake.calls] == ["DescribeAudit"]


@pytest.mark.parametrize("status", ["1", "true", "running", "enable", "enabled", "ENABLED"])
def test_running_status_aliases_count_as_running(monkeypatch, status):
    # every accepted AuditStatus spelling with enabled=True is a no-op
    fake = FakeCloudAuditClient(_audit(AuditStatus=status))
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert [c[0] for c in fake.calls] == ["DescribeAudit"]


def test_config_drift_triggers_update_only(monkeypatch):
    fake = FakeCloudAuditClient(_audit(CosBucketName="audit-logs-old"))
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["audit"]["CosBucketName"] == "audit-logs-1250000000"
    names = [c[0] for c in fake.calls]
    assert names.count("DescribeAudit") == 2  # find + refetch
    assert names.count("UpdateAudit") == 1
    assert "StartLogging" not in names
    assert "StopLogging" not in names
    update = [c for c in fake.calls if c[0] == "UpdateAudit"][0][1]
    assert update.CosBucketName == "audit-logs-1250000000"


def test_create_bucket_flag_alone_is_not_drift(monkeypatch):
    # IsCreateNewBucket is a create-time hint, not a compared field
    fake = FakeCloudAuditClient(_audit())
    _make_module(monkeypatch, fake)
    _run_args(create_new_bucket=True)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert [c[0] for c in fake.calls] == ["DescribeAudit"]


def test_read_write_attribute_drift_triggers_update(monkeypatch):
    fake = FakeCloudAuditClient(_audit(ReadWriteAttribute=1))
    _make_module(monkeypatch, fake)
    _run_args(read_write_attribute=2)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["audit"]["ReadWriteAttribute"] == 2
    update = [c for c in fake.calls if c[0] == "UpdateAudit"][0][1]
    assert update.ReadWriteAttribute == 2


def test_stopped_audit_starts_logging(monkeypatch):
    fake = FakeCloudAuditClient(_audit(AuditStatus="0"))
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["audit"]["AuditStatus"] == "1"
    names = [c[0] for c in fake.calls]
    assert names.count("StartLogging") == 1
    assert "UpdateAudit" not in names
    assert "StopLogging" not in names
    start = [c for c in fake.calls if c[0] == "StartLogging"][0][1]
    assert start.AuditName == "default"


def test_running_audit_stops_logging(monkeypatch):
    fake = FakeCloudAuditClient(_audit())
    _make_module(monkeypatch, fake)
    _run_args(enabled=False)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["audit"]["AuditStatus"] == "0"
    names = [c[0] for c in fake.calls]
    assert names.count("StopLogging") == 1
    assert "UpdateAudit" not in names
    stop = [c for c in fake.calls if c[0] == "StopLogging"][0][1]
    assert stop.AuditName == "default"


def test_config_and_state_drift_apply_update_then_logging(monkeypatch):
    fake = FakeCloudAuditClient(_audit(CosBucketName="audit-logs-old", AuditStatus="0"))
    _make_module(monkeypatch, fake)
    _run_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["audit"]["CosBucketName"] == "audit-logs-1250000000"
    assert result["audit"]["AuditStatus"] == "1"
    names = [c[0] for c in fake.calls]
    assert names == ["DescribeAudit", "UpdateAudit", "StartLogging", "DescribeAudit"]


def test_cmq_and_kms_enablement_drift(monkeypatch):
    fake = FakeCloudAuditClient(_audit())
    _make_module(monkeypatch, fake)
    _run_args(cmq_notify=True, cmq_region="ap-shanghai", cmq_queue_name="queue-audit", kms_encryption=True, kms_region="ap-shanghai", key_id="key-abc")
    result = run(mod.run_module)
    assert result["changed"] is True
    audit = result["audit"]
    assert audit["IsEnableCmqNotify"] == 1
    assert audit["CmqQueueName"] == "queue-audit"
    assert audit["IsEnableKmsEncry"] == 1
    assert audit["KeyId"] == "key-abc"
    update = [c for c in fake.calls if c[0] == "UpdateAudit"][0][1]
    assert update.IsEnableCmqNotify == 1
    assert update.CmqRegion == "ap-shanghai"
    assert update.IsEnableKmsEncry == 1
    assert update.KeyId == "key-abc"


def test_check_mode_config_drift_is_dry_run(monkeypatch):
    fake = FakeCloudAuditClient(_audit(CosBucketName="audit-logs-old"))
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["audit"]["CosBucketName"] == "audit-logs-old"  # pre-change audit
    assert [c[0] for c in fake.calls] == ["DescribeAudit"]
    assert not any("UpdateAudit" == c[0] for c in fake.calls)


def test_check_mode_state_drift_is_dry_run(monkeypatch):
    fake = FakeCloudAuditClient(_audit(AuditStatus="0"))
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, **{k: v for k, v in _params().items() if v is not None})
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["audit"]["AuditStatus"] == "0"  # pre-change audit
    assert not any("StartLogging" == c[0] for c in fake.calls)
    assert not any("StopLogging" == c[0] for c in fake.calls)


def test_sdk_error_is_reported(monkeypatch):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        mod,
        "_load",
        lambda: (FakeModels(), SimpleNamespace(CloudauditClient=object)),
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
