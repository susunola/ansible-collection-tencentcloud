"""Unit tests for the waiters module."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import (
    wait_for_state,
    wait_for_task,
    wait_until_gone,
)


class _NotFoundError(Exception):
    """Shape-compatible stand-in for an SDK "resource not found" exception."""

    def __init__(self, code="ResourceNotFound.Bucket"):
        super(_NotFoundError, self).__init__(code)
        self._code = code

    def get_code(self):
        return self._code


class FakeModule(object):
    def __init__(self, check_mode=False):
        self.check_mode = check_mode
        self.failures = []

    def fail_json(self, *args, **kwargs):
        if args:
            kwargs["msg"] = args[0]
        kwargs["failed"] = True
        raise SystemExit(kwargs)


def _no_sleep(_seconds):
    return None


def test_wait_for_task_returns_payload_on_success():
    module = FakeModule()
    calls = []

    def poll():
        calls.append(1)
        return 0, None, {"LoadBalancerIds": ["lb-1"]}

    assert wait_for_task(module, poll, timeout=10, delay=1, sleep_fn=_no_sleep) == {
        "LoadBalancerIds": ["lb-1"],
    }
    assert len(calls) == 1


def test_wait_for_task_polls_until_success():
    module = FakeModule()
    statuses = iter([(2, None, None), (2, None, None), (0, None, "done")])

    def poll():
        return next(statuses)

    assert wait_for_task(module, poll, timeout=10, delay=1, sleep_fn=_no_sleep) == "done"


def test_wait_for_task_fails_fast_on_task_failure():
    module = FakeModule()
    calls = []

    def poll():
        calls.append(1)
        return 1, "quota exceeded", None

    with pytest.raises(SystemExit) as excinfo:
        wait_for_task(module, poll, timeout=10, delay=1, sleep_fn=_no_sleep)
    assert len(calls) == 1
    assert "quota exceeded" in excinfo.value.args[0]["msg"]


def test_wait_for_task_times_out():
    module = FakeModule()

    def poll():
        return 2, None, None

    with pytest.raises(SystemExit) as excinfo:
        wait_for_task(module, poll, timeout=2, delay=1, sleep_fn=_no_sleep)
    assert "Timed out" in excinfo.value.args[0]["msg"]


def test_wait_for_task_skips_polling_in_check_mode():
    module = FakeModule(check_mode=True)

    def poll():
        raise AssertionError("poll must not run in check mode")

    assert wait_for_task(module, poll, timeout=10, delay=1, sleep_fn=_no_sleep) is None


def test_wait_for_state_returns_immediately_on_match():
    module = FakeModule()
    calls = []

    def poll():
        calls.append(1)
        return "RUNNING"

    state = wait_for_state(module, poll, ["RUNNING"], timeout=10, delay=1, sleep_fn=_no_sleep)
    assert state == "RUNNING"
    assert len(calls) == 1


def test_wait_for_state_polls_until_match():
    module = FakeModule()
    states = iter(["PENDING", "PENDING", "RUNNING"])

    def poll():
        return next(states)

    assert wait_for_state(module, poll, ["RUNNING"], timeout=10, delay=1, sleep_fn=_no_sleep) == "RUNNING"


def test_wait_for_state_accepts_multiple_desired_states():
    module = FakeModule()

    def poll():
        return "DELETING"

    assert wait_for_state(module, poll, ["RUNNING", "DELETING"], timeout=10, delay=1, sleep_fn=_no_sleep) == "DELETING"


def test_wait_for_state_skips_polling_in_check_mode():
    module = FakeModule(check_mode=True)

    def poll():
        raise AssertionError("poll must not run in check mode")

    assert wait_for_state(module, poll, ["RUNNING"], timeout=10, delay=1, sleep_fn=_no_sleep) is None


def test_wait_for_state_times_out_with_last_state():
    module = FakeModule()

    def poll():
        return "STUCK"

    with pytest.raises(SystemExit) as excinfo:
        wait_for_state(module, poll, ["RUNNING"], timeout=2, delay=1, sleep_fn=_no_sleep)
    payload = excinfo.value.args[0]
    assert "Timed out" in payload["msg"]
    assert payload["expected_states"] == ["RUNNING"]
    assert payload["last_state"] == "STUCK"
    assert payload["timeout"] == 2


def test_wait_until_gone_returns_when_poll_raises_not_found():
    module = FakeModule()
    calls = []

    def poll():
        calls.append(1)
        raise _NotFoundError()

    assert wait_until_gone(module, poll, timeout=10, delay=1, sleep_fn=_no_sleep) is None
    assert len(calls) == 1


def test_wait_until_gone_polls_until_absent():
    module = FakeModule()
    responses = [object(), object(), _NotFoundError()]
    calls = []

    def poll():
        calls.append(1)
        current = responses.pop(0)
        if isinstance(current, Exception):
            raise current
        return current

    assert wait_until_gone(module, poll, timeout=10, delay=1, sleep_fn=_no_sleep) is None
    assert len(calls) == 3


def test_wait_until_gone_reraises_unexpected_errors():
    module = FakeModule()
    calls = []

    def poll():
        calls.append(1)
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        wait_until_gone(module, poll, timeout=10, delay=1, sleep_fn=_no_sleep)
    assert len(calls) == 1


def test_wait_until_gone_skips_polling_in_check_mode():
    module = FakeModule(check_mode=True)

    def poll():
        raise AssertionError("poll must not run in check mode")

    assert wait_until_gone(module, poll, timeout=10, delay=1, sleep_fn=_no_sleep) is None


def test_wait_until_gone_times_out_while_resource_still_exists():
    module = FakeModule()

    def poll():
        return object()

    with pytest.raises(SystemExit) as excinfo:
        wait_until_gone(module, poll, timeout=2, delay=1, sleep_fn=_no_sleep)
    assert "Timed out waiting for resource deletion" in excinfo.value.args[0]["msg"]
