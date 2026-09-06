#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cvm_image_share
short_description: Manage Tencent Cloud CVM image sharing permissions
version_added: "0.14.0"
description:
  - Share a custom CVM image with other Tencent Cloud accounts, or cancel
    existing shares, through the C(cvm.v20170312) API.
  - This module is idempotent. Running it twice leaves the share list
    unchanged and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) (default) shares the image with every account in
        O(account_ids) that is not already shared.
      - C(absent) cancels sharing with the accounts in O(account_ids) that
        are currently shared, leaving other shares in place.
    type: str
    choices: [present, absent]
    default: present
  image_id:
    description:
      - ID of the custom image, e.g. C(img-xxxxxxxx). The image must be in
        the C(NORMAL) state.
    type: str
    required: true
  account_ids:
    description:
      - Root account IDs to share the image with, e.g. C(103849387508).
        An account ID is different from a QQ number.
      - A custom image can be shared with at most 500 accounts, and sharing
        is only supported with accounts in the same region.
    type: list
    elements: str
    required: true
  retries:
    description: Number of retries for transient SDK failures.
    type: int
    default: 5
  waiter_delay:
    description: Seconds to wait between state-polling attempts.
    type: int
    default: 5
  waiter_timeout:
    description: Overall timeout in seconds for state polling.
    type: int
    default: 120
  user_agent:
    description:
      - Value appended to the SDK User-Agent header so API usage can be
        attributed to this collection.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-cvm) package on the controller.
  - Only account-level sharing is managed; global sharing (every account)
    is not supported by this module.
  - Sharing with your own account fails with a platform error.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Share an image with two accounts
  susunola.tencentcloud.cvm_image_share:
    region: ap-guangzhou
    state: present
    image_id: img-xxxxxxxx
    account_ids:
      - "100000000001"
      - "100000000002"

- name: Stop sharing with one account
  susunola.tencentcloud.cvm_image_share:
    region: ap-guangzhou
    state: absent
    image_id: img-xxxxxxxx
    account_ids:
      - "100000000001"
'''

RETURN = r'''
shared_accounts:
  description: The effective list of accounts the image is shared with.
  returned: always
  type: list
  elements: str
changed:
  description: Whether the share list was modified.
  returned: always
  type: bool
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load_cvm():
    from tencentcloud.cvm.v20170312 import models, cvm_client
    return models, cvm_client


def find_shared_accounts(module, client, models, image_id):
    """Return the sorted account IDs the image is currently shared with."""
    request = models.DescribeImageSharePermissionRequest()
    request.ImageId = image_id
    response = module.sdk_call(client.DescribeImageSharePermission, request)
    accounts = []
    for item in response.SharePermissionSet or []:
        account = getattr(item, "AccountId", None) or getattr(item, "Account", None)
        if account:
            accounts.append(str(account))
    return sorted(set(accounts))


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "image_id": {"type": "str", "required": True},
            "account_ids": {"type": "list", "elements": "str", "required": True},
        },
        supports_check_mode=True,
    )
    module.require_sdk()
    p = module.params
    accounts = sorted(set(p["account_ids"]))
    if not accounts:
        module.fail_json(msg="account_ids must not be empty")

    models, cvm_client = _load_cvm()
    client = module.create_client(cvm_client.CvmClient, "cvm.tencentcloudapi.com")
    try:
        current = find_shared_accounts(module, client, models, p["image_id"])

        if p["state"] == "absent":
            to_cancel = sorted(set(accounts) & set(current))
            if not to_cancel:
                module.exit_json(changed=False, shared_accounts=current, msg="Image shares already absent")
            after = sorted(set(current) - set(accounts))
            diff = maybe_diff(module, {"SharedAccounts": current}, {"SharedAccounts": after})
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), shared_accounts=after, msg="Would cancel sharing with {0}".format(to_cancel))
            request = models.ModifyImageSharePermissionRequest()
            request.ImageId = p["image_id"]
            request.AccountIds = to_cancel
            request.Permission = "CANCEL"
            module.sdk_call(client.ModifyImageSharePermission, request)
            module.exit_json(changed=True, **(diff or {}), shared_accounts=after, msg="Cancelled sharing with {0}".format(to_cancel))

        to_share = sorted(set(accounts) - set(current))
        if not to_share:
            module.exit_json(changed=False, shared_accounts=current, msg="Image shares are up to date")
        after = sorted(set(current) | set(to_share))
        diff = maybe_diff(module, {"SharedAccounts": current}, {"SharedAccounts": after})
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), shared_accounts=after, msg="Would share with {0}".format(to_share))
        request = models.ModifyImageSharePermissionRequest()
        request.ImageId = p["image_id"]
        request.AccountIds = to_share
        request.Permission = "SHARE"
        module.sdk_call(client.ModifyImageSharePermission, request)
        module.exit_json(changed=True, **(diff or {}), shared_accounts=after, msg="Shared with {0}".format(to_share))
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
