# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Bounded polling loop, for controller-side plugins.

``poll_until`` itself lives in
:mod:`ansible_collections.susunola.tencentcloud.plugins.module_utils.polling`
and is re-exported here. That direction is forced, not chosen:
``module_utils.waiters`` runs the same loop inside a module, and ansible-test's
``import`` test lets module-side code import only ``plugins.module_utils``.
The ``tc_wait`` action plugin imports this path so that the controller-side
import surface stays uniform. See ``README.md``.

Layering: imports ``module_utils.polling``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.module_utils.polling import (
    PollOutcome,
    poll_until,
)

__all__ = ["PollOutcome", "poll_until"]
