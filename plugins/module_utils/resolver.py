# -*- coding: utf-8 -*-
"""Unified resource reference resolution.

Capability panorama gap #3: cross-resource references are still ID-driven and
silently ambiguous. Two things combine into a real correctness problem:

* Tencent Cloud list filters match **fuzzily**. ``vpc-name`` is a substring
  match, so ``DescribeVpcs(vpc-name="prod")`` also returns ``prod-old`` and
  ``prod-eu``.
* Most modules then take ``response.VpcSet[0]`` and call it a day.

A task that says ``name: prod`` therefore manages whichever resource the API
happened to list first. Renaming or deleting the wrong VPC is possible and
invisible.

This module gives every resource module one resolution contract:

* an ID, a name, a tag set - or any combination - addresses a resource;
* a server-side filter is only a hint. Results are always re-checked
  client-side, so a fuzzy filter can never widen the match;
* zero matches returns ``None``;
* more than one match is an error that lists the candidates, never a silent
  pick;
* a registered variable (the dict a previous task returned) is accepted
  wherever an ID or a name is accepted.

Typical use inside a module::

    def find_vpc(module, client, models, name, vpc_id):
        def describe(filters):
            request = models.DescribeVpcsRequest()
            request.Offset = "0"
            request.Limit = "100"
            resolver.attach_filters(request, models, filters)
            response = module.sdk_call(client.DescribeVpcs, request)
            return resolver.records(response.VpcSet)

        return resolver.resolve_one(
            module, describe, resource="VPC",
            id_value=vpc_id, name_value=name,
            id_keys=("VpcId",), name_keys=("VpcName",),
            id_filters=("vpc-id",), name_filters=("vpc-name",),
        )
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.module_utils.tagging import (
    normalize_tags,
)


# Tencent Cloud is not consistent about tag field names: VPC/CVM style APIs
# return TagKey/TagValue, older ones Key/Value, and a few use camelCase.
TAG_KEY_FIELDS = ("TagKey", "Key", "tagKey", "key")
TAG_VALUE_FIELDS = ("TagValue", "Value", "tagValue", "value")

TAG_SET_FIELDS = ("TagSet", "Tags", "tagSet", "tags")

# How many candidates to echo back when a reference is ambiguous. Enough to
# diagnose the problem, small enough to keep the failure payload readable.
MAX_CANDIDATES = 10


def serialize(record):
    """Return a plain dict for an SDK model object; dicts pass through."""
    if record is None:
        return None
    if isinstance(record, dict):
        return record
    serializer = getattr(record, "_serialize", None)
    if callable(serializer):
        return serializer(allow_none=True)
    return record


def records(items):
    """Normalize a Describe* result set into a list of dicts."""
    return [serialize(item) for item in (items or []) if item is not None]


def value_of(record, keys):
    """First non-empty value among ``keys`` (SDK attributes or dict keys)."""
    if record is None:
        return None
    for key in keys:
        if isinstance(record, dict):
            value = record.get(key)
        else:
            value = getattr(record, key, None)
        if value not in (None, ""):
            return value
    return None


def tag_map(record):
    """Return the record's tags as a ``{key: value}`` dict."""
    if record is None:
        return {}
    tags = value_of(record, TAG_SET_FIELDS)
    if not tags:
        return {}
    normalized = {}
    for tag in tags:
        key = value_of(tag, TAG_KEY_FIELDS)
        if key is None:
            continue
        normalized[str(key)] = str(value_of(tag, TAG_VALUE_FIELDS) or "")
    return normalized


def matches_tags(record, tags):
    """True when the record carries every requested tag."""
    if not tags:
        return True
    current = tag_map(record)
    desired = normalize_tags(tags)
    return all(current.get(key) == value for key, value in desired.items())


def _matches_id(record, id_value, id_keys):
    if not id_value:
        return True
    current = value_of(record, id_keys)
    return current is not None and str(current) == str(id_value)


