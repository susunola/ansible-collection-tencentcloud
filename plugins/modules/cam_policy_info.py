#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cam_policy_info
short_description: Gather information about Tencent Cloud CAM policies
version_added: "0.5.0"
description:
  - Returns CAM policies visible to the account.
  - With O(policy_id) the policy is fetched directly with GetPolicy.
  - Otherwise policies are listed with the page-based ListPolicies API;
    O(policy_name) filters the result client-side by exact name.
options:
  policy_id:
    description: Return only the policy with this ID.
    type: int
  policy_name:
    description: Return only policies with this exact name.
    type: str
  scope:
    description:
      - Policy scope passed to ListPolicies. C(all) returns custom and preset
        policies, C(local) only custom policies, C(qcs) only preset policies.
      - Ignored when O(policy_id) is given.
    type: str
    choices: [all, local, qcs]
    default: all
  page_size:
    description: Number of results requested per API call (maximum 200).
    type: int
    default: 100
notes:
  - Requires the C(tencentcloud-sdk-python-cam) package on the controller.
  - CAM is a global service. O(region) is accepted but ignored; the global
    C(cam.tencentcloudapi.com) endpoint is used.
extends_documentation_fragment: tencentcloud.cloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: List all custom CAM policies
  tencentcloud.cloud.cam_policy_info:
    region: ap-guangzhou
    scope: local

- name: Find a policy by name
  tencentcloud.cloud.cam_policy_info:
    region: ap-guangzhou
    policy_name: app-read-only
'''

RETURN = r'''
policies:
  description: Matching CAM policies.
  returned: always
  type: list
  elements: dict
total_count:
  description: Number of policies returned.
  returned: always
  type: int
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.tencentcloud.cloud.plugins.module_utils.tencentcloud import (
    create_client_profile, create_credential, sdk_call, serialize_sdk_object,
    tencentcloud_argument_spec,
)

SCOPE_MAP = {"all": "All", "local": "Local", "qcs": "QCS"}


def build_request(models, scope, keyword, page, page_size):
    request = models.ListPoliciesRequest()
    request.Scope = SCOPE_MAP[scope]
    if keyword:
        request.Keyword = keyword
    request.Page = page
    request.Rp = page_size
    return request


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "policy_id": {"type": "int"},
        "policy_name": {"type": "str"},
        "scope": {"type": "str", "choices": ["all", "local", "qcs"], "default": "all"},
        "page_size": {"type": "int", "default": 100},
    })
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )
    try:
        from tencentcloud.cam.v20190116 import models, cam_client
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python package with CAM support is required.")

    client = cam_client.CamClient(
        create_credential(module), module.params["region"],
        create_client_profile(module, "cam.tencentcloudapi.com"),
    )
    policy_id = module.params["policy_id"]
    policy_name = module.params["policy_name"]

    if policy_id is not None:
        request = models.GetPolicyRequest()
        request.PolicyId = policy_id
        response = sdk_call(module, client.GetPolicy, request)
        policy = serialize_sdk_object(response)
        policy.pop("RequestId", None)
        policy["PolicyId"] = policy_id
        module.exit_json(changed=False, policies=[policy], total_count=1)

    policies = []
    page = 1
    while True:
        request = build_request(models, module.params["scope"], policy_name, page, module.params["page_size"])
        response = sdk_call(module, client.ListPolicies, request)
        batch = response.List or []
        for policy in batch:
            # Keyword is a fuzzy match server-side; enforce exact name here.
            if policy_name and policy.PolicyName != policy_name:
                continue
            policies.append(serialize_sdk_object(policy))
        total = response.TotalNum or 0
        page += 1
        if not batch or (page - 1) * module.params["page_size"] >= total:
            break
    module.exit_json(changed=False, policies=policies, total_count=len(policies))


def main():
    run_module()


if __name__ == "__main__":
    main()
