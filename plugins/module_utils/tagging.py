# -*- coding: utf-8 -*-
"""Tag conversion and comparison helpers.

Tencent Cloud list APIs return tags as ``Tag`` objects with ``Key``/``Value``
attributes, while resource modules receive a plain ``dict`` from the user and
write APIs consume ``Tag`` objects. These helpers convert between the two
representations and diff them for idempotency checks.

:func:`merge_tags` layers the two readers over each other so any number of
sources in any of those shapes can be combined in one call. It lives here
rather than in ``plugin_utils`` because the layering rule is one-directional:
its consumer is the ``tag_merge`` filter plugin, and the collection's shared
tag semantics must stay in the layer a module can also import.

Layering: imports nothing else from the collection.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type


def normalize_tags(tags):
    """Return a sorted ``{key: value}`` dict from user input.

    Accepts a dict or a list of ``{key, value}`` dicts (the shape Tencent
    Cloud consoles and SDKs commonly use). ``None`` becomes ``{}``.
    """
    if not tags:
        return {}
    if isinstance(tags, dict):
        return {str(k): str(v) for k, v in sorted(tags.items())}
    normalized = {}
    for item in tags:
        key = str(item.get("key"))
        value = str(item.get("value"))
        if key:
            normalized[key] = value
    return dict(sorted(normalized.items()))


def tags_from_sdk(sdk_tags):
    """Convert SDK ``Tag`` objects (or serialized dicts) to a dict."""
    if not sdk_tags:
        return {}
    normalized = {}
    for tag in sdk_tags:
        key = getattr(tag, "Key", None)
        if key is None:
            key = tag.get("Key") if isinstance(tag, dict) else None
        if not key:
            continue
        value = getattr(tag, "Value", None)
        if value is None:
            value = tag.get("Value") if isinstance(tag, dict) else None
        normalized[str(key)] = str(value)
    return dict(sorted(normalized.items()))


def build_sdk_tags(models, tags):
    """Build a list of SDK ``Tag`` objects from a normalized dict.

    :param models: the SDK service ``models`` module (provides ``Tag``).
    """
    if not tags:
        return None
    sdk_tags = []
    for key, value in sorted(tags.items()):
        tag = models.Tag()
        tag.Key = key
        tag.Value = value
        sdk_tags.append(tag)
    return sdk_tags


def compare_tags(desired, current_sdk_tags):
    """Compare desired tags against tags reported by the API.

    :param desired: normalized dict from user input.
    :param current_sdk_tags: SDK ``Tag`` objects from the describe response.
    :returns: (is_equal, to_add, to_remove) where ``to_add`` is a dict of
        keys whose value differs or that are missing, and ``to_remove`` is a
        list of keys present remotely but absent from the desired set.
    """
    desired = normalize_tags(desired)
    current = tags_from_sdk(current_sdk_tags)
    to_add = {k: v for k, v in desired.items() if current.get(k) != v}
    to_remove = [k for k in current if k not in desired]
    return (not to_add and not to_remove), to_add, to_remove


#: How the two sides of a single tag are spelled. Tencent Cloud's own shape is
#: ``{"Key": ..., "Value": ...}``; the collection's parameter shape is
#: ``{"key": ..., "value": ...}`` (see :func:`normalize_tags`).
_TAG_PAIR_FIELDS = (("Key", "Value"), ("key", "value"))


def _single_tag_pair(mapping):
    """Return ``(key, value)`` when ``mapping`` is one tag, otherwise ``None``.

    A mapping whose keys are a subset of one of the :data:`_TAG_PAIR_FIELDS`
    pairs is a *single tag* and must not be read as a tag map — otherwise
    ``{"Key": "env", "Value": "prod"}`` would come out as two tags named
    ``Key`` and ``Value``. Any other mapping is a tag map (several tags at
    once) and is left to :func:`normalize_tags`.
    """
    for key_field, value_field in _TAG_PAIR_FIELDS:
        if key_field in mapping and set(mapping) <= {key_field, value_field}:
            return mapping[key_field], mapping.get(value_field)
    return None


def _iter_tag_pairs(source):
    """Yield ``(key, value)`` pairs from one tag source of any accepted shape.

    Delegates to :func:`normalize_tags` and :func:`tags_from_sdk` for the
    actual field reading, so a merged result and a module's own view of the
    same tags are produced by the same code.

    :raises TypeError: when ``source`` is neither empty, nor a mapping, nor a
        list/tuple of sources, nor an object exposing a ``Key`` attribute. A
        silently dropped source would be a tag loss nobody notices.
    """
    if not source:
        return
    if isinstance(source, dict):
        pair = _single_tag_pair(source)
        if pair is None:
            for item in normalize_tags(source).items():
                yield item
            return
        # Re-read the pair through normalize_tags so an empty key is dropped
        # exactly as it is for a tag map or a tag list.
        for item in normalize_tags([{"key": pair[0], "value": pair[1]}]).items():
            yield item
        return
    if isinstance(source, (list, tuple)):
        for element in source:
            for item in _iter_tag_pairs(element):
                yield item
        return
    if not hasattr(source, "Key"):
        raise TypeError(
            "unsupported tag source %r: expected a mapping, a list of tags or an SDK Tag object" % (source,)
        )
    for item in tags_from_sdk([source]).items():
        yield item


def merge_tags(*sources):
    """Merge any number of tag sources into one normalized ``{key: value}`` dict.

    Sources are merged left to right, so the last source that sets a key wins
    — the same precedence as ``dict.update`` and Jinja's ``combine``. Each
    source may be any shape the collection already deals with:

    * a ``{key: value}`` tag map (the module parameter shape);
    * a ``{"Key": ..., "Value": ...}`` single tag (the Tencent Cloud API shape);
    * a list of either of the above (what a ``*_info`` module returns);
    * a list of SDK ``Tag`` objects with ``Key``/``Value`` attributes;
    * a nested list of any of the above, which is flattened.

    ``None`` and empty sources contribute nothing, so an optional variable can
    be merged without a guard. Keys and values are stringified and the result
    is sorted by key, which is what :func:`normalize_tags` returns — so a
    merged result can be handed back to a module or compared with what the
    module computed.

    :raises TypeError: for a source of an unsupported type (see
        :func:`_iter_tag_pairs`).
    """
    merged = {}
    for source in sources:
        for key, value in _iter_tag_pairs(source):
            merged[key] = value
    return dict(sorted(merged.items()))
