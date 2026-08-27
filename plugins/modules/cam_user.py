#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cam_user
short_description: Manage Tencent Cloud CAM sub-users
version_added: "0.5.0"
description:
  - Create, update, and delete Tencent Cloud CAM sub-users.
  - This module is idempotent. Running it twice leaves the sub-user unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the sub-user if it does not exist and updates its
        remark, console login flag and tags to match the task.
      - C(absent) deletes the sub-user if it exists. Deleting a sub-user that
        still has API keys fails; delete those keys first.
    type: str
    choices: [present, absent]
    default: present
  name:
    description:
      - Name of the CAM sub-user. Sub-users are matched by name.
    type: str
    required: true
  remark:
    description: Remark (description) of the sub-user.
    type: str
  console_login:
    description:
      - Whether the sub-user can log in to the console.
      - When omitted, the console login flag is not enforced on existing
        sub-users; new sub-users are created without console access.
    type: bool
  password:
    description:
      - Console login password set at creation time. Only applied when the
        sub-user is created and O(console_login=true); changing it on an
        existing sub-user is a no-op.
      - When O(console_login=true) and no password is given, CAM generates a
        random password that is not returned by this module; reset it in the
        CAM console if needed.
    type: str
  tags:
    description:
      - Tags to apply to the sub-user as a dict, for example I(env=prod).
      - Existing tags not listed are removed; listed tags with a different
        value are updated. Requires the C(tencentcloud-sdk-python-tag)
        package and the tag service to be enabled for the account.
      - CAM does not return sub-user tags in its own APIs, so current tags
        are read through the tag service on every C(state=present) run.
    type: dict
    default: {}
  retries:
    description:
      - Maximum number of retry attempts for throttled or transient API
        failures, using exponential backoff with jitter.
    type: int
    default: 5
  waiter_timeout:
    description:
      - Maximum time in seconds to wait for an asynchronous resource to reach
        the desired state.
    type: int
    default: 120
  waiter_delay:
    description: Interval in seconds between state polls while waiting.
    type: int
    default: 5
  user_agent:
    description:
      - User-Agent string sent with API requests.
    type: str
    default: ansible-collection.tencentcloud.cloud
notes:
  - Requires the C(tencentcloud-sdk-python-cam) package on the controller.
  - Tag reconciliation additionally requires C(tencentcloud-sdk-python-tag).
  - CAM is a global service. O(region) is accepted (the shared argument spec
    requires it) but ignored; the global C(cam.tencentcloudapi.com) endpoint
    is used.
  - API keys for the sub-user are never created (C(AddUser) is called with
    C(UseApi=0)), so no secret material appears in the module result.
extends_documentation_fragment: tencentcloud.cloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a CAM sub-user with console access
  tencentcloud.cloud.cam_user:
    region: ap-guangzhou
    state: present
    name: deploy-bot
    remark: CI deployment account
    console_login: true
    password: "{{ vault_cam_user_password }}"
    tags:
      env: prod

- name: Check whether the sub-user would be updated (no changes applied)
  tencentcloud.cloud.cam_user:
    region: ap-guangzhou
    state: present
    name: deploy-bot
    remark: CI deployment account
  check_mode: true

- name: Delete a CAM sub-user
  tencentcloud.cloud.cam_user:
    region: ap-guangzhou
    state: absent
    name: deploy-bot
'''

RETURN = r'''
user:
  description: The sub-user as reported by the CAM ListUsers API after the operation.
  returned: success
  type: dict
  sample:
    Uin: 100000000001
    Name: deploy-bot
    Uid: 2000001
    Remark: CI deployment account
    ConsoleLogin: 1
    CreateTime: "2026-08-26 12:00:00"
