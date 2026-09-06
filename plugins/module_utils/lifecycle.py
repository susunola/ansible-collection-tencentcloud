# -*- coding: utf-8 -*-
"""Shared lifecycle contracts for resource modules.

Capability panorama gap #4: lifecycle semantics are still implemented per
module. Each module decides on its own what "not found" means, how an
immutable-field drift is reported, whether a delete waits, how a soft delete
differs from a purge, and which fields count as a change. The behaviour is
mostly right, but it is right by copy-paste, so it drifts.

This module is the single implementation of those decisions:

* **not found** -- :func:`missing_as_none` turns a ``ResourceNotFound``
  exception into ``None`` so a lookup reads like a lookup;
* **immutable drift** -- :func:`immutable_changes` /
  :func:`require_immutable_unchanged` fail instead of silently replacing a
  resource;
* **async waiters** -- :mod:`waiters` owns polling; this module only decides
  when to call it;
* **soft delete** -- :func:`soft_delete` encodes the isolate-then-purge
  convention Tencent Cloud databases and CVM use;
* **check/diff** -- :func:`plan_changes` computes the changed field list
  once, for both the check-mode preview and the real run;
* **errors** -- :func:`error_envelope` / :func:`fail_from_sdk_error` emit one
  failure shape, with credentials redacted.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import (
    sanitize_error,
)
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import (
    classify,
    is_not_found,
)


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


def error_envelope(exc, operation=None, message=None):
    """Build the standard failure payload for an SDK exception.

    Every module used to assemble this by hand, and the copies disagree on
    whether the error is redacted and whether the operation is named. The
    envelope also carries the classification from :mod:`errors`, so a caller
    can tell a permission problem from a throttling problem without matching
    on strings.
    """
    if message is None:
        message = "Tencent Cloud API request failed"
        if operation:
            message = "Tencent Cloud API request failed during %s" % operation
    return {
        "msg": message,
        "error": sanitize_error(exc),
        "error_code": getattr(exc, "get_code", lambda: None)(),
        "error_kind": classify(exc),
        "request_id": getattr(exc, "get_request_id", lambda: None)(),
        "operation": operation,
    }


def fail_from_sdk_error(module, exc, operation=None):
    """Fail with the standard envelope. Never returns (``fail_json`` exits)."""
    module.fail_json(**error_envelope(exc, operation=operation))


def missing_as_none(func, *args, **kwargs):
    """Run a lookup and return ``None`` when the resource is reported missing.

    Tencent Cloud APIs are inconsistent about a missing resource: some return
    an empty set, others raise ``ResourceNotFound`` or one of a dozen
    ``InvalidXxxId.NotFound`` variants. Both mean "absent", and a lookup
    should not make the caller care which one happened.
    """
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        if is_not_found(exc):
            return None
        raise


def delete_resource(delete, resource="resource"):
    """Run a delete call; an already-missing resource reports as unchanged.

    :returns: ``True`` when something was deleted, ``False`` when the
        resource was already gone. Exceptions other than "not found"
        propagate.
    """
    try:
        delete()
    except Exception as exc:
        if is_not_found(exc):
            return False
        raise
    return True


def soft_delete(isolate, purge=None, force=False, resource="resource"):
    """Encode the Tencent Cloud two-phase delete convention.

    Databases (CDB, Redis, MongoDB), CVM and several managed services do not
    delete on the first call: they *isolate* the resource into a recycle
    state where it can still be recovered and often still bills, and a second
    call purges it. Modules hard-coded one of the two, so ``state=absent``
    meant different things in different modules.

    :param isolate: callable performing the isolate/terminate call.
    :param purge: callable performing the irreversible purge call.
    :param force: when True the resource is purged as well as isolated.
        Without it - or without a ``purge`` callable - the resource is left
        in the recoverable state.
    :returns: ``True`` when any call changed something.
    """
    changed = delete_resource(isolate, resource=resource)
    if force and purge is not None:
        changed = delete_resource(purge, resource=resource) or changed
    return changed


def plan_changes(current, desired, fields=None):
    """Return the field names whose desired value differs from remote state.

    ``None`` in ``desired`` means "this task does not manage that field",
    which matters because Tencent Cloud ``Modify*`` APIs rewrite every
    attribute they accept: a module must read the current value back for
    anything the user omitted, and it must not report those as changes.

    :param current: remote state as returned by the API.
    :param desired: requested state; ``None`` values are skipped.
    :param fields: restrict the comparison to these fields; defaults to
        every key of ``desired``.
    """
    current = current or {}
    desired = desired or {}
    changes = []
    for field in fields or desired.keys():
        if field not in desired or desired[field] is None:
            continue
        if current.get(field) != desired[field]:
            changes.append(field)
    return changes


def require_state(module, state, supported, resource="resource"):
    """Fail when a module is asked for a lifecycle state it does not implement.

    Silently ignoring an unsupported ``state`` leaves a playbook believing it
    converged; reporting it as "up to date" would be worse.
    """
    if state not in supported:
        module.fail_json(
            msg="%s does not support state=%s" % (resource, state),
            resource=resource,
            state=state,
            supported_states=sorted(supported),
        )
