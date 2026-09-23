# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""TCCLI credential-profile resolution, for controller-side plugins.

The reader itself lives in
:mod:`ansible_collections.susunola.tencentcloud.plugins.module_utils.client`
and is re-exported here. That direction is forced, not chosen: ansible-test's
``import`` test lets module-side code import only ``plugins.module_utils``, so
anything a module also needs cannot be implemented under ``plugin_utils``.
The lookup, inventory and connection plugins import this path so that the
controller-side import surface stays uniform. See ``README.md``.

Layering: imports ``module_utils.client``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.module_utils.client import (
    load_profile,
)

__all__ = ["load_profile"]
