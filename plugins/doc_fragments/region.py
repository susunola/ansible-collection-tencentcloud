# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment(object):
    DOCUMENTATION = r"""
options:
  region:
    description:
      - Tencent Cloud region.
      - Falls back to C(TENCENTCLOUD_REGION), then to the C(region) key of
        the selected O(profile) section in
        C(~/.tencentcloud/default.configure).
      - Required unless one of those fallbacks provides it.
    type: str
"""
