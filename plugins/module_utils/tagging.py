# -*- coding: utf-8 -*-
"""Tag conversion and comparison helpers.

Tencent Cloud list APIs return tags as ``Tag`` objects with ``Key``/``Value``
attributes, while resource modules receive a plain ``dict`` from the user and
write APIs consume ``Tag`` objects. These helpers convert between the two
representations and diff them for idempotency checks.
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
