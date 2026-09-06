from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.module_utils import lifecycle


class FakeModule:
    def fail_json(self, **kwargs):
        raise RuntimeError(kwargs)


class FakeError(Exception):
    def get_code(self):
        return "InvalidParameter"

    def get_request_id(self):
        return "req-1"


def test_immutable_changes_only_reports_differences():
    assert lifecycle.immutable_changes({"Size": 1, "Name": "a"}, {"Size": 2, "Name": "a"}, ("Size", "Name")) == {
        "Size": {"before": 1, "after": 2}
    }


def test_require_immutable_unchanged_fails_with_replacement_contract():
    try:
        lifecycle.require_immutable_unchanged(FakeModule(), {"Size": 1}, {"Size": 2}, ("Size",), "queue")
    except RuntimeError as exc:
        assert exc.args[0]["replacement_required"] is True
    else:
        raise AssertionError("expected immutable field failure")


def test_sdk_error_payload_preserves_diagnostics():
    payload = lifecycle.sdk_error_payload(FakeError("bad"))
    assert payload["error_code"] == "InvalidParameter"
    assert payload["request_id"] == "req-1"


class NotFoundError(Exception):
    def get_code(self):
        return "ResourceNotFound"

    def get_request_id(self):
        return "req-2"


class LeakedSecretError(Exception):
    """An SDK error that happens to carry a credential in its message."""

    def __str__(self):
        return "call failed with secretId=AKIDDUMMYVALUE not authorised"

    def get_code(self):
        return "AuthFailure.SecretIdNotFound"

    def get_request_id(self):
        return "req-3"


def test_error_envelope_classifies_and_names_the_operation():
    payload = lifecycle.error_envelope(FakeError("bad"), operation="DescribeVpcs")
    assert payload["error_kind"] == "other"
    assert payload["operation"] == "DescribeVpcs"
    assert payload["msg"] == "Tencent Cloud API request failed during DescribeVpcs"


def test_error_envelope_redacts_credentials():
    payload = lifecycle.error_envelope(LeakedSecretError(), operation="DescribeVpcs")
    assert "AKIDDUMMYVALUE" not in payload["error"]
    assert payload["error_kind"] == "unauthorized"


def test_fail_from_sdk_error_uses_the_shared_envelope():
    try:
        lifecycle.fail_from_sdk_error(FakeModule(), FakeError("bad"), "DeleteVpc")
    except RuntimeError as exc:
        assert exc.args[0]["operation"] == "DeleteVpc"
    else:
        raise AssertionError("expected fail_json")


def test_missing_as_none_swallows_only_not_found():
    assert lifecycle.missing_as_none(lambda: {"VpcId": "vpc-1"}) == {"VpcId": "vpc-1"}
    assert lifecycle.missing_as_none(_raise_not_found) is None
    try:
        lifecycle.missing_as_none(_raise_other)
    except FakeError:
        pass
    else:
        raise AssertionError("expected the non-not-found error to propagate")


def _raise_not_found():
    raise NotFoundError("gone")


def _raise_other():
    raise FakeError("bad")


def test_delete_resource_reports_already_gone_as_unchanged():
    calls = []
    assert lifecycle.delete_resource(lambda: calls.append("delete")) is True
    assert calls == ["delete"]
    assert lifecycle.delete_resource(_raise_not_found) is False


def test_soft_delete_isolates_by_default_and_purges_when_forced():
    calls = []
    assert lifecycle.soft_delete(lambda: calls.append("isolate"),
                                 lambda: calls.append("purge")) is True
    assert calls == ["isolate"]

    calls.clear()
    assert lifecycle.soft_delete(lambda: calls.append("isolate"),
                                 lambda: calls.append("purge"), force=True) is True
    assert calls == ["isolate", "purge"]


def test_soft_delete_without_purge_callable_leaves_resource_recoverable():
    calls = []
    assert lifecycle.soft_delete(lambda: calls.append("isolate"), force=True) is True
    assert calls == ["isolate"]


def test_plan_changes_skips_unmanaged_fields():
    current = {"VpcName": "prod", "DomainName": "prod.internal", "DnsServerSet": ["1.1.1.1"]}
    desired = {"VpcName": "prod", "DomainName": None, "DnsServerSet": ["1.1.1.1", "8.8.8.8"]}
    # DomainName is None in the desired state, so the task does not manage it
    # and the module must not report it as a change.
    assert lifecycle.plan_changes(current, desired) == ["DnsServerSet"]
    assert lifecycle.plan_changes(current, desired, fields=("VpcName",)) == []


def test_plan_changes_handles_absent_remote_state():
    assert lifecycle.plan_changes(None, {"VpcName": "prod"}) == ["VpcName"]


def test_require_state_fails_with_supported_list():
    lifecycle.require_state(FakeModule(), "present", ["present", "absent"], "VPC")
    try:
        lifecycle.require_state(FakeModule(), "restarted", ["present", "absent"], "VPC")
    except RuntimeError as exc:
        assert exc.args[0]["supported_states"] == ["absent", "present"]
    else:
        raise AssertionError("expected an unsupported state failure")
