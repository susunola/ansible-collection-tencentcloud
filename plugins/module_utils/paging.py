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

The loop is pure Python over three callables and has no ``AnsibleModule``
dependency. It lives in ``module_utils`` rather than ``plugin_utils`` because
the generated ``_info`` modules — the largest consumer — are module-side, and
ansible-test's ``import`` test allows module-side code to import only
``plugins.module_utils``. ``plugin_utils.paging`` re-exports it for the
controller-side inventory plugins. See ``plugins/plugin_utils/README.md``.

An API that does not honour ``Offset`` is reported, not papered over:
``PaginationError`` is raised when a page is served twice, because the
duplicated rows it would otherwise contribute are indistinguishable from a
correct reply. Hand-written callers already guarded this individually — see
the repeated-token check in ``modules/alb_load_balancer.py`` — and doing it
here is what makes the generated modules inherit the guard.

Layering: imports nothing else from the collection.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class PaginationError(Exception):
    """A list API's paging behaviour cannot be reconciled with its own reply.

    Raised instead of returning a result the caller cannot trust. The two
    shapes it covers both fail silently if left alone: an API that ignores
    ``Offset`` makes the walk re-read one page until the reported total is
    reached, so the result carries duplicate rows, and an empty page under an
    unreached total makes the walk never terminate. Neither is distinguishable
    from a correct reply by looking at the returned items alone, which is why
    this is an exception and not a truncated list.
    """


def _page_signature(batch):
    """Return a comparable form of one page, or None when there is none.

    Two responses never carry the same *objects*: every item is deserialised
    again, so ``batch == previous`` on the raw items would compare identities
    and never match. Serialising first makes the comparison about content,
    which is the only thing a repeated page can share. Items that carry no
    ``_serialize`` (already plain values in tests and inventory code) compare
    as they are.

    ``None`` means the page could not be reduced to a comparable form; the
    caller skips the check for that round instead of guessing.
    """
    signature = []
    for item in batch:
        serializer = getattr(item, "_serialize", None)
        if not callable(serializer):
            signature.append(item)
            continue
        try:
            signature.append(serializer(allow_none=True))
        except Exception:
            return None
    return signature


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

        :raises PaginationError: when the API re-serves a page it already
            served. A repeated non-empty page means ``Offset`` was ignored,
            and appending it again would hand the caller a result whose
            duplicates are invisible; the walk stops and says so instead.
        """
        items = []
        total_count = None
        offset = 0
        previous = None
        while True:
            response = self.call_api(self.build_request(offset, self.page_size))
            self.request_id = getattr(response, "RequestId", None)
            batch = self.items_of(response) or []
            # Only a *non-empty* repeat is a signal: an empty page legitimately
            # follows an empty page when a filtered list has no matches, and it
            # terminates on the check below.
            signature = _page_signature(batch)
            if batch and signature is not None and signature == previous:
                raise PaginationError(
                    "list API returned the same %d item(s) again at offset %d; "
                    "it is ignoring Offset, so continuing would repeat them in "
                    "the result" % (len(batch), offset))
            previous = signature
            items.extend(batch)
            reported_total = self.total_of(response)
            if total_count is None and reported_total is not None:
                total_count = reported_total
            # An empty page ends the walk under either rule. Without this an
            # API that reports TotalCount and then serves nothing would be
            # asked for the same offset forever, because offset only advances
            # by the size of the page it just returned.
            if not batch:
                break
            if total_count is not None:
                if len(items) >= total_count:
                    break
            elif len(batch) < self.page_size:
                break
            offset += len(batch)
        return items, total_count if total_count is not None else len(items)


__all__ = ["Paginator", "PaginationError", "fetch_all_or_raise", "paginate"]


def fetch_all_or_raise(paginator, error_class):
    """Walk *paginator*, re-raising an unusable page sequence as *error_class*.

    Modules call :func:`paginate`, which reports through ``fail_json``. The
    controller-side callers -- the inventory plugins and the shared inventory
    layer -- have no module: they raise, and ansible-core renders that as a
    plugin failure rather than a traceback. ``paging`` cannot import either
    channel, so the caller supplies it. Without this the translation is the
    same four-line ``try``/``except`` copied into every paginated list helper.
    """
    try:
        return paginator.fetch_all()
    except PaginationError as exc:
        raise error_class(
            "Tencent Cloud list API returned an unusable page sequence: %s" % exc)


def paginate(module, page_size, build_request, call_api, items_of, total_of):
    """Convenience wrapper that runs a paginator inside a module.

    Uses the module's client (which already applies the retry policy) and
    returns ``(items, total_count)``.

    ``PaginationError`` is turned into a module failure rather than allowed to
    escape: the 555 generated ``_info`` modules reach this helper, and a raw
    traceback would report an unhandled exception instead of the API behaviour
    that caused it. ``module`` is only used on that path, so callers that
    never expect a malformed list may pass ``None``.
    """
    paginator = Paginator(page_size, build_request, call_api, items_of, total_of)
    try:
        return paginator.fetch_all()
    except PaginationError as exc:
        module.fail_json(
            msg="Tencent Cloud list API returned an unusable page sequence",
            error=str(exc),
            request_id=paginator.request_id,
        )
