#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: security_group
short_description: Manage Tencent Cloud security groups
version_added: "0.3.0"
description:
  - Create, update, and delete Tencent Cloud security groups.
  - This module is idempotent. Running it twice leaves the resource unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the security group if it does not exist and updates
        its name, description and tags to match the task.
      - C(absent) deletes the security group if it exists. Deleting a group
        that is still associated with resources fails with a C(ResourceInUse)
        error; release those associations first.
    type: str
    choices: [present, absent]
    default: present
  name:
    description:
      - Name of the security group. Required when C(state=present).
      - When C(security_group_id) is not given, the group is matched by name.
    type: str
  security_group_id:
    description:
      - ID of an existing security group, e.g. C(sg-xxxxxxxx).
      - When given, the module operates on that group and C(name) is used as
        the desired name to enforce.
    type: str
  description:
    description: Description of the security group.
    type: str
  project_id:
    description:
      - Project ID the security group belongs to. Only applied at creation;
        changing it after creation is a no-op (the API does not support it).
    type: int
    default: 0
  tags:
    description:
      - Tags to apply to the security group as a dict, for example
        I(env=prod).
      - Existing tags not listed are removed; listed tags with a different
        value are updated. Requires the C(tencentcloud-sdk-python-tag) package
        and the tag service to be enabled for the account.
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
    default: ansible-collection/tencentcloud.cloud
notes:
  - Requires the C(tencentcloud-sdk-python-vpc) package on the controller.
  - Tag reconciliation additionally requires C(tencentcloud-sdk-python-tag).
  - Uses the C(vpc.tencentcloudapi.com) endpoint by default.
extends_documentation_fragment: tencentcloud.cloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a security group
  tencentcloud.cloud.security_group:
    region: ap-guangzhou
    state: present
    name: web-sg
    description: Web tier security group
    tags:
      env: prod
      tier: web

- name: Check whether the group would be updated (no changes applied)
  tencentcloud.cloud.security_group:
    region: ap-guangzhou
    state: present
    name: web-sg
    description: Web tier security group
  check_mode: true

- name: Delete a security group
  tencentcloud.cloud.security_group:
    region: ap-guangzhou
    state: absent
    name: web-sg
'''

RETURN = r'''
security_group:
  description: The security group as reported by the API after the operation.
  returned: success
  type: dict
  sample:
    SecurityGroupId: sg-xxxxxxxx
    SecurityGroupName: web-sg
    SecurityGroupDesc: Web tier security group
    CreatedTime: "2026-08-26 12:00:00"
    TagSet: []
