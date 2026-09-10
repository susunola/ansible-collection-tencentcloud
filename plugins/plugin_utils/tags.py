# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Tag merging, for controller-side plugins.

``merge_tags`` itself lives in
:mod:`ansible_collections.susunola.tencentcloud.plugins.module_utils.tagging`
and is re-exported here. It is implemented in ``module_utils`` even though the
``tag_merge`` filter plugin is its only consumer today: tag reading and
comparison are one body of semantics, and splitting it across the two
directories would let the two copies drift. The layering rule is
one-directional anyway — module-side code may import only
``plugins.module_utils``, so a helper that a module may later need has to be
born there. See ``README.md``.

Layering: imports ``module_utils.tagging``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.module_utils.tagging import (
    merge_tags,
)

__all__ = ["merge_tags"]
