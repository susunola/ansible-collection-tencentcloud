# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment(object):
    DOCUMENTATION = r"""
options:
  waiter_delay:
    description:
      - Seconds to wait between state-polling attempts while waiting for a
        resource to reach its desired state.
    type: int
    default: 5
  waiter_timeout:
    description:
      - Overall timeout in seconds for state polling before the module gives
        up and fails the task.
    type: int
    default: 120
"""
