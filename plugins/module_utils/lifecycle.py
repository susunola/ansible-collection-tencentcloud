# -*- coding: utf-8 -*-
"""Shared lifecycle contracts for mutable and immutable resource fields."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type


def immutable_changes(current, desired, fields):
    """Return immutable fields whose requested values differ from remote state."""
    current = current or {}
    desired = desired or {}
    return {
        field: {"before": current.get(field), "after": desired.get(field)}
        for field in fields
        if field in desired and current.get(field) != desired.get(field)
    }


def require_immutable_unchanged(module, current, desired, fields, resource_name="resource"):
    """Fail clearly instead of silently replacing a resource with data-loss risk."""
    changes = immutable_changes(current, desired, fields)
    if changes:
        module.fail_json(
            msg="Immutable fields cannot be changed on an existing %s" % resource_name,
            immutable_changes=changes,
            replacement_required=True,
        )


def sdk_error_payload(exc, message="Tencent Cloud API request failed"):
    """Build one consistent, diagnostic-safe SDK failure envelope."""
    return {
        "msg": message,
        "error": str(exc),
        "error_code": getattr(exc, "get_code", lambda: None)(),
        "request_id": getattr(exc, "get_request_id", lambda: None)(),
    }
