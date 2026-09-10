# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unified offset/limit pagination for Tencent Cloud list APIs.

Almost every Tencent Cloud list API follows the same shape:

- the request carries ``Offset`` and ``Limit`` (integers serialised as strings
  by the SDK, but the SDK accepts ints too)
- the response carries a paginated set plus a ``TotalCount``

The existing discovery modules each hand-rolled this loop, which duplicated
the same two latent bugs: ``total_count`` was overwritten every round, and an
empty first batch relied on a short-circuit to stop. This module replaces all
of that with a single tested loop.

The loop is pure Python over three callables and has no ``AnsibleModule``
dependency, so it lives in ``plugin_utils``: generated ``_info`` modules,
hand-written modules and controller-side plugins (the CVM/CLB/SG/TKE inventory
plugins page the same list APIs) all iterate with the same class. See
``plugins/plugin_utils/README.md``.

Layering: this module imports nothing else from the collection.
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
        # RequestId of the last API response, set by fetch_all(). Callers can
        # surface it to the user for cross-referencing cloud audit logs.
        self.request_id = None

    def fetch_all(self):
        """Return (items, total_count) walking every page exactly once.

        Termination is driven by the API's reported total (when available) or
        by a short page, never by a mutable total overwritten per round.
        ``request_id`` is left set to the last response's RequestId.
        """
        items = []
        total_count = None
        offset = 0
        while True:
            response = self.call_api(self.build_request(offset, self.page_size))
            self.request_id = getattr(response, "RequestId", None)
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
