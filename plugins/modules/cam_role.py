#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cam_role
short_description: Manage Tencent Cloud CAM roles
version_added: "0.5.0"
description:
  - Create, update, and delete Tencent Cloud CAM roles.
  - This module is idempotent. Running it twice leaves the role unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the role if it does not exist and updates its
        description, trust policy and tags to match the task.
      - C(absent) deletes the role if it exists.
    type: str
    choices: [present, absent]
    default: present
  role_id:
    description:
      - ID of an existing role, e.g. C(4611686018427904001).
      - When given, the role is matched by ID and O(role_name) is treated as
        the desired name. Roles cannot be renamed by the CAM API, so a
        mismatching name is reported but not enforced.
    type: str
  role_name:
    description:
      - Name of the role. Required when C(state=present) and the role must be
        created. When O(role_id) is not given, the role is matched by name.
    type: str
  description:
    description: Description of the role.
    type: str
  assume_policy_document:
    description:
      - Trust policy document granting the role's principals permission to
        assume it, as a JSON string or a dict. Required when creating a role.
      - The document is compared semantically (parsed JSON), so formatting
        differences do not cause spurious changes.
    type: raw
  tags:
    description:
      - Tags to apply to the role as a dict, for example I(env=prod).
      - Existing tags not listed are removed; listed tags with a different
        value are updated.
      - Reconciled through the CAM-native C(TagRole)/C(UntagRole) APIs.
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
  - CAM is a global service. O(region) is accepted (the shared argument spec
    requires it) but ignored; the global C(cam.tencentcloudapi.com) endpoint
    is used.
extends_documentation_fragment: tencentcloud.cloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a CAM role assumable by CVM
  tencentcloud.cloud.cam_role:
    region: ap-guangzhou
    state: present
    role_name: app-instance-role
    description: Role for application CVM instances
    assume_policy_document:
      version: "2.0"
      statement:
        - action: name/sts:AssumeRole
          effect: allow
          principal:
            service:
              - cvm.qcloud.com
    tags:
      env: prod

- name: Check whether the role would be updated (no changes applied)
  tencentcloud.cloud.cam_role:
    region: ap-guangzhou
    state: present
    role_name: app-instance-role
    description: Role for application CVM instances
  check_mode: true

- name: Delete a CAM role
  tencentcloud.cloud.cam_role:
    region: ap-guangzhou
    state: absent
    role_name: app-instance-role
'''

RETURN = r'''
role:
  description: The role as reported by the CAM DescribeRoleList API after the operation.
  returned: success
  type: dict
  sample:
    RoleId: "4611686018427904001"
    RoleName: app-instance-role
    Description: Role for application CVM instances
    PolicyDocument: '{"version":"2.0","statement":[{"action":"name/sts:AssumeRole","effect":"allow","principal":{"service":["cvm.qcloud.com"]}}]}'
    AddTime: "2026-08-26 12:00:00"
    Tags: []
