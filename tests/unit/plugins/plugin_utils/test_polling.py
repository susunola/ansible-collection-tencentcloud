"""Re-export guard for the ``plugin_utils.polling`` shim.

The loop itself is implemented in ``plugins/module_utils/polling.py`` and its
mechanics are covered by ``tests/unit/plugins/module_utils/test_polling.py``.
This file only guards the controller-side import path, because
``plugins/action/tc_wait.py`` imports ``plugin_utils.polling`` and the
re-export must not quietly turn into a second implementation.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.module_utils import polling as module_polling
from ansible_collections.susunola.tencentcloud.plugins.plugin_utils import polling as plugin_polling


def test_poll_until_is_the_module_utils_function():
    """One function, two import paths: the shim must not define a second copy."""
    assert plugin_polling.poll_until is module_polling.poll_until


def test_poll_outcome_is_the_module_utils_class():
    assert plugin_polling.PollOutcome is module_polling.PollOutcome


def test_the_shim_exports_exactly_the_loop():
    assert plugin_polling.__all__ == ["PollOutcome", "poll_until"]