def _matches_name(record, name_value, name_keys, exact=True):
    if not name_value:
        return True
    current = value_of(record, name_keys)
    if current is None:
        return False
    current = str(current)
    wanted = str(name_value)
    if exact:
        return current == wanted
    return wanted.casefold() in current.casefold()


def filter_records(items, id_value=None, name_value=None, tags=None, id_keys=(), name_keys=(), exact=True):
    """Return the records matching every selector that was supplied.

    Selectors left as ``None`` are ignored, so the same helper serves
    "by id", "by name", "by tags" and any combination.
    """
    matched = []
    for record in records(items):
        if not _matches_id(record, id_value, id_keys):
            continue
        if not _matches_name(record, name_value, name_keys, exact=exact):
            continue
        if not matches_tags(record, tags):
            continue
        matched.append(record)
    return matched


def candidate_summary(items, id_keys=(), name_keys=(), limit=MAX_CANDIDATES):
    """Describe candidates for an ambiguity failure payload."""
    return [
        {"id": value_of(record, id_keys), "name": value_of(record, name_keys)}
        for record in items[:limit]
    ]


def reference(value, id_keys=(), name_keys=(), default="name"):
    """Normalize a user-supplied reference into ``(id_value, name_value)``.

    Accepts a plain string (an ID or a name - ``default`` says which) or a
    dict, which is what a registered variable from a previous task looks
    like. This is what lets a task chain feed ``vpc.vpc_id`` or the whole
    ``vpc`` dict straight into the next module.
    """
    if value is None:
        return (None, None)
    if isinstance(value, dict):
        return (value_of(value, id_keys), value_of(value, name_keys))
    text = str(value)
    if default == "id":
        return (text, None)
    return (None, text)


def attach_filters(request, models, filters, attr="Filters", filter_class="Filter"):
    """Attach ``{filter_name: [values]}`` to an SDK request.

    Filters already on the request are kept unless the resolver is about to
    set the same name, in which case they are replaced. That matters for
    scoped lookups: a subnet lookup carries a ``vpc-id`` scope filter built
    by the module, and re-resolving the name must not drop the scope or
    apply ``vpc-id`` twice.

    Products that name their filter class or attribute differently pass
    ``filter_class``/``attr``. Returns the request so it can be chained.
    """
    if not filters:
        return request
    factory = getattr(models, filter_class, None)
    existing = list(getattr(request, attr, None) or [])
    kept = [item for item in existing if getattr(item, "Name", None) not in filters]
    for name, values in sorted(filters.items()):
        item = factory()
        item.Name = name
        item.Values = [str(value) for value in values]
        kept.append(item)
    setattr(request, attr, kept)
    return request


def _with_extra_match(items, extra_match):
    """Apply the caller's product-specific predicate, when there is one."""
    if extra_match is None:
        return list(items)
    return [record for record in items if extra_match(record)]


def _fail_ambiguous(module, resource, matches, selectors, id_keys, name_keys):
    module.fail_json(
        msg="Ambiguous %s reference: %d resources match %s"
        % (resource, len(matches), selectors or "the given selectors"),
        resource=resource,
        ambiguous=True,
        match_count=len(matches),
        matches=candidate_summary(matches, id_keys=id_keys, name_keys=name_keys),
        resolution="pass an explicit id, or make the name/tags unique",
    )


def _fail_not_found(module, resource, selectors):
    module.fail_json(
        msg="%s not found for %s" % (resource, selectors or "the given selectors"),
        resource=resource,
        not_found=True,
    )


