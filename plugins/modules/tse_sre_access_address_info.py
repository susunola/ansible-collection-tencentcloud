#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_sre_access_address_info
short_description: Gather Tencent Cloud TSE registry-engine access addresses
version_added: "0.14.0"
description: Returns client, console, Apollo environment and Polaris limiter access endpoints and bandwidth metadata.
options:
  instance_id:
    description:
      - TSE engine instance ID.
    type: str
    required: true
  vpc_id:
    description:
      - VPC used to resolve an intranet endpoint.
    type: str
  subnet_id:
    description:
      - Subnet used to resolve an intranet endpoint.
    type: str
  workload:
    description:
      - Additional engine workload such as pushgateway or polaris-limiter.
    type: str
  engine_region:
    description:
      - Deployment region override for the queried endpoint.
    type: str
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
attributes:
  check_mode:
    description:
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  idempotency:
    description:
      - Read-only, so every run returns the current state and never changes
        the target, and a repeated run reports C(changed=false).
    support: full
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_sre_access_address_info:
    instance_id: ins-xxxxxxxx
  register: engine_access
"""
RETURN = r"""
access_address: {description: 'Engine client, console, environment, limiter and bandwidth endpoint metadata.', type: dict, returned: always}
request_id: {description: Tencent Cloud request ID., type: str, returned: always}
"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def request(models, p):
    r = models.DescribeSREInstanceAccessAddressRequest()
    r.InstanceId, r.VpcId, r.SubnetId, r.Workload, r.EngineRegion = (
        p["instance_id"],
        p.get("vpc_id"),
        p.get("subnet_id"),
        p.get("workload"),
        p.get("engine_region"),
    )
    return r


def serialize_response(response):
    value = response._serialize(allow_none=True) if hasattr(response, "_serialize") else {}
    value.pop("RequestId", None)
    return value


def run_module():
    spec = {"instance_id": {"required": True}, "vpc_id": {}, "subnet_id": {}, "workload": {}, "engine_region": {}}
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeSREInstanceAccessAddress, request(models, p))
        module.exit_json(changed=False, access_address=serialize_response(response), request_id=getattr(response, "RequestId", None))
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
