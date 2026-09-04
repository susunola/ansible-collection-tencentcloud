"""Unit tests for error classification helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.module_utils import errors


class FakeExc(object):
    def __init__(self, code):
        self._code = code

    def get_code(self):
        return self._code


def test_classify_not_found_prefix():
    assert errors.classify(FakeExc("ResourceNotFound")) == "not_found"
    assert errors.classify(FakeExc("ResourceNotFound.SecurityGroupId")) == "not_found"


def test_classify_known_not_found_variants():
    assert errors.classify(FakeExc("InvalidSecurityGroupId.NotFound")) == "not_found"
    assert errors.classify(FakeExc("InvalidInstanceId.NotFound")) == "not_found"
    assert errors.classify(FakeExc("InvalidParameter.LBIdNotFound")) == "not_found"
    assert errors.classify(FakeExc("InvalidParameter.ListenerIdNotFound")) == "not_found"


def test_classify_rate_limited():
    assert errors.classify(FakeExc("RequestLimitExceeded")) == "rate_limited"
    assert errors.classify(FakeExc("LimitExceeded")) == "rate_limited"


def test_classify_retryable_internal_error():
    assert errors.classify(FakeExc("InternalError")) == "retryable"
    assert errors.classify(FakeExc("InternalError.AuthFailure")) == "retryable"
    assert errors.classify(FakeExc("RequestTimeout")) == "retryable"


def test_classify_unauthorized():
    assert errors.classify(FakeExc("AuthFailure.SecretIdNotFound")) == "unauthorized"
    assert errors.classify(FakeExc("UnauthorizedOperation")) == "unauthorized"


def test_classify_other():
    assert errors.classify(FakeExc("InvalidParameterValue")) == "other"
    assert errors.classify(FakeExc("ResourceInUse")) == "other"


def test_classify_no_code():
    assert errors.classify(object()) == "other"


def test_is_idempotent_success_matches_not_found():
    assert errors.is_idempotent_success(FakeExc("ResourceNotFound"))
    assert not errors.is_idempotent_success(FakeExc("ResourceInUse"))


def test_is_not_found_non_sdk_exception():
    assert not errors.is_not_found(ValueError("boom"))


def test_is_retryable_treats_rate_limited_as_retryable():
    assert errors.is_retryable(FakeExc("RequestLimitExceeded"))
    assert errors.is_retryable(FakeExc("LimitExceeded.Instances"))


def test_is_retryable_false_for_non_transient():
    assert not errors.is_retryable(FakeExc("InvalidParameterValue"))


def test_is_rate_limited_only_matches_throttle_prefixes():
    assert not errors.is_rate_limited(FakeExc("InternalError"))
    assert not errors.is_rate_limited(FakeExc("ResourceNotFound"))
