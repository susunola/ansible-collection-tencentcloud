"""Re-export guard for the ``plugin_utils.tags`` shim.

``merge_tags`` is implemented in ``plugins/module_utils/tagging.py`` and its
behaviour is covered by ``tests/unit/plugins/module_utils/test_tagging.py``.
This file only guards the controller-side import path, because the ``tag_merge``
filter imports ``plugin_utils.tags`` and the re-export must not quietly turn
into a second implementation.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.module_utils import tagging as module_tagging
from ansible_collections.susunola.tencentcloud.plugins.plugin_utils import tags as plugin_tags


def test_merge_tags_is_the_module_utils_function():
    """One function, two import paths: the shim must not define a second copy."""
    assert plugin_tags.merge_tags is module_tagging.merge_tags


def test_the_shim_exports_exactly_the_merger():
    """The other tag readers stay module-side until a plugin needs them."""
    assert plugin_tags.__all__ == ["merge_tags"]
    assert not hasattr(plugin_tags, "normalize_tags")
    assert not hasattr(plugin_tags, "tags_from_sdk")
    assert not hasattr(plugin_tags, "compare_tags")
