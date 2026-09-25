# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for the ssm_rotation_info read module.

The module returns a secret's rotation configuration and, when asked, the
visible recent rotation history. The ``include_history`` gate is the point of
the module, so it is asserted in both directions: the default run must also
call ``DescribeRotationHistory`` and merge that payload under ``history``, and
``include_history=false`` must leave the history action uncalled and the
result without a history key. Both requests carry the same secret name, and
the request id reported is the one from the final call, so the merge order is
pinned too. Around that sit the required ``secret_name`` guard -- which has to
fire before any client is built -- and the SDK failure path, which must
surface the service error instead of a half-populated rotation payload.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from types import SimpleNamespace

from ansible_collections.susunola.tencentcloud.plugins.modules import ssm_rotation_info as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ROTATION = {
    "SecretName": "prod/database",
    "RotationEnabled": True,
    "RotationInterval": 30,
    "RequestId": "req-detail",
}

HISTORY = {
    "SecretName": "prod/database",
    "RotationVersions": ["v3", "v2"],
    "RequestId": "req-history",
}


class FakeSsmClient(object):
    """Records every call and returns canned rotation responses."""

    def __init__(self, rotation=None, history=None):
        self.rotation = dict(rotation if rotation is not None else ROTATION)
        self.history = dict(history if history is not None else HISTORY)
        self.calls = []

    def DescribeRotationDetail(self, request):
        self.calls.append(("DescribeRotationDetail", request))
        return FakeResource(self.rotation)

    def DescribeRotationHistory(self, request):
        self.calls.append(("DescribeRotationHistory", request))
        return FakeResource(self.history)

    def operations(self):
        return [name for name, _request in self.calls]


class MetadataOnlyResponse(object):
    """A response whose serialized payload omits RequestId.

    The module falls back to the response attribute for the request id, so a
    response that only carries it as an attribute still reports one.
    """

    RequestId = "req-attribute"

    def _serialize(self, allow_none=True):
        return {"SecretName": "prod/database", "RotationEnabled": False}


def _wire(monkeypatch, client):
    """Point the module at the fake client and a no-op SDK check."""
    monkeypatch.setattr(mod.TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load",
                        lambda: (FakeModels(), SimpleNamespace(SsmClient=object())))
    monkeypatch.setattr(mod.TencentCloudModule, "create_client",
                        lambda self, cls, endpoint: client)


# ---------------------------------------------------------------------------
# rotation configuration
# ---------------------------------------------------------------------------

def test_rotation_detail_is_returned(monkeypatch):
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database", include_history=False)
    result = run(mod.run_module)

    assert result["changed"] is False
    assert result["rotation"] == {"SecretName": "prod/database",
                                  "RotationEnabled": True,
                                  "RotationInterval": 30}
    assert client.operations() == ["DescribeRotationDetail"]


def test_rotation_detail_request_carries_the_secret_name(monkeypatch):
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database", include_history=False)
    run(mod.run_module)
    name, request = client.calls[0]
    assert name == "DescribeRotationDetail"
    assert request.SecretName == "prod/database"


def test_rotation_request_id_is_lifted_out_of_the_payload(monkeypatch):
    """RequestId is reported as request_id rather than left inside the
    rotation configuration the caller inspects."""
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database", include_history=False)
    result = run(mod.run_module)

    assert result["request_id"] == "req-detail"
    assert "RequestId" not in result["rotation"]


def test_rotation_request_id_falls_back_to_the_response_attribute(monkeypatch):
    client = FakeSsmClient()
    client.DescribeRotationDetail = lambda request: MetadataOnlyResponse()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database", include_history=False)
    result = run(mod.run_module)

    assert result["request_id"] == "req-attribute"
    assert "RequestId" not in result["rotation"]


# ---------------------------------------------------------------------------
# the include_history gate
# ---------------------------------------------------------------------------

def test_history_is_fetched_and_merged_by_default(monkeypatch):
    """include_history defaults to true, so a bare run must issue both reads
    and expose the history payload next to the rotation configuration."""
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database")
    result = run(mod.run_module)

    assert result["changed"] is False
    assert client.operations() == ["DescribeRotationDetail", "DescribeRotationHistory"]
    assert result["history"] == {"SecretName": "prod/database",
                                 "RotationVersions": ["v3", "v2"]}


def test_history_request_carries_the_secret_name(monkeypatch):
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database")
    run(mod.run_module)
    assert [request.SecretName for _name, request in client.calls] == \
        ["prod/database", "prod/database"]


def test_history_request_id_wins_over_the_rotation_request_id(monkeypatch):
    """request_id is documented as the id of the final API call, so the
    history read replaces the detail read's id and lifts its own RequestId
    out of the history payload."""
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database")
    result = run(mod.run_module)

    assert result["request_id"] == "req-history"
    assert "RequestId" not in result["history"]


def test_history_is_not_fetched_when_disabled(monkeypatch):
    """include_history=false must leave DescribeRotationHistory uncalled and
    keep the history key out of the result entirely."""
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database", include_history=False)
    result = run(mod.run_module)

    assert client.operations() == ["DescribeRotationDetail"]
    assert "history" not in result
    assert result["request_id"] == "req-detail"


def test_reads_still_happen_in_check_mode(monkeypatch):
    """check_mode is supported: a read still returns the current state."""
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database", _ansible_check_mode=True)
    result = run(mod.run_module)

    assert result["changed"] is False
    assert client.operations() == ["DescribeRotationDetail", "DescribeRotationHistory"]


# ---------------------------------------------------------------------------
# guard rails
# ---------------------------------------------------------------------------

def test_secret_name_is_required(monkeypatch):
    client = FakeSsmClient()
    _wire(monkeypatch, client)
    module_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "secret_name" in exc.value.args[0]["msg"]
    assert client.calls == []


# ---------------------------------------------------------------------------
# failures
# ---------------------------------------------------------------------------

def test_rotation_detail_sdk_error_is_surfaced(monkeypatch):
    client = FakeSsmClient()

    def boom(request):
        raise RuntimeError("AuthFailure.SignatureExpire")

    client.DescribeRotationDetail = boom
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["failed"] is True
    assert "AuthFailure.SignatureExpire" in str(payload)
    assert "rotation" not in payload
    assert "history" not in payload


def test_history_sdk_error_is_surfaced(monkeypatch):
    """A failure on the second read fails the run rather than returning the
    rotation configuration as if the requested history had been included."""
    client = FakeSsmClient()

    def boom(request):
        raise RuntimeError("RequestLimitExceeded")

    client.DescribeRotationHistory = boom
    _wire(monkeypatch, client)
    module_args(secret_name="prod/database")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["failed"] is True
    assert "RequestLimitExceeded" in str(payload)
    assert "rotation" not in payload


# ---------------------------------------------------------------------------
# request builder
# ---------------------------------------------------------------------------

def test_request_sets_the_secret_name():
    request = mod.request(FakeModels().DescribeRotationDetailRequest, "prod/database")
    assert request.SecretName == "prod/database"
