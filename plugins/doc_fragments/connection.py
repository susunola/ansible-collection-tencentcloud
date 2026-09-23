# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment(object):
    DOCUMENTATION = r"""
options:
  endpoint:
    description:
      - Override the Tencent Cloud API endpoint.
      - Intended for private endpoints, proxies, and integration tests.
    type: str
  timeout:
    description: SDK HTTP request timeout in seconds.
    type: int
    default: 60
"""
