#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: organization_member_identity
short_description: Reconcile Tencent Cloud Organization member identities
version_added: "0.14.0"
description: Adds and removes organization access identities until a member has exactly the requested identity IDs.
options:
  member_uin: {type: int, required: true, description: Organization member UIN.}
  identity_ids: {type: list, elements: int, required: true, description: Complete desired set of identity IDs.}
  purge: {type: bool, default: true, description: Remove identities not listed in C(identity_ids).}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.organization_member_identity:
    member_uin: 100000000001
    identity_ids: [1, 12]
'''
RETURN = r'''identity_ids: {description: Resulting identity ID set., type: list, elements: int, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.organization.v20210331 import models, organization_client
    return models, organization_client


def describe_request(models, member_uin, offset=0):
    request = models.DescribeOrganizationMemberAuthIdentitiesRequest()
    request.MemberUin, request.Offset, request.Limit = member_uin, offset, 50
    return request


def create_request(models, member_uin, identity_ids):
    request = models.CreateOrganizationMemberAuthIdentityRequest()
    request.MemberUins, request.IdentityIds = [member_uin], sorted(identity_ids)
    return request


def delete_request(models, member_uin, identity_id):
    request = models.DeleteOrganizationMemberAuthIdentityRequest()
    request.MemberUin, request.IdentityId = member_uin, identity_id
    return request


def fetch(module, client, models, member_uin):
    offset, result = 0, []
    while True:
        response = module.sdk_call(client.DescribeOrganizationMemberAuthIdentities, describe_request(models, member_uin, offset)); items = list(response.Items or [])
        result.extend(int(item.IdentityId) for item in items); offset += len(items)
        if not items or offset >= int(response.Total or 0): return sorted(set(result))


def run_module():
    module = TencentCloudModule(argument_spec={"member_uin": {"type": "int", "required": True}, "identity_ids": {"type": "list", "elements": "int", "required": True}, "purge": {"type": "bool", "default": True}}, supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.OrganizationClient, "organization.tencentcloudapi.com")
    try:
        current = fetch(module, client, models, p["member_uin"]); requested = sorted(set(p["identity_ids"]))
        additions = sorted(set(requested) - set(current)); removals = sorted(set(current) - set(requested)) if p["purge"] else []
        target = sorted((set(current) | set(additions)) - set(removals))
        if current == target: module.exit_json(changed=False, identity_ids=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            if additions: module.sdk_call(client.CreateOrganizationMemberAuthIdentity, create_request(models, p["member_uin"], additions))
            for identity_id in removals: module.sdk_call(client.DeleteOrganizationMemberAuthIdentity, delete_request(models, p["member_uin"], identity_id))
            current = fetch(module, client, models, p["member_uin"])
        module.exit_json(changed=True, **(diff or {}), identity_ids=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
