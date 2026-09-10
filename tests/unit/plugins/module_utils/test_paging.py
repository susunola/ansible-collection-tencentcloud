"""Backward-compatibility tests for the ``module_utils.paging`` shim.

The paginator itself lives in ``plugins/plugin_utils/paging.py`` (behaviour is
covered by ``tests/unit/plugins/plugin_utils/test_paging.py``). This file only
guards the two things ``module_utils.paging`` must keep offering:

* the re-exported ``Paginator`` — ``scripts/generate_info_modules.py`` emits
  ``from ...module_utils.paging import Paginator`` into every generated
  ``_info`` module, and those committed modules can never be rewritten, so
  this import path is frozen;
* ``paginate()``, the module-flavoured convenience wrapper that stays behind.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from importlib import import_module

from ansible_collections.susunola.tencentcloud.plugins.module_utils import paging
from ansible_collections.susunola.tencentcloud.plugins.plugin_utils.paging import Paginator


class FakeResponse(object):
    def __init__(self, items, total, request_id="req-1"):
        self.items = items
        self.total = total
        self.RequestId = request_id


def test_paginator_is_the_plugin_utils_class():
    """One class, two import paths: the shim must not define a second copy."""
    assert paging.Paginator is Paginator


def test_generated_module_import_path_still_resolves():
    """The exact import path emitted by the generator must keep working."""
    module = import_module("ansible_collections.susunola.tencentcloud.plugins.module_utils.paging")
    assert module.Paginator is Paginator


def test_paginate_wrapper_returns_items_and_total():
    items, total = paging.paginate(
        None,
        2,
        lambda offset, limit: {"offset": offset},
        lambda req: FakeResponse([1, 2], 2, request_id="req-w"),
        lambda r: r.items,
        lambda r: r.total,
    )
    assert items == [1, 2]
    assert total == 2


def test_paginate_wrapper_walks_every_page():
    rounds = [[1, 2], [3, 4], [5]]

    def call_api(request):
        return FakeResponse(rounds[request["offset"] // 2], 5)

    items, total = paging.paginate(
        None,
        2,
        lambda offset, limit: {"offset": offset, "limit": limit},
        call_api,
        lambda r: r.items,
        lambda r: r.total,
    )
    assert items == [1, 2, 3, 4, 5]
    assert total == 5
