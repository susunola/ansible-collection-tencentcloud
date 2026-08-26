# -*- coding: utf-8 -*-
"""Unified offset/limit pagination for Tencent Cloud list APIs.

Almost every Tencent Cloud list API follows the same shape:

- the request carries ``Offset`` and ``Limit`` (integers serialised as strings
  by the SDK, but the SDK accepts ints too)
- the response carries a paginated set plus a ``TotalCount``

The existing discovery modules each hand-rolled this loop, which duplicated
the same two latent bugs: ``total_count`` was overwritten every round, and an
empty first batch relied on a short-circuit to stop. This module replaces all
of that with a single tested loop.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class Paginator(object):
    """Iterate over a paged Tencent Cloud list API.

    :param page_size: requested page size (``Limit``).
    :param build_request: callable(offset, limit) -> request object.
    :param call_api: callable(request) -> response object.
    :param items_of: callable(response) -> list of items (may be None).
    :param total_of: callable(response) -> total count (may be None).
    """

    def __init__(self, page_size, build_request, call_api, items_of, total_of):
        self.page_size = page_size
        self.build_request = build_request
        self.call_api = call_api
        self.items_of = items_of
        self.total_of = total_of

    def fetch_all(self):
        """Return (items, total_count) walking every page exactly once.

        Termination is driven by the API's reported total (when available) or
        by a short page, never by a mutable total overwritten per round.
        """
        items = []
        total_count = None
        offset = 0
        while True:
            response = self.call_api(self.build_request(offset, self.page_size))
            batch = self.items_of(response) or []
            items.extend(batch)
            reported_total = self.total_of(response)
            if total_count is None and reported_total is not None:
                total_count = reported_total
            if total_count is not None:
                if len(items) >= total_count:
                    break
            elif len(batch) < self.page_size:
                break
            offset += len(batch)
        return items, total_count if total_count is not None else len(items)


def paginate(module, page_size, build_request, call_api, items_of, total_of):
    """Convenience wrapper that runs a paginator inside a module.

    Uses the module's client (which already applies the retry policy) and
    returns ``(items, total_count)``.
    """
    paginator = Paginator(page_size, build_request, call_api, items_of, total_of)
    return paginator.fetch_all()
