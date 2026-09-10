# -*- coding: utf-8 -*-
"""Module-facing entry point for the shared offset/limit paginator.

The loop itself lives in ``plugins/plugin_utils/paging.py`` because the
generated ``_info`` modules and the hand-written inventory plugins page the
same list APIs, and the loop has no ``AnsibleModule`` dependency. ``Paginator``
is re-exported here so the import path emitted by
``scripts/generate_info_modules.py`` (and by every already-committed generated
module) keeps resolving; new code that is not a module should import from
``plugins.plugin_utils.paging`` directly.

``paginate()`` stays here: it is the module-flavoured convenience wrapper and
its signature leads with the module for symmetry with the other module_utils
helpers.

Layering: imports ``plugin_utils.paging``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.plugin_utils.paging import Paginator

__all__ = ["Paginator", "paginate"]


def paginate(module, page_size, build_request, call_api, items_of, total_of):
    """Convenience wrapper that runs a paginator inside a module.

    Uses the module's client (which already applies the retry policy) and
    returns ``(items, total_count)``.
    """
    paginator = Paginator(page_size, build_request, call_api, items_of, total_of)
    return paginator.fetch_all()
