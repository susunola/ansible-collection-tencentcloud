# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Bounded polling loop shared by the module-side and controller-side waiters.

Tencent Cloud operations are asynchronous: the API returns before the resource
has converged. Two very different callers need the same loop over that
convergence:

* :mod:`ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters`
  runs it inside a module and reports through ``module.fail_json``;
* ``plugins/action/tc_wait.py`` runs it on the controller, where every poll is
  a nested module invocation, and reports through ``AnsibleActionFail``.

The loop has no ``AnsibleModule`` dependency and no opinion about how a caller
reports a timeout, so each caller keeps its own failure envelope. It lives in
``module_utils`` — not ``plugin_utils`` — because ansible-test's ``import``
test allows module-side code to import only ``plugins.module_utils``: see
``plugins/plugin_utils/README.md`` for the enforced rule.

Layering: imports nothing else from the collection.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import time


class PollOutcome(object):
    """What one :func:`poll_until` call observed.

    :ivar matched: True when the predicate accepted an observation.
    :ivar value: the observation the predicate accepted, or the last
        observation when the budget ran out.
    :ivar attempts: how many times ``poll()`` was called.
    :ivar waited: seconds slept between polls (the delays actually taken).
    """

    def __init__(self, matched, value, attempts, waited):
        self.matched = matched
        self.value = value
        self.attempts = attempts
        self.waited = waited

    def __repr__(self):
        return "PollOutcome(matched=%r, attempts=%r, waited=%r, value=%r)" % (
            self.matched,
            self.attempts,
            self.waited,
            self.value,
        )


def poll_until(poll, is_done, timeout, delay, sleep_fn=None):
    """Call ``poll()`` until ``is_done`` accepts a result or the budget is gone.

    The loop is deliberately policy-free: it never raises on timeout and never
    looks inside the observation beyond handing it to ``is_done``, so the
    caller decides what a timeout means and which diagnostics to attach.

    :param poll: zero-argument callable returning the current observation.
    :param is_done: callable taking that observation and returning a truthy
        value when the wait is over.
    :param timeout: maximum number of seconds to spend, counted as the sum of
        the delays actually slept. Counting the delays rather than the wall
        clock keeps the loop deterministic and makes it testable with an
        injected ``sleep_fn``.
    :param delay: seconds to sleep between polls; must be greater than zero or
        the loop cannot make progress against its budget.
    :param sleep_fn: injectable sleep, defaults to ``time.sleep``.
    :returns: a :class:`PollOutcome`. When ``matched`` is False the caller can
        report ``outcome.value`` as the last observation instead of polling
        again.
    """
    sleep_fn = sleep_fn or time.sleep
    attempts = 0
    waited = 0
    value = None
    while waited < timeout:
        value = poll()
        attempts += 1
        if is_done(value):
            return PollOutcome(True, value, attempts, waited)
        sleep_fn(delay)
        waited += delay
    return PollOutcome(False, value, attempts, waited)