def resolve_one(module, describe, resource="resource", id_value=None, name_value=None, tags=None,
                id_keys=(), name_keys=(), id_filters=None, name_filters=None, extra_filters=None,
                extra_match=None, required=False):
    """Resolve exactly one resource through a Describe* call.

    :param module: module instance (used for ``sdk_call`` and ``fail_json``).
    :param describe: callable ``describe(filters)`` returning an iterable of
        records (SDK objects or dicts). ``filters`` is a
        ``{name: [values]}`` dict or ``None``.
    :param resource: human-readable resource name used in failures.
    :param id_value: resource ID. When given it is the identity and the
        other selectors are ignored (a rename task must still find the
        resource by ID).
    :param name_value: resource name.
    :param tags: dict of tags the resource must carry.
    :param id_keys/name_keys: record fields holding the ID and the name.
    :param id_filters/name_filters: server-side filter names, used only to
        narrow the request; the match is always re-checked client-side.
    :param extra_filters: additional ``{name: [values]}`` filters, applied
        server-side only.
    :param extra_match: predicate ``record -> bool`` for product-specific
        identity that is not an ID, a name or a tag (for example an EIP
        addressed by its public address). Applied client-side to every
        candidate, and usable as the only selector.
    :param required: fail instead of returning ``None`` when nothing matches.
    :returns: the matching record as a dict, or ``None``.

    Name resolution prefers an exact match. When no exact match exists but
    exactly one fuzzy match does, that single candidate is accepted (the
    fuzzy filter is a substring match, so this keeps existing playbooks
    working); two or more fuzzy candidates are reported as ambiguous.
    """
    if not id_value and not name_value and not tags and extra_match is None:
        # Nothing to resolve on - the caller has no identity for the
        # resource. Listing everything would be a silent wildcard.
        return None

    filters = {}
    if id_value:
        for name in id_filters or ():
            filters[name] = [str(id_value)]
    if name_value:
        for name in name_filters or ():
            filters[name] = [str(name_value)]
    for name, values in (extra_filters or {}).items():
        filters[name] = list(values)

    items = describe(filters or None)
    selectors = ", ".join(
        part for part in (
            "id=%s" % (id_value,) if id_value else None,
            "name=%s" % (name_value,) if name_value else None,
            "tags=%s" % (sorted(normalize_tags(tags).items()),) if tags else None,
        ) if part
    ) or None

    if id_value:
        # An ID is unique by construction; more than one hit means the API
        # (or the caller's id_keys) is wrong, and that is worth failing on.
        matches = _with_extra_match(
            filter_records(items, id_value=id_value, id_keys=id_keys), extra_match,
        )
        if len(matches) > 1:
            _fail_ambiguous(module, resource, matches, selectors, id_keys, name_keys)
        if matches:
            return matches[0]
        if required:
            _fail_not_found(module, resource, selectors)
        return None

    exact = _with_extra_match(
        filter_records(
            items, name_value=name_value, tags=tags, id_keys=id_keys, name_keys=name_keys, exact=True,
        ),
        extra_match,
    )
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        _fail_ambiguous(module, resource, exact, selectors, id_keys, name_keys)

    # No exact match: the fuzzy server-side filter may still have returned
    # exactly one candidate, which is not ambiguous.
    fuzzy = _with_extra_match(
        filter_records(
            items, name_value=name_value, tags=tags, id_keys=id_keys, name_keys=name_keys, exact=False,
        ),
        extra_match,
    )
    fuzzy = [record for record in fuzzy if record not in exact]
    if len(fuzzy) == 1:
        return fuzzy[0]
    if len(fuzzy) > 1:
        _fail_ambiguous(module, resource, fuzzy, selectors, id_keys, name_keys)

    if required:
        _fail_not_found(module, resource, selectors)
    return None


def resolve_all(describe, name_value=None, tags=None, id_value=None,
                id_keys=(), name_keys=(), name_filters=None, id_filters=None,
                extra_filters=None, exact=False):
    """Resolve every resource matching the selectors.

    The counterpart of :func:`resolve_one` for list-style lookups: a
    non-unique result is the point here, so ambiguity never fails and no
    module handle is needed.
    """
    filters = {}
    if id_value:
        for name in id_filters or ():
            filters[name] = [str(id_value)]
    if name_value:
        for name in name_filters or ():
            filters[name] = [str(name_value)]
    for name, values in (extra_filters or {}).items():
        filters[name] = list(values)
    items = describe(filters or None)
    return filter_records(
        items, id_value=id_value, name_value=name_value, tags=tags,
        id_keys=id_keys, name_keys=name_keys, exact=exact,
    )
