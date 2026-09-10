# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Support code shared by every plugin type, not only by modules.

``module_utils`` is the home of module-side helpers: anything that receives an
``AnsibleModule`` (``module.params``, ``module.fail_json``) or that only makes
sense inside a module payload belongs there. This directory is the home of the
layer *below* it: helpers with no ``AnsibleModule`` dependency at all, so they
can be imported unchanged by action, callback, connection, filter, inventory
and lookup plugins as well as by modules.

The split is not cosmetic. ``module_utils`` is documented as a support
directory for *modules*; a lookup or inventory plugin importing from it works
only by accident of the collection being installed on the controller. Keeping
the plugin-agnostic helpers here makes the intended consumers explicit and lets
those plugins depend on a layer that is defined for them.

Layering (a lower layer never imports a higher one):

    plugin_utils      no AnsibleModule, no ansible module payload assumptions
      ^
    module_utils      module-side helpers; may import plugin_utils
      ^
    modules / other plugin types

See ``README.md`` in this directory for the file inventory and the rules for
adding helpers.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