'''

from ansible_collections.tencentcloud.cloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.tencentcloud.cloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.tencentcloud.cloud.plugins.module_utils.errors import (
    is_idempotent_success,
)
from ansible_collections.tencentcloud.cloud.plugins.module_utils.tagging import (
    build_sdk_tags,
    compare_tags,
)


def _load_vpc():
    from tencentcloud.vpc.v20170312 import models, vpc_client
    return models, vpc_client


def _load_tag():
    from tencentcloud.tag.v20180813 import models as tag_models, tag_client
    return tag_models, tag_client


def build_describe_request(models, name, security_group_id):
    request = models.DescribeSecurityGroupsRequest()
    # The VPC API accepts Limit/Offset as strings only.
    request.Limit = "100"
    if security_group_id:
        request.SecurityGroupIds = [security_group_id]
    if name:
        name_filter = models.Filter()
        name_filter.Name = "security-group-name"
        name_filter.Values = [name]
        request.Filters = [name_filter]
    return request


def _first(collection):
    return collection[0] if collection else None


def find_security_group(module, client, models, name, security_group_id):
    """Return the matching security group dict or None."""
    request = build_describe_request(models, name, security_group_id)
    response = module.sdk_call(client.DescribeSecurityGroups, request)
    group = _first(response.SecurityGroupSet or [])
    if group is None:
        return None
    return group._serialize(allow_none=True)


def _update_attributes(module, client, models, group_id, name, description):
    request = models.ModifySecurityGroupAttributeRequest()
    request.SecurityGroupId = group_id
    request.SecurityGroupName = name
    request.SecurityGroupDesc = description
    module.sdk_call(client.ModifySecurityGroupAttribute, request)


def _apply_tags(module, client, tag_models, group_id, to_add, to_remove):
    """Reconcile tags through the tag service.

    The tag service model differs from the VPC model: resources are addressed
    by a plural ``ResourceIds`` list and tags by ``TagKey``/``TagValue``.
    Each tag key is processed independently.
    """
    for key, value in sorted(to_add.items()):
        request = tag_models.AttachResourcesTagRequest()
        request.ServiceType = "vpc"
        request.ResourceIds = [group_id]
        request.ResourceRegion = module.params["region"]
        request.ResourcePrefix = "security-group"
        request.TagKey = key
        request.TagValue = value
        module.sdk_call(client.AttachResourcesTag, request)
    for key in to_remove:
        request = tag_models.DetachResourcesTagRequest()
        request.ServiceType = "vpc"
        request.ResourceIds = [group_id]
        request.ResourceRegion = module.params["region"]
        request.ResourcePrefix = "security-group"
        request.TagKey = key
        module.sdk_call(client.DetachResourcesTag, request)


def _create(module, client, models, name, description, project_id, tags):
    request = models.CreateSecurityGroupRequest()
    request.GroupName = name
    request.GroupDescription = description or ""
    # The VPC API accepts ProjectId as a string only.
    request.ProjectId = str(project_id)
    if tags:
        request.Tags = build_sdk_tags(models, tags)
    response = module.sdk_call(client.CreateSecurityGroup, request)
    return response.SecurityGroup._serialize(allow_none=True)


def _delete(module, client, models, group_id):
    request = models.DeleteSecurityGroupRequest()
    request.SecurityGroupId = group_id
    module.sdk_call(client.DeleteSecurityGroup, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "name": {"type": "str"},
            "security_group_id": {"type": "str"},
            "description": {"type": "str"},
            "project_id": {"type": "int", "default": 0},
            "tags": {"type": "dict", "default": {}},
        },
        required_if=[("state", "present", ["name"])],
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    name = module.params["name"]
    security_group_id = module.params["security_group_id"]
    description = module.params["description"]
    project_id = module.params["project_id"]
    tags = module.params["tags"]

    if state == "absent" and not name and not security_group_id:
        module.fail_json(msg="name or security_group_id is required when state=absent")

    models, vpc_client = _load_vpc()
    client = module.create_client(vpc_client.VpcClient, "vpc.tencentcloudapi.com")

    try:
        current = find_security_group(module, client, models, name, security_group_id)

        if state == "absent":
            if current is None:
                module.exit_json(changed=False, msg="Security group already absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would delete security group")
            try:
                _delete(module, client, models, current["SecurityGroupId"])
            except Exception as exc:
                if is_idempotent_success(exc):
                    module.exit_json(changed=True, **(diff or {}), msg="Security group deleted")
                raise
            module.exit_json(changed=True, **(diff or {}), security_group=None, msg="Security group deleted")

        # state == present
        desired = {"name": name, "description": description or "", "tags": tags}
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would create security group")
            created = _create(module, client, models, name, description, project_id, tags)
            module.exit_json(changed=True, **(diff or {}), security_group=created, msg="Security group created")

        group_id = current["SecurityGroupId"]
        current_name = current.get("SecurityGroupName")
        current_desc = current.get("SecurityGroupDesc")
        current_tags = current.get("TagSet") or []

        changes = []
        if current_name != name:
            changes.append("name")
        if (description or "") != (current_desc or ""):
            changes.append("description")
        tags_equal, to_add, to_remove = compare_tags(tags, current_tags)
        if not tags_equal:
            changes.append("tags")

        if not changes:
            module.exit_json(changed=False, security_group=current, msg="Security group is up to date")

        if module.check_mode:
            module.exit_json(changed=True, **(maybe_diff(module, current, desired) or {}), msg="Would update security group")

        if "name" in changes or "description" in changes:
            _update_attributes(module, client, models, group_id, name, description or "")
        if not tags_equal:
            tag_models, tag_client = _load_tag()
            tag_client_instance = module.create_client(
                tag_client.TagClient, "tag.tencentcloudapi.com"
            )
            _apply_tags(module, tag_client_instance, tag_models, group_id, to_add, to_remove)

        updated = find_security_group(module, client, models, None, group_id)
        module.exit_json(
            changed=True,
            **(maybe_diff(module, current, desired) or {}),
            security_group=updated,
            msg="Security group updated",
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
