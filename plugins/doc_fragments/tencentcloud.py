# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment(object):
    DOCUMENTATION = r'''
options:
  secret_id:
    description:
      - Tencent Cloud API secret ID.
      - Falls back to C(TENCENTCLOUD_SECRET_ID), then to the selected
        O(profile) section in C(~/.tencentcloud/default.configure).
    type: str
  secret_key:
    description:
      - Tencent Cloud API secret key.
      - Falls back to C(TENCENTCLOUD_SECRET_KEY), then to the selected
        O(profile) section in C(~/.tencentcloud/default.configure).
    type: str
  token:
    description: Temporary credential token. Falls back to C(TENCENTCLOUD_TOKEN).
    type: str
  role_arn:
    description:
      - CAM role ARN to assume via the STS AssumeRole API before calling any
        other service, for example C(qcs::cam::uin/1000000000:roleName/MyRole).
      - When set, the module exchanges O(secret_id)/O(secret_key) for
        temporary credentials bound to this role.
      - Falls back to C(TENCENTCLOUD_ROLE_ARN).
    type: str
  role_session_name:
    description: Session name recorded for the assumed role.
    type: str
    default: ansible-tencentcloud
  role_session_duration:
    description: Validity of the temporary role credentials in seconds.
    type: int
    default: 7200
  profile:
    description:
      - Name of the TCCLI profile section in
        C(~/.tencentcloud/default.configure) to read credentials and region
        from, for example C(default) or C(prod).
      - A profile only supplies values not given as module parameters or
        environment variables; precedence is parameter > environment
        variable > profile section.
      - Falls back to C(TENCENTCLOUD_PROFILE); when neither is set the
        C(default) section is used.
    type: str
    version_added: "0.5.0"
  region:
    description:
      - Tencent Cloud region.
      - Falls back to C(TENCENTCLOUD_REGION), then to the C(region) key of
        the selected O(profile) section in
        C(~/.tencentcloud/default.configure).
      - Required unless one of those fallbacks provides it.
    type: str
  endpoint:
    description:
      - Override the Tencent Cloud API endpoint.
      - Intended for private endpoints, proxies, and integration tests.
    type: str
  timeout:
    description: SDK HTTP request timeout in seconds.
    type: int
    default: 60
'''
