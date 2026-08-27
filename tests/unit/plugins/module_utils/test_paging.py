"""Unit tests for the paginator."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.module_utils.paging import Paginator


class FakeResponse(object):
    def __init__(self, items, total):
        self.items = items
        self.total = total


def _paginator_rounds(rounds, page_size=10):
    """Build a paginator whose API returns one round per call."""
    calls = []

    def build_request(offset, limit):
        calls.append(offset)
        return {"offset": offset, "limit": limit}

    def call_api(request):
        idx = request["offset"] // page_size
        return FakeResponse(rounds[idx], sum(len(r) for r in rounds))

    return Paginator(page_size, build_request, call_api, lambda r: r.items, lambda r: r.total), calls


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


def test_none_items_are_treated_as_empty():
    p = Paginator(3, lambda o, lim: {}, lambda r: FakeResponse(None, 0), lambda r: r.items, lambda r: r.total)
    items, total = p.fetch_all()
    assert items == []
