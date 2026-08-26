#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cam_policy
short_description: Manage Tencent Cloud CAM policies
version_added: "0.5.0"
description:
  - Create, update, and delete Tencent Cloud CAM custom policies.
  - This module is idempotent. Running it twice leaves the policy unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the policy if it does not exist and updates its
        description, policy document and tags to match the task.
      - C(absent) deletes the policy if it exists. Deleting a policy that is
        still attached to users, groups or roles fails; detach it first.
    type: str
    choices: [present, absent]
    default: present
  policy_id:
    description:
      - ID of an existing policy. When given, the policy is looked up with
        C(GetPolicy) and O(policy_name) is treated as the desired name.
    type: int
  policy_name:
    description:
      - Name of the policy. Required when C(state=present) and the policy
        must be created. When O(policy_id) is not given, the policy is
        matched by name within the O(type) scope.
    type: str
  description:
    description: Description of the policy.
    type: str
  policy_document:
    description:
      - Policy document as a JSON string or a dict. Required when creating a
        policy.
      - The document is compared semantically (parsed JSON), so formatting
        differences do not cause spurious changes.
    type: raw
  type:
    description:
      - Scope used when matching a policy by name. C(custom) matches
        user-created policies (CAM scope C(Local)); C(preset) matches
        Tencent-managed preset policies (CAM scope C(QCS)).
      - Only custom policies can be created, updated or deleted; preset
        policies are read-only.
    type: str
    choices: [custom, preset]
    default: custom
  tags:
    description:
      - Tags to apply to the policy as a dict, for example I(env=prod).
      - Existing tags not listed are removed; listed tags with a different
        value are updated. Requires the C(tencentcloud-sdk-python-tag)
        package and the tag service to be enabled for the account.
      - Tags given at creation are passed to C(CreatePolicy) directly; tag
        changes on an existing policy go through the tag service with
        service type C(cam) and resource prefix C(policy).
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
  - Requires the C(tencentcloud-sdk-python-cam) package on the controller.
  - Tag reconciliation additionally requires C(tencentcloud-sdk-python-tag).
  - CAM is a global service. O(region) is accepted (the shared argument spec
    requires it) but ignored; the global C(cam.tencentcloudapi.com) endpoint
    is used.