'''

from ansible_collections.tencentcloud.cloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.tencentcloud.cloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.tencentcloud.cloud.plugins.module_utils.errors import (
    is_idempotent_success,
)
from ansible_collections.tencentcloud.cloud.plugins.module_utils.tagging import (
    compare_tags,
)


def _load_cam():
    from tencentcloud.cam.v20190116 import models, cam_client
    return models, cam_client


def _load_tag():
    from tencentcloud.tag.v20180813 import models as tag_models, tag_client
    return tag_models, tag_client


def find_user(module, client, models, name):
    """Return the matching sub-user dict or None.

    ListUsers takes no parameters and returns every sub-user of the account,
    so the match is done client-side.
    """
    request = models.ListUsersRequest()
    response = module.sdk_call(client.ListUsers, request)
    for user in response.Data or []:
        if user.Name == name:
            return user._serialize(allow_none=True)
    return None


def _create(module, client, models, name, remark, console_login, password):
    request = models.AddUserRequest()
    request.Name = name
    request.Remark = remark or ""
    request.ConsoleLogin = 1 if console_login else 0
    # Never generate API keys: they would land in the module result.
    request.UseApi = 0
    if console_login and password:
        request.Password = password
    response = module.sdk_call(client.AddUser, request)
    return response.Uin


def _update(module, client, models, name, remark, console_login):
    request = models.UpdateUserRequest()
    request.Name = name
    request.Remark = remark or ""
    if console_login is not None:
        request.ConsoleLogin = 1 if console_login else 0
    module.sdk_call(client.UpdateUser, request)


def _delete(module, client, models, name):
    request = models.DeleteUserRequest()
    request.Name = name
    module.sdk_call(client.DeleteUser, request)


def _current_tags(module, client, tag_models, resource_id, resource_prefix):
    """Read current tags through the tag service (CAM has no tag read API)."""
    request = tag_models.DescribeResourceTagsByResourceIdsRequest()
    request.ServiceType = "cam"
    request.ResourcePrefix = resource_prefix
    request.ResourceIds = [resource_id]
    request.ResourceRegion = module.params["region"]
    response = module.sdk_call(client.DescribeResourceTagsByResourceIds, request)
    tags = []
    for resource_tag in response.Tags or []:
        for tag in resource_tag.Tags or []:
            # Tag service models use TagKey/TagValue; normalize to Key/Value.
            tags.append({"Key": tag.TagKey, "Value": tag.TagValue})
    return tags


def _apply_tags(module, client, tag_models, resource_id, resource_prefix, to_add, to_remove):
    """Reconcile tags through the tag service.

    CAM sub-users are addressed by their Uin with the ``uin`` resource
    prefix; each tag key is processed independently.
    """
    for key, value in sorted(to_add.items()):
        request = tag_models.AttachResourcesTagRequest()
        request.ServiceType = "cam"
        request.ResourceIds = [resource_id]
        request.ResourceRegion = module.params["region"]
        request.ResourcePrefix = resource_prefix
        request.TagKey = key
        request.TagValue = value
        module.sdk_call(client.AttachResourcesTag, request)
    for key in to_remove:
        request = tag_models.DetachResourcesTagRequest()
        request.ServiceType = "cam"
        request.ResourceIds = [resource_id]
        request.ResourceRegion = module.params["region"]
        request.ResourcePrefix = resource_prefix
        request.TagKey = key
        module.sdk_call(client.DetachResourcesTag, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "name": {"type": "str", "required": True},
            "remark": {"type": "str"},
            "console_login": {"type": "bool"},
            "password": {"type": "str", "no_log": True},
            "tags": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    name = module.params["name"]
    remark = module.params["remark"]
    console_login = module.params["console_login"]
    password = module.params["password"]
    tags = module.params["tags"]

    models, cam_client = _load_cam()
    client = module.create_client(cam_client.CamClient, "cam.tencentcloudapi.com")

    try:
        current = find_user(module, client, models, name)

        if state == "absent":
            if current is None:
                module.exit_json(changed=False, msg="CAM user already absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would delete CAM user")
            try:
                _delete(module, client, models, name)
            except Exception as exc:
                if is_idempotent_success(exc):
                    module.exit_json(changed=True, **(diff or {}), msg="CAM user deleted")
                raise
            module.exit_json(changed=True, **(diff or {}), user=None, msg="CAM user deleted")

        # state == present
        desired = {
            "name": name,
            "remark": remark or "",
            "console_login": console_login,
            "tags": tags,
        }
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would create CAM user")
            uin = _create(module, client, models, name, remark, console_login, password)
            created = find_user(module, client, models, name)
            if tags:
                tag_models, tag_client = _load_tag()
                tag_client_instance = module.create_client(
                    tag_client.TagClient, "tag.tencentcloudapi.com"
                )
                if created:
                    uin = created["Uin"]
                _apply_tags(
                    module, tag_client_instance, tag_models,
                    str(uin), "uin", dict(tags), [],
                )
                created = find_user(module, client, models, name)
            module.exit_json(changed=True, **(diff or {}), user=created, msg="CAM user created")

        tag_models, tag_client = _load_tag()
        tag_client_instance = module.create_client(
            tag_client.TagClient, "tag.tencentcloudapi.com"
        )
        current_tags = _current_tags(
            module, tag_client_instance, tag_models, str(current["Uin"]), "uin"
        )

        changes = []
        if (remark or "") != (current.get("Remark") or ""):
            changes.append("remark")
        if console_login is not None and int(bool(console_login)) != int(current.get("ConsoleLogin") or 0):
            changes.append("console_login")
        tags_equal, to_add, to_remove = compare_tags(tags, current_tags)
        if not tags_equal:
            changes.append("tags")

        if not changes:
            module.exit_json(changed=False, user=current, msg="CAM user is up to date")

        if module.check_mode:
            module.exit_json(changed=True, **(maybe_diff(module, current, desired) or {}), msg="Would update CAM user")

        if "remark" in changes or "console_login" in changes:
            _update(module, client, models, name, remark, console_login)
        if not tags_equal:
            _apply_tags(
                module, tag_client_instance, tag_models, str(current["Uin"]), "uin", to_add, to_remove
            )

        updated = find_user(module, client, models, name)
        module.exit_json(
            changed=True,
            **(maybe_diff(module, current, desired) or {}),
            user=updated,
            msg="CAM user updated",
        )
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )


def main():
    run_module()


if __name__ == "__main__":
    main()
