"""Re-export guard for the ``plugin_utils.inventory`` shim.

The multi-product query layer itself is implemented in
``plugins/module_utils/inventory.py`` and its behaviour is covered by
``tests/unit/plugins/module_utils/test_inventory.py``. This file only guards
the controller-side import path, because the ``tc_inventory`` plugin imports
``plugin_utils.inventory`` and the re-export must not quietly turn into a
second implementation — a copy would let the plugin and the layer it is
supposed to share code with drift apart.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.module_utils import (
    inventory as module_inventory,
)
from ansible_collections.susunola.tencentcloud.plugins.plugin_utils import (
    inventory as plugin_inventory,
)

REEXPORTED = [
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


def test_every_reexported_name_is_the_module_utils_object():
    for name in REEXPORTED:
        assert getattr(plugin_inventory, name) is getattr(module_inventory, name), name


def test_all_matches_the_reexported_names():
    assert sorted(plugin_inventory.__all__) == sorted(REEXPORTED)


def test_source_specs_stay_one_object_across_both_paths():
    """The registry is a mapping, so mutating it through either path is seen."""
    assert plugin_inventory.SOURCE_SPECS is module_inventory.SOURCE_SPECS
    assert plugin_inventory.SOURCE_NAMES is module_inventory.SOURCE_NAMES


def test_the_internal_helpers_are_not_reexported():
    """The shim exposes the API, not the private plumbing."""
    for name in ("_paged", "build_filter", "build_request", "collect_flat",
                 "collect_tke_nodes", "normalize_cvm", "PAGE_SIZE"):
        assert not hasattr(plugin_inventory, name), name
