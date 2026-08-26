# -*- coding: utf-8 -*-
"""Waiter: poll an API until a resource reaches a desired state.

Several Tencent Cloud operations (instance lifecycle, image creation, CLB
provisioning) are asynchronous: the request returns immediately and the
resource transitions to a target state some seconds later. A waiter polls a
describe API until the resource matches, so a module can return a
``changed`` result only once the state has converged.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import time

from ansible_collections.tencentcloud.cloud.plugins.module_utils.errors import (
    is_not_found,
)


def wait_for_state(module, poll, desired_states, timeout=120, delay=5, sleep_fn=None):
    """Poll until the resource reaches one of the desired states.

    :param module: module instance (used for check-mode and fail_json).
    :param poll: zero-argument callable returning the current state string.
    :param desired_states: iterable of accepted states (e.g. ["RUNNING"]).
    :param timeout: maximum wait in seconds.
    :param delay: interval between polls in seconds.
    :param sleep_fn: injectable sleep for tests.
    :returns: the state string that matched.
    :raises: SystemExit via ``module.fail_json`` on timeout, unless the module
        is running in check mode (no API writes happen, so waiting is skipped).
    """
    if module.check_mode:
        return None
    sleep_fn = sleep_fn or time.sleep
    waited = 0
    while waited < timeout:
        state = poll()
        if state in desired_states:
            return state
        sleep_fn(delay)
        waited += delay
    module.fail_json(
        msg="Timed out waiting for resource state",
        expected_states=sorted(desired_states),
        last_state=poll(),
        timeout=timeout,
    )


def wait_until_gone(module, poll, timeout=120, delay=5, sleep_fn=None):
    """Poll until the resource no longer exists.

    A resource is considered gone when ``poll()`` raises a "not found" SDK
    exception.
    """
    if module.check_mode:
        return None
    sleep_fn = sleep_fn or time.sleep
    waited = 0
    while waited < timeout:
        try:
            poll()
        except Exception as exc:
            if is_not_found(exc):
                return None
            raise
        sleep_fn(delay)
        waited += delay
    module.fail_json(msg="Timed out waiting for resource deletion", timeout=timeout)
