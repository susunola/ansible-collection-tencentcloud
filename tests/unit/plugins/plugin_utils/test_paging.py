"""Re-export guard for the ``plugin_utils.paging`` shim.

The paginator itself is implemented in ``plugins/module_utils/paging.py`` and
its behaviour is covered by ``tests/unit/plugins/module_utils/test_paging.py``.
This file only guards the controller-side import path, because the inventory
plugins import ``plugin_utils.paging`` and the re-export must not quietly turn
into a second implementation.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.module_utils import paging as module_paging
from ansible_collections.susunola.tencentcloud.plugins.plugin_utils import paging as plugin_paging


def test_paginator_is_the_module_utils_class():
    """One class, two import paths: the shim must not define a second copy."""
    assert plugin_paging.Paginator is module_paging.Paginator


def test_the_module_flavoured_wrapper_is_not_reexported():
    """``paginate()`` is module-only; the controller-side shim stays narrow."""
    assert not hasattr(plugin_paging, "paginate")
    assert plugin_paging.__all__ == ["Paginator"]
