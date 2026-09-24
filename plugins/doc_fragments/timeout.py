# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment(object):
    DOCUMENTATION = r"""
options:
  timeout:
    description:
      - SDK HTTP request timeout in seconds.
      - Increase it for slow control-plane calls. It bounds a single API
        request and does not affect how long the module polls for a
        resource to converge.
    type: int
    default: 60
"""
