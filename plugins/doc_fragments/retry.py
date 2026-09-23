# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment(object):
    DOCUMENTATION = r"""
options:
  retries:
    description:
      - Number of retries for transient SDK failures, applied with
        exponential backoff before the module gives up.
    type: int
    default: 5
"""