extends_documentation_fragment: tencentcloud.cloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a custom CAM policy
  tencentcloud.cloud.cam_policy:
    region: ap-guangzhou
    state: present
    policy_name: app-read-only
    description: Read-only access to the app COS bucket
    policy_document:
      version: "2.0"
      statement:
        - action:
            - name/cos:GetObject
          effect: allow
          resource:
            - qcs::cos:ap-guangzhou:uid/1000000000:app-bucket-1000000000/*
    tags:
      env: prod

- name: Check whether the policy would be updated (no changes applied)
  tencentcloud.cloud.cam_policy:
    region: ap-guangzhou
    state: present
    policy_name: app-read-only
    description: Read-only access to the app COS bucket
  check_mode: true

- name: Delete a custom CAM policy
  tencentcloud.cloud.cam_policy:
    region: ap-guangzhou
    state: absent
    policy_name: app-read-only
'''

RETURN = r'''
policy:
  description: The policy as reported by the CAM API after the operation.
  returned: success
  type: dict
  sample:
    PolicyId: 1000001
    PolicyName: app-read-only
    Description: Read-only access to the app COS bucket
    Type: 1
    AddTime: "2026-08-26 12:00:00"
    Tags: []
'''

import json

from ansible_collections.tencentcloud.cloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.tencentcloud.cloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.tencentcloud.cloud.plugins.module_utils.errors import (
    is_idempotent_success,
    is_not_found,
)
from ansible_collections.tencentcloud.cloud.plugins.module_utils.tagging import (
    build_sdk_tags,
    compare_tags,
)

POLICY_LIST_PAGE_SIZE = 100
POLICY_TYPE_CUSTOM = 1
SCOPE_BY_TYPE = {"custom": "Local", "preset": "QCS"}


def _load_cam():
    from tencentcloud.cam.v20190116 import models, cam_client
    return models, cam_client


def _load_tag():
    from tencentcloud.tag.v20180813 import models as tag_models, tag_client
    return tag_models, tag_client


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


def find_policy(module, client, models, policy_id, policy_name, scope):
    """Return the matching policy dict or None.

    With a policy ID the policy is fetched with GetPolicy; a not-found error
    maps to None. By name the policy is matched client-side from the
    page-based ListPolicies API (1-based Page/Rp).
    """
    if policy_id is not None:
        request = models.GetPolicyRequest()
        request.PolicyId = policy_id
        try:
            response = module.sdk_call(client.GetPolicy, request)
        except Exception as exc:
            if is_not_found(exc):
                return None
            raise
        policy = response._serialize(allow_none=True)
        policy.pop("RequestId", None)
        # GetPolicy does not echo the ID back.
        policy["PolicyId"] = policy_id
        return policy

    page = 1
    while True:
        request = models.ListPoliciesRequest()
        request.Scope = scope
        request.Keyword = policy_name
        request.Page = page
        request.Rp = POLICY_LIST_PAGE_SIZE
        response = module.sdk_call(client.ListPolicies, request)
        batch = response.List or []
        for policy in batch:
            if policy.PolicyName == policy_name:
                return policy._serialize(allow_none=True)
        total = response.TotalNum or 0
        page += 1
        if not batch or (page - 1) * POLICY_LIST_PAGE_SIZE >= total:
            return None


def _create(module, client, models, policy_name, description, policy_document, tags):
    request = models.CreatePolicyRequest()
    request.PolicyName = policy_name
    request.PolicyDocument = json.dumps(policy_document)
    request.Description = description or ""
    if tags:
        request.Tags = build_sdk_tags(models, tags)
    response = module.sdk_call(client.CreatePolicy, request)
    return response.PolicyId


def _update(module, client, models, policy_id, policy_name, description, policy_document, changes):
    request = models.UpdatePolicyRequest()
    request.PolicyId = policy_id
    if "policy_name" in changes:
        request.PolicyName = policy_name
    if "description" in changes:
        request.Description = description or ""
    if "policy_document" in changes:
        request.PolicyDocument = json.dumps(policy_document)
    module.sdk_call(client.UpdatePolicy, request)


def _delete(module, client, models, policy_id):
    request = models.DeletePolicyRequest()
    request.PolicyId = [policy_id]
    module.sdk_call(client.DeletePolicy, request)


def _apply_tags(module, client, tag_models, resource_id, to_add, to_remove):
    """Reconcile tags through the tag service.

    CAM policies are addressed by their numeric policy ID with the ``policy``
    resource prefix; each tag key is processed independently.
    """
    for key, value in sorted(to_add.items()):
        request = tag_models.AttachResourcesTagRequest()
        request.ServiceType = "cam"
        request.ResourceIds = [resource_id]
        request.ResourceRegion = module.params["region"]
        request.ResourcePrefix = "policy"
        request.TagKey = key
        request.TagValue = value
        module.sdk_call(client.AttachResourcesTag, request)
    for key in to_remove:
        request = tag_models.DetachResourcesTagRequest()
        request.ServiceType = "cam"
        request.ResourceIds = [resource_id]
        request.ResourceRegion = module.params["region"]
        request.ResourcePrefix = "policy"
        request.TagKey = key
        module.sdk_call(client.DetachResourcesTag, request)


def _documents_equal(current_document, desired_document):
    """Compare policy documents semantically (parsed JSON)."""
    try:
        current = normalize_document(current_document)
    except ValueError:
        current = current_document
    return current == desired_document


def _fail_if_preset(module, policy):
    if policy.get("Type") not in (None, POLICY_TYPE_CUSTOM):
        module.fail_json(
            msg="Policy %s is a preset (QCS) policy; only custom policies can be modified or deleted"
            % policy.get("PolicyId")
        )


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "policy_id": {"type": "int"},
            "policy_name": {"type": "str"},
            "description": {"type": "str"},
            "policy_document": {"type": "raw"},
            "type": {"type": "str", "choices": ["custom", "preset"], "default": "custom"},
            "tags": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    policy_id = module.params["policy_id"]
    policy_name = module.params["policy_name"]
    description = module.params["description"]
    policy_document = module.params["policy_document"]
    policy_type = module.params["type"]
    tags = module.params["tags"]

    if policy_id is None and not policy_name:
        module.fail_json(msg="policy_id or policy_name is required")

    models, cam_client = _load_cam()
    client = module.create_client(cam_client.CamClient, "cam.tencentcloudapi.com")

    try:
        desired_document = normalize_document(policy_document)
    except ValueError:
        module.fail_json(msg="policy_document is not valid JSON")

    try:
        current = find_policy(
            module, client, models, policy_id, policy_name, SCOPE_BY_TYPE[policy_type]
        )

        if state == "absent":
            if current is None:
                module.exit_json(changed=False, msg="CAM policy already absent")
            _fail_if_preset(module, current)
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would delete CAM policy")
            try:
                _delete(module, client, models, current["PolicyId"])
            except Exception as exc:
                if is_idempotent_success(exc):
                    module.exit_json(changed=True, **(diff or {}), msg="CAM policy deleted")
                raise
            module.exit_json(changed=True, **(diff or {}), policy=None, msg="CAM policy deleted")

        # state == present
        desired = {
            "policy_name": policy_name,
            "description": description or "",
            "policy_document": desired_document,
            "tags": tags,
        }
        if current is None:
            if not policy_name:
                module.fail_json(msg="policy_name is required to create a CAM policy")
            if policy_type != "custom":
                module.fail_json(msg="Only custom policies can be created; type=preset matches existing preset policies only")
            if desired_document is None:
                module.fail_json(msg="policy_document is required to create a CAM policy")
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), msg="Would create CAM policy")
            new_policy_id = _create(module, client, models, policy_name, description, desired_document, tags)
            created = find_policy(module, client, models, new_policy_id, None, SCOPE_BY_TYPE[policy_type])
            module.exit_json(changed=True, **(diff or {}), policy=created, msg="CAM policy created")

        current_policy_id = current["PolicyId"]
        changes = []
        if policy_name and policy_name != current.get("PolicyName"):
            changes.append("policy_name")
        if (description or "") != (current.get("Description") or ""):
            changes.append("description")
        if desired_document is not None and not _documents_equal(
            current.get("PolicyDocument"), desired_document
        ):
            changes.append("policy_document")
        tags_equal, to_add, to_remove = compare_tags(tags, current.get("Tags") or [])
        if not tags_equal:
            changes.append("tags")

        if not changes:
            module.exit_json(changed=False, policy=current, msg="CAM policy is up to date")

        _fail_if_preset(module, current)

        if module.check_mode:
            module.exit_json(changed=True, **(maybe_diff(module, current, desired) or {}), msg="Would update CAM policy")

        if any(change in changes for change in ("policy_name", "description", "policy_document")):
            _update(module, client, models, current_policy_id, policy_name, description, desired_document, changes)
        if not tags_equal:
            tag_models, tag_client = _load_tag()
            tag_client_instance = module.create_client(
                tag_client.TagClient, "tag.tencentcloudapi.com"
            )
            _apply_tags(module, tag_client_instance, tag_models, str(current_policy_id), to_add, to_remove)

        updated = find_policy(module, client, models, current_policy_id, None, SCOPE_BY_TYPE[policy_type])
        module.exit_json(
            changed=True,
            **(maybe_diff(module, current, desired) or {}),
            policy=updated,
            msg="CAM policy updated",
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
