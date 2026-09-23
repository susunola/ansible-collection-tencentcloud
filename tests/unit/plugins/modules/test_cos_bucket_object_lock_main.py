"""Unit tests for the cos_bucket_object_lock write module (run_module flows).

Drives ``run_module()`` against an in-memory fake COS client whose
``put_bucket_object_lock`` mutates the object-lock store so the post-write
``get_bucket_object_lock`` refetch converges immediately.

Scenario matrix:

* present when object lock is disabled (enablement happy path, check mode)
* no-op when the current configuration already matches
* drift updates (retention mode / period)
* absent when no lock exists (idempotent no-op) and the irreversible
  object-lock guard when one does
* validation guards (mode/period pairing, mutually exclusive days/years,
  non-positive periods, state=absent without a lock)
* the COS SDK failure envelope
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import cos_bucket_object_lock as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

APPID = "1300000000"
FULL_NAME = "audit-archive-{0}".format(APPID)


class FakeCosError(Exception):
    """Stand-in for qcloud_cos CosServiceError (404 here means "no lock")."""

    def __init__(self, code, status=404, request_id="req-fake"):
        super(FakeCosError, self).__init__(code)
        self._code = code
        self._status = status
        self._request_id = request_id

    def get_error_code(self):
        return self._code

    def get_status_code(self):
        return self._status

    def get_request_id(self):
        return self._request_id


def _config(enabled="Enabled", mode="COMPLIANCE", days=None, years=None):
    retention = {"Mode": mode}
    if days is not None:
        retention["Days"] = str(days)
    if years is not None:
        retention["Years"] = str(years)
    return {"ObjectLockEnabled": enabled, "Rule": {"DefaultRetention": retention}}


class FakeCosClient(object):
    """In-memory CosS3Client stand-in for object-lock sub-resources."""

    def __init__(self, config=None, raise_on_get=None):
        self.config = copy.deepcopy(config)
        self.raise_on_get = raise_on_get
        self.calls = []

    def _record(self, name, **kwargs):
        self.calls.append((name, kwargs))

    def get_bucket_object_lock(self, Bucket, **kwargs):
        self._record("get_bucket_object_lock", Bucket=Bucket, **kwargs)
        if self.raise_on_get is not None:
            raise self.raise_on_get
        if self.config is None:
            raise FakeCosError("NoSuchObjectLockConfiguration")
        return {"ObjectLockConfiguration": copy.deepcopy(self.config)}

    def put_bucket_object_lock(self, Bucket, ObjectLockConfiguration, **kwargs):
        self._record("put_bucket_object_lock", Bucket=Bucket, ObjectLockConfiguration=ObjectLockConfiguration)
        self.config = copy.deepcopy(ObjectLockConfiguration)
        return {}


def _base(**overrides):
    params = {"name": "audit-archive", "appid": APPID}
    params.update(overrides)
    return module_args(**params)


@pytest.fixture
def client(monkeypatch):
    fake = FakeCosClient()
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: fake)
    return fake


# ---------------------------------------------------------------------------
# present flows
# ---------------------------------------------------------------------------


def test_enable_object_lock(client):
    _base(state="present", retention_mode="COMPLIANCE", retention_years=7)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["object_lock"] == {
        "ObjectLockEnabled": "Enabled",
        "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Years": 7}},
    }
    assert client.config["ObjectLockEnabled"] == "Enabled"
    assert client.calls[-1][0] == "put_bucket_object_lock"


def test_enable_check_mode_is_dry_run(client):
    _base(
        _ansible_check_mode=True,
        state="present",
        retention_mode="GOVERNANCE",
        retention_days=30,
    )
    result = run(mod.run_module)
    assert result["changed"] is True
    assert "diff" in result
    assert client.config is None
    assert [c for c, kwargs in client.calls] == ["get_bucket_object_lock"]


def test_matching_config_is_idempotent(client):
    client.config = _config(mode="GOVERNANCE", days=30)
    _base(state="present", retention_mode="GOVERNANCE", retention_days=30)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["object_lock"]["Rule"]["DefaultRetention"]["Days"] == 30
    assert [c for c, kwargs in client.calls] == ["get_bucket_object_lock"]


def test_retention_mode_drift_updates(client):
    client.config = _config(mode="GOVERNANCE", days=30)
    _base(state="present", retention_mode="COMPLIANCE", retention_days=30)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["object_lock"]["Rule"]["DefaultRetention"]["Mode"] == "COMPLIANCE"


def test_retention_period_drift_updates(client):
    client.config = _config(mode="COMPLIANCE", days=30)
    _base(state="present", retention_mode="COMPLIANCE", retention_days=60)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["object_lock"]["Rule"]["DefaultRetention"]["Days"] == 60


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_without_lock_is_idempotent(client):
    _base(state="absent")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["object_lock"] is None
    assert [c for c, kwargs in client.calls] == ["get_bucket_object_lock"]


def test_absent_with_lock_is_irreversible(client):
    client.config = _config(mode="COMPLIANCE", years=7)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert "irreversible" in payload["msg"]
    assert payload["object_lock"]["ObjectLockEnabled"] == "Enabled"


# ---------------------------------------------------------------------------
# validation guards
# ---------------------------------------------------------------------------


def test_mode_without_period_fails(client):
    _base(state="present", retention_mode="COMPLIANCE")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "retention_mode and exactly one retention period" in exc.value.args[0]["msg"]


def test_period_without_mode_fails(client):
    _base(state="present", retention_days=30)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "retention_mode and exactly one retention period" in exc.value.args[0]["msg"]


def test_days_and_years_are_mutually_exclusive(client):
    _base(state="present", retention_mode="COMPLIANCE", retention_days=30, retention_years=1)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "mutually exclusive" in exc.value.args[0]["msg"]


def test_non_positive_period_fails(client):
    _base(state="present", retention_mode="COMPLIANCE", retention_days=0)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "retention period must be positive" in exc.value.args[0]["msg"]


def test_negative_year_period_fails(client):
    _base(state="present", retention_mode="COMPLIANCE", retention_years=-1)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "retention period must be positive" in exc.value.args[0]["msg"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_cos_error_maps_to_failure_payload(client):
    client.raise_on_get = FakeCosError("InternalFailure", status=500)
    _base(state="present", retention_mode="COMPLIANCE", retention_years=7)
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud COS request failed"
    assert payload["error_code"] == "InternalFailure"
