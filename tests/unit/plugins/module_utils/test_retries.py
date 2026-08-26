"""Unit tests for the retry policy."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
import pytest

from ansible_collections.tencentcloud.cloud.plugins.module_utils import retries


class FakeRateLimited(Exception):
    def get_code(self):
        return "RequestLimitExceeded"


class FakeInternal(Exception):
    def get_code(self):
        return "InternalError"


class FakePermanent(Exception):
    def get_code(self):
        return "InvalidParameterValue"


class FakeNoCode(Exception):
    pass


def _no_sleep(seconds):
    raise AssertionError("should not sleep")


def test_retry_on_success_first_try():
    calls = []
    result = retries.retry_on(lambda: calls.append(1) or "ok", retries=3, sleep_fn=_no_sleep)
    assert result == "ok"
    assert len(calls) == 1


def test_retry_on_recovers_after_throttling():
    calls = []

    def operation():
        calls.append(1)
        if len(calls) < 3:
            raise FakeRateLimited("slow down")
        return "recovered"

    result = retries.retry_on(operation, retries=5, backoff=lambda attempt: 0, sleep_fn=lambda s: None)
    assert result == "recovered"
    assert len(calls) == 3


def test_retry_on_exhausts_and_raises():
    calls = []

    def operation():
        calls.append(1)
        raise FakeInternal("always fails")

    with pytest.raises(FakeInternal):
        retries.retry_on(operation, retries=2, backoff=lambda attempt: 0, sleep_fn=lambda s: None)
    assert len(calls) == 3  # initial call + 2 retries


def test_retry_on_does_not_retry_permanent_errors():
    calls = []

    def operation():
        calls.append(1)
        raise FakePermanent("nope")

    with pytest.raises(FakePermanent):
        retries.retry_on(operation, retries=5, sleep_fn=_no_sleep)
    assert len(calls) == 1


def test_retry_on_does_not_retry_unclassified_errors():
    calls = []

    def operation():
        calls.append(1)
        raise FakeNoCode("mystery")

    with pytest.raises(FakeNoCode):
        retries.retry_on(operation, retries=5, sleep_fn=_no_sleep)
    assert len(calls) == 1


def test_backoff_delay_is_capped():
    for attempt in range(1, 20):
        delay = retries.backoff_delay(attempt, base=2, cap=10, jitter=False)
        assert delay <= 10


def test_backoff_delay_full_jitter_within_range():
    import random
    random.seed(42)
    for attempt in range(1, 8):
        delay = retries.backoff_delay(attempt, base=2, cap=10, jitter=True)
        assert 0 <= delay <= min(10, 2 ** attempt)


def test_default_backoff_exponential():
    assert retries._default_backoff(1) == 1
    assert retries._default_backoff(2) == 2
    assert retries._default_backoff(5) == 10  # capped
