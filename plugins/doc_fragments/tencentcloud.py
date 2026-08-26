# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment(object):
    DOCUMENTATION = r'''
options:
  secret_id:
    description: Tencent Cloud API secret ID. Falls back to C(TENCENTCLOUD_SECRET_ID).
    type: str
  secret_key:
    description: Tencent Cloud API secret key. Falls back to C(TENCENTCLOUD_SECRET_KEY).
    type: str
  token:
    description: Temporary credential token. Falls back to C(TENCENTCLOUD_TOKEN).
    type: str
  region:
    description: Tencent Cloud region. Falls back to C(TENCENTCLOUD_REGION).
    type: str
    required: true
'''
