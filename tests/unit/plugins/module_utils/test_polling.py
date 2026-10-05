"""Unit tests for the shared bounded polling loop.

``poll_until`` is implemented here in ``plugins/module_utils/polling.py``
because both ``module_utils.waiters`` (module-side, reports through
``module.fail_json``) and the ``tc_wait`` action plugin (controller-side,
reports through ``AnsibleActionFail``) run the same loop, and modules may
import only ``plugins.module_utils`` (ansible-test's ``import`` test).
``plugins/plugin_utils/polling.py`` re-exports it for controller-side callers.

The loop is policy-free, so these tests pin the loop mechanics only: the
caller-owned failure behaviour is covered by
``tests/unit/plugins/module_utils/test_waiters.py`` and
``tests/unit/plugins/action/test_tc_wait.py``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.module_utils.polling import (
    PollOutcome,
    poll_until,
)


def _no_sleep(_seconds):
    return None


def test_returns_immediately_on_first_match():
    calls = []

    def poll():
        calls.append(1)
        return "RUNNING"

    outcome = poll_until(poll, lambda value: value == "RUNNING", timeout=10, delay=1, sleep_fn=_no_sleep)
    assert outcome.matched is True
    assert outcome.value == "RUNNING"
    assert outcome.attempts == 1
    assert outcome.waited == 0
    assert len(calls) == 1


def test_polls_until_the_predicate_accepts():
    states = iter(["PENDING", "PENDING", "RUNNING"])
    slept = []

    outcome = poll_until(
        lambda: next(states),
        lambda value: value == "RUNNING",
        timeout=10,
        delay=2,
        sleep_fn=slept.append,
    )
    assert outcome.matched is True
    assert outcome.value == "RUNNING"
    assert outcome.attempts == 3
    assert outcome.waited == 4
    assert slept == [2, 2]


def test_exhausted_budget_reports_the_last_observation():
    # The caller must be able to describe what it last saw without polling
    # again, so a failed outcome still carries the final value.
    values = iter(["PENDING", "PENDING"])

    outcome = poll_until(lambda: next(values), lambda value: value == "RUNNING", timeout=2, delay=1, sleep_fn=_no_sleep)
    assert outcome.matched is False
    assert outcome.value == "PENDING"
    assert outcome.attempts == 2
    assert outcome.waited == 2


def test_zero_timeout_never_polls():
    # A zero budget is spent before the first poll, so the loop makes no API
    # call at all and reports no observation.
    def poll():
        raise AssertionError("poll must not run with a zero timeout")

    outcome = poll_until(poll, lambda value: True, timeout=0, delay=1, sleep_fn=_no_sleep)
    assert outcome.matched is False
    assert outcome.value is None
    assert outcome.attempts == 0


def test_truthy_predicate_is_accepted():
    # The predicate is only required to be truthy, not exactly True, so
    # callers can pass expressions such as `len(items) >= 3`.
    outcome = poll_until(lambda: [1, 2, 3], lambda value: len(value) >= 3, timeout=5, delay=1, sleep_fn=_no_sleep)
    assert outcome.matched is True
    assert outcome.value == [1, 2, 3]


def test_delay_is_not_slept_after_a_match():
    slept = []

    def poll():
        return "READY"

    poll_until(poll, lambda value: True, timeout=10, delay=7, sleep_fn=slept.append)
    assert slept == []


def test_a_zero_delay_still_terminates():
    """``delay=0`` used to hang the loop, and the caller cannot prevent it.

    The budget counts the delays actually slept, so at zero the budget never
    advanced and ``waited < timeout`` stayed true: the loop asked for another
    observation forever. Every one of the 77 modules that waits through this
    helper takes ``waiter_delay`` from the shared argument spec, where the
    option has no lower bound, so a task setting it to zero hung. The wall
    clock ends the wait now.
    """
    ticks = iter(range(1000))

    outcome = poll_until(
        lambda: "PENDING", lambda value: value == "DONE",
        timeout=3, delay=0, sleep_fn=_no_sleep, clock=lambda: next(ticks))

    assert outcome.matched is False
    assert outcome.value == "PENDING"
    # Nothing was slept, so the slept-delay budget is still zero -- the wall
    # clock is what stopped it.
    assert outcome.waited == 0


def test_a_slow_poll_cannot_outlast_the_timeout():
    """The budget is wall-clock as well as slept-delay.

    A caller asking for "at most N seconds" means N seconds, so a poll that
    takes longer than ``delay`` between observations must not buy extra time.
    Here ten seconds pass per observation: the slept-delay budget alone would
    allow three polls, the wall clock allows one.
    """
    ticks = iter([0, 10, 20, 30])

    outcome = poll_until(
        lambda: "PENDING", lambda value: value == "DONE",
        timeout=15, delay=5, sleep_fn=_no_sleep, clock=lambda: next(ticks))

    assert outcome.matched is False
    assert outcome.attempts == 1


def test_outcome_repr_is_informative():
    outcome = PollOutcome(True, "RUNNING", 2, 1)
    assert "matched=True" in repr(outcome)
    assert "RUNNING" in repr(outcome)
