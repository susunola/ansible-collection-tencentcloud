"""Unit tests for the shared offset/limit paginator.

``Paginator`` is implemented here in ``plugins/module_utils/paging.py`` because
generated ``_info`` modules, hand-written modules and the inventory plugins all
page the same list APIs, and modules may import only ``plugins.module_utils``
(ansible-test's ``import`` test). ``plugins/plugin_utils/paging.py`` re-exports
the class for controller-side callers; ``tests/unit/plugins/plugin_utils/test_paging.py``
guards that import path.

This file covers the paginator behaviour and ``paginate()``, the module-flavoured
convenience wrapper that stays behind.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from importlib import import_module

from ansible_collections.susunola.tencentcloud.plugins.module_utils import paging


class FakeResponse(object):
    def __init__(self, items, total, request_id="req-1"):
        self.items = items
        self.total = total
        self.RequestId = request_id


def _paginator_rounds(rounds, page_size=10):
    """Build a paginator whose API returns one round per call."""
    calls = []

    def build_request(offset, limit):
        calls.append(offset)
        return {"offset": offset, "limit": limit}

    def call_api(request):
        idx = request["offset"] // page_size
        return FakeResponse(rounds[idx], sum(len(r) for r in rounds))

    return paging.Paginator(page_size, build_request, call_api, lambda r: r.items, lambda r: r.total), calls


def test_single_page():
    p, calls = _paginator_rounds([[1, 2, 3]], page_size=100)
    items, total = p.fetch_all()
    assert items == [1, 2, 3]
    assert total == 3
    assert calls == [0]


def test_multi_page():
    # Two pages reported; total is exactly the number of items returned.
    p, calls = _paginator_rounds([[1, 2, 3], [4, 5, 6]], page_size=3)
    items, total = p.fetch_all()
    assert items == [1, 2, 3, 4, 5, 6]
    assert total == 6
    assert calls == [0, 3]


def test_empty_first_page_terminates():
    p, calls = _paginator_rounds([[]], page_size=3)
    items, total = p.fetch_all()
    assert items == []
    assert calls == [0]


def test_partial_last_page_terminates():
    # Two full pages followed by a partial page must not request a fourth.
    rounds = [[1, 2, 3], [4, 5, 6], [7]]
    p, calls = _paginator_rounds(rounds, page_size=3)
    items, total = p.fetch_all()
    assert items == [1, 2, 3, 4, 5, 6, 7]
    assert calls == [0, 3, 6]


def test_exact_multiple_stops_after_last_full_page():
    # 6 items in pages of 3: third call would return empty, must not happen.
    rounds = [[1, 2, 3], [4, 5, 6], []]
    p, calls = _paginator_rounds(rounds, page_size=3)
    items, total = p.fetch_all()
    assert items == [1, 2, 3, 4, 5, 6]
    assert calls == [0, 3]


def test_short_page_without_reported_total_terminates():
    # An API that never reports TotalCount falls back to the short-page rule.
    rounds = [[1, 2, 3], [4]]

    def call_api(request):
        idx = request["offset"] // 3
        return FakeResponse(rounds[idx], None)

    p = paging.Paginator(3, lambda o, lim: {"offset": o}, call_api, lambda r: r.items, lambda r: r.total)
    items, total = p.fetch_all()
    assert items == [1, 2, 3, 4]
    assert total == 4


def test_none_items_are_treated_as_empty():
    p = paging.Paginator(3, lambda o, lim: {}, lambda r: FakeResponse(None, 0), lambda r: r.items, lambda r: r.total)
    items, total = p.fetch_all()
    assert items == []


def test_request_id_tracks_last_response():
    # The paginator records the last response's RequestId; responses without
    # one fall back to None instead of raising.
    p = paging.Paginator(
        3,
        lambda o, lim: {},
        lambda r: FakeResponse([1, 2], 2, request_id="req-final"),
        lambda r: r.items,
        lambda r: r.total,
    )
    items, total = p.fetch_all()
    assert (items, total) == ([1, 2], 2)
    assert p.request_id == "req-final"

    p = paging.Paginator(3, lambda o, lim: {}, lambda r: object(), lambda r: [], lambda r: None)
    p.fetch_all()
    assert p.request_id is None


def test_generated_module_import_path_still_resolves():
    """The exact import path emitted by the generator must keep working."""
    module = import_module("ansible_collections.susunola.tencentcloud.plugins.module_utils.paging")
    assert module.Paginator is paging.Paginator


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
