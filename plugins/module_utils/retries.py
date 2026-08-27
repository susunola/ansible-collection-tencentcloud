# -*- coding: utf-8 -*-
"""Retry policy: throttling detection, exponential backoff and jitter.

The Tencent Cloud SDK has no built-in retry policy, so every module that
talks to the API needs one. Centralising it here guarantees every module
uses the same backoff curve and the same set of "worth retrying" errors
instead of each module implementing its own loop.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import random
import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import (
    is_rate_limited,
    is_retryable,
)


def _default_backoff(attempt):
    """Base sleep in seconds for a 1-based attempt, capped at 10s."""
    return min(10, 2 ** (attempt - 1))


def backoff_delay(attempt, base=2, cap=10, jitter=True):
    """Compute the delay before retrying a failed attempt.

    Uses exponential backoff with full jitter: ``random() * min(cap, base ** attempt)``.
    ``attempt`` is 1-based: the first retry (attempt 1) sleeps between 0 and 2s.
    """
    delay = min(cap, base ** attempt)
    if jitter:
        return random.uniform(0, delay)
    return delay


def retry_on(operation, retries=5, backoff=None, sleep_fn=time.sleep):
    """Run ``operation()`` retrying transient failures.

    Retries are attempted for throttling (``RequestLimitExceeded`` /
    ``LimitExceeded``) and transient errors (5xx, timeouts, ``InternalError``).
    All other exceptions propagate immediately, including "resource not found",
    which callers handle as an idempotent success rather than a retry.

    :param operation: zero-argument callable returning the SDK response.
    :param retries: maximum number of retry attempts after the first call.
    :param backoff: callable(attempt) -> seconds, default exponential w/ jitter.
    :param sleep_fn: sleep function, injectable for tests.
    :returns: the response of the first successful call.
    :raises: the last exception when all attempts are exhausted.
    """
    backoff = backoff or _default_backoff
    attempt = 0
    while True:
        try:
            return operation()
        except Exception as exc:
            if not (is_rate_limited(exc) or is_retryable(exc)):
                raise
            attempt += 1
            if attempt > retries:
                raise
            sleep_fn(backoff(attempt))
