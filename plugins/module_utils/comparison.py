# -*- coding: utf-8 -*-
"""Resource diff computation for idempotent modules.

The diff returned by ``module.exit_json`` is what makes Ansible runs
self-documenting: check mode shows exactly what a change would do, and a real
run shows what was done. The convention mirrors ``amazon.aws`` and
``azure.azcollection``: ``before`` is the current remote state, ``after`` is
the desired state.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type


def _normalize(value):
    """Strip empty containers so absent and empty compare equal."""
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in sorted(value.items()) if v not in (None, "", [], {})}
    if isinstance(value, list):
        return [_normalize(v) for v in value if v not in (None, "", [], {})]
    return value


def build_diff(before, after):
    """Build an Ansible ``diff`` payload from current and desired state.

    :param before: current remote state (dict) or ``None`` when absent.
    :param after: desired state (dict) or ``None`` when absent.
    :returns: dict with ``before`` and ``after`` keys, or ``None`` when both
        sides are empty/absent (nothing to show).
    """
    before = _normalize(before) if before else None
    after = _normalize(after) if after else None
    if before is None and after is None:
        return None
    return {"before": before, "after": after}


def maybe_diff(module, before, after):
    """Return ``exit_json`` keyword arguments carrying a resource diff.

    Ansible surfaces a module's ``diff`` result in two situations: check mode
    (where the diff *is* the preview of what would change) and runs with
    ``--diff`` (``module._diff``). In a plain run the diff would only inflate
    the result payload, so it is omitted. The convention mirrors
    ``amazon.aws``.

    Use with ``or {}`` and keyword unpacking so the ``diff`` key is left out
    of the result entirely when no diff is wanted::

        module.exit_json(changed=True, **(maybe_diff(module, before, after) or {}))

    :param module: the running module (reads ``check_mode`` and ``_diff``).
    :param before: current remote state (dict) or ``None`` when absent.
    :param after: desired state (dict) or ``None`` when absent.
    :returns: ``{"diff": build_diff(before, after)}`` in check mode or with
        ``--diff`` active, otherwise ``None``.
    """
    if module.check_mode or getattr(module, "_diff", False):
        return {"diff": build_diff(before, after)}
    return None


def changed(before, after, ignore_keys=()):
    """Return True when the desired state differs from the current state.

    Comparison is done on normalized values, ignoring SDK noise fields listed
    in ``ignore_keys`` (e.g. ``CreatedTime``, ``TagSet`` handled separately).
    """
    before = _normalize(before) if before else {}
    after = _normalize(after) if after else {}
    for key in ignore_keys:
        before.pop(key, None)
        after.pop(key, None)
    return before != after
