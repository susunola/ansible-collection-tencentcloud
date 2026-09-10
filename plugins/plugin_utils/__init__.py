# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""The controller-side import surface for shared helpers.

Every plugin type may import ``module_utils`` — ansible-test's ``import`` test
allows it explicitly — but the reverse is not true: a module or a
``module_utils`` helper that imports ``plugins.plugin_utils`` fails with
"import of ... is not allowed in this context". A helper that modules need
therefore *must* be implemented in ``module_utils``.

This directory is what remains useful after that constraint: one stable,
uniform import path for the non-module plugins (action, callback, connection,
filter, inventory, lookup), so their dependency surface is reviewable in one
place instead of being spread over ``module_utils`` internals. Its files
re-export the shared implementations and hold nothing else today; genuine
controller-only helpers belong here when they appear.

Layering (a lower layer never imports a higher one):

    module_utils      implementations; importable by every plugin type
      ^
    plugin_utils      controller-side re-export surface; never imported by
      ^               modules or by module_utils
    non-module plugins

See ``README.md`` in this directory for the file inventory and the rules for
adding helpers.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
