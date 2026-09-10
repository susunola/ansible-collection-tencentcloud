# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unified offset/limit pagination, for controller-side plugins.

``Paginator`` itself lives in
:mod:`ansible_collections.susunola.tencentcloud.plugins.module_utils.paging`
and is re-exported here. That direction is forced, not chosen: the generated
``_info`` modules import the ``module_utils`` path, and ansible-test's
``import`` test lets module-side code import only ``plugins.module_utils``.
The CVM/CLB/SG/TKE inventory plugins import this path so that the
controller-side import surface stays uniform. See ``README.md``.

Layering: imports ``module_utils.paging``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.module_utils.paging import (
    Paginator,
)

__all__ = ["Paginator"]
