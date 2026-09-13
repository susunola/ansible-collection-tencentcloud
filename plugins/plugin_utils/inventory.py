# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Shared multi-product inventory layer, for controller-side plugins.

The implementation lives in
:mod:`ansible_collections.susunola.tencentcloud.plugins.module_utils.inventory`
and is re-exported here. That direction is forced, not chosen: ansible-test's
``import`` test lets module-side code import only ``plugins.module_utils``, so
anything a module might need cannot be implemented under ``plugin_utils``.
The ``tc_inventory`` plugin imports this path so that the controller-side
import surface stays uniform. See ``README.md``.

``PAGE_SIZE`` is deliberately **not** re-exported: a re-exported constant is a
separate binding, so rebinding ``plugin_utils.inventory.PAGE_SIZE`` would
silently have no effect on the reader. Patch
``module_utils.inventory.PAGE_SIZE`` instead. ``SOURCE_SPECS`` *is*
re-exported because it is a mapping: mutating it through either path affects
one object.

Layering: imports ``module_utils.inventory``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.module_utils.inventory import (
    SOURCE_NAMES,
    SOURCE_SPECS,
    InventorySourceError,
    LITERAL_HOSTNAMES,
    SourceSpec,
    build_cache_key,
    build_client,
    collect_source,
    describe_entry,
    hostname_of,
    load_models,
    merge_entries,
    normalize,
    resolve_credentials,
    resolve_sources,
    serialize,
    tag_mapping,
)

__all__ = [
    "InventorySourceError",
    "LITERAL_HOSTNAMES",
    "SOURCE_NAMES",
    "SOURCE_SPECS",
    "SourceSpec",
    "build_cache_key",
    "build_client",
    "collect_source",
    "describe_entry",
    "hostname_of",
    "load_models",
    "merge_entries",
    "normalize",
    "resolve_credentials",
    "resolve_sources",
    "serialize",
    "tag_mapping",
]
