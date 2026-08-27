"""Unit tests for the waiters module."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.tencentcloud.cloud.plugins.module_utils.waiters import (
    wait_for_task,
)


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