'''

import json

from ansible_collections.tencentcloud.cloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.tencentcloud.cloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.tencentcloud.cloud.plugins.module_utils.errors import (
    is_idempotent_success,
)
from ansible_collections.tencentcloud.cloud.plugins.module_utils.tagging import (
    compare_tags,
)

ROLE_LIST_PAGE_SIZE = 100


def _load_cam():
    from tencentcloud.cam.v20190116 import models, cam_client
    return models, cam_client


def normalize_document(document):
    """Return the policy document as a parsed JSON value (dict/list).

    Accepts a dict/list or a JSON string. Returns None for absent input so
    callers can distinguish "not given" from an empty document.
    """
    if document is None:
        return None
    if isinstance(document, str):
        return json.loads(document)
    return document


def find_role(module, client, models, role_id, role_name):
    """Return the matching role dict or None.

    DescribeRoleList paginates with 1-based Page/Rp; there is no server-side
    name or ID filter, so the match is done client-side.
    """
    page = 1
    while True:
        request = models.DescribeRoleListRequest()
        request.Page = page
        request.Rp = ROLE_LIST_PAGE_SIZE
        response = module.sdk_call(client.DescribeRoleList, request)
        batch = response.List or []
        for role in batch:
            if role_id and role.RoleId == role_id:
                return role._serialize(allow_none=True)
            if not role_id and role_name and role.RoleName == role_name:
                return role._serialize(allow_none=True)
        total = response.TotalNum or 0
        page += 1
        if not batch or (page - 1) * ROLE_LIST_PAGE_SIZE >= total:
            return None


def build_role_tags(models, tags):
    """Build a list of CAM ``RoleTags`` objects from a normalized dict."""
    if not tags:
        return None
    sdk_tags = []
    for key, value in sorted(tags.items()):
        tag = models.RoleTags()
        tag.Key = key
        tag.Value = value
        sdk_tags.append(tag)
    return sdk_tags


def _create(module, client, models, role_name, description, policy_document, tags):
    request = models.CreateRoleRequest()
    request.RoleName = role_name
    request.PolicyDocument = json.dumps(policy_document)
    request.Description = description or ""
    if tags:
        request.Tags = build_role_tags(models, tags)
    response = module.sdk_call(client.CreateRole, request)
    return response.RoleId


def _update_description(module, client, models, role_id, description):
    request = models.UpdateRoleDescriptionRequest()
    request.RoleId = role_id
    request.Description = description or ""
    module.sdk_call(client.UpdateRoleDescription, request)


def _update_policy_document(module, client, models, role_id, policy_document):
    request = models.UpdateAssumeRolePolicyRequest()
    request.RoleId = role_id
    request.PolicyDocument = json.dumps(policy_document)
    module.sdk_call(client.UpdateAssumeRolePolicy, request)


def _delete(module, client, models, role_id, role_name):
    request = models.DeleteRoleRequest()
    if role_id:
        request.RoleId = role_id
    else:
        request.RoleName = role_name
    module.sdk_call(client.DeleteRole, request)


def _tag_role(module, client, models, role_id, tags):
    request = models.TagRoleRequest()
    request.RoleId = role_id
    request.Tags = build_role_tags(models, tags)
    module.sdk_call(client.TagRole, request)


def _untag_role(module, client, models, role_id, keys):
    request = models.UntagRoleRequest()
    request.RoleId = role_id
    request.TagKeys = list(keys)
    module.sdk_call(client.UntagRole, request)


def _documents_equal(current_document, desired_document):
    """Compare trust policies semantically (parsed JSON)."""
    try:
        current = normalize_document(current_document)
    except ValueError:
        current = current_document
    return current == desired_document


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "role_id": {"type": "str"},
            "role_name": {"type": "str"},
            "description": {"type": "str"},
            "assume_policy_document": {"type": "raw"},
            "tags": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    role_id = module.params["role_id"]
    role_name = module.params["role_name"]
    description = module.params["description"]
    assume_policy_document = module.params["assume_policy_document"]
    tags = module.params["tags"]

    if not role_id and not role_name:
        module.fail_json(msg="role_id or role_name is required")

    models, cam_client = _load_cam()
    client = module.create_client(cam_client.CamClient, "cam.tencentcloudapi.com")

    try:
        desired_document = normalize_document(assume_policy_document)
    except ValueError:
        module.fail_json(msg="assume_policy_document is not valid JSON")

    try:
        current = find_role(module, client, models, role_id, role_name)

        if state == "absent":
            if current is None:
                module.exit_json(changed=False, msg="CAM role already absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would delete CAM role")
            try:
                _delete(module, client, models, current["RoleId"], None)
            except Exception as exc:
                if is_idempotent_success(exc):
                    module.exit_json(changed=True, **(diff or {}), msg="CAM role deleted")
                raise
            module.exit_json(changed=True, **(diff or {}), role=None, msg="CAM role deleted")

        # state == present
        desired = {
            "role_name": role_name,
            "description": description or "",
            "assume_policy_document": desired_document,
            "tags": tags,
        }
        if current is None:
            if not role_name:
                module.fail_json(msg="role_name is required to create a CAM role")
            if desired_document is None:
                module.fail_json(msg="assume_policy_document is required to create a CAM role")
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would create CAM role")
            new_role_id = _create(module, client, models, role_name, description, desired_document, tags)
            created = find_role(module, client, models, new_role_id, None)
            module.exit_json(changed=True, **(diff or {}), role=created, msg="CAM role created")

        current_role_id = current["RoleId"]
        changes = []
        if (description or "") != (current.get("Description") or ""):
            changes.append("description")
        if desired_document is not None and not _documents_equal(
            current.get("PolicyDocument"), desired_document
        ):
            changes.append("assume_policy_document")
        tags_equal, to_add, to_remove = compare_tags(tags, current.get("Tags") or [])
        if not tags_equal:
            changes.append("tags")

        if not changes:
            module.exit_json(changed=False, role=current, msg="CAM role is up to date")

        if module.check_mode:
            module.exit_json(changed=True, **(maybe_diff(module, current, desired) or {}), msg="Would update CAM role")

        if "description" in changes:
            _update_description(module, client, models, current_role_id, description)
        if "assume_policy_document" in changes:
            _update_policy_document(module, client, models, current_role_id, desired_document)
        if not tags_equal:
            if to_add:
                _tag_role(module, client, models, current_role_id, to_add)
            if to_remove:
                _untag_role(module, client, models, current_role_id, to_remove)

        updated = find_role(module, client, models, current_role_id, None)
        module.exit_json(
            changed=True,
            **(maybe_diff(module, current, desired) or {}),
            role=updated,
            msg="CAM role updated",
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
