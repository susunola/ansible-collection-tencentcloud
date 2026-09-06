#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: vod_sub_app
short_description: Manage Tencent Cloud VOD sub-applications
version_added: "0.14.0"
description:
  - Create, update or destroy a Video on Demand (VOD) sub-application
    through the C(vod.v20180717) API C(CreateSubAppId),
    C(ModifySubAppIdInfo), C(ModifySubAppIdStatus) and
    C(DescribeSubAppIds).
  - This module is idempotent. A sub-application is matched by its name.
    When a sub-application with the same name already exists, the module
    compares the description and status and issues updates only when they
    differ; all other fields are create-only.
  - Removal marks the sub-application as destroyed through
    C(ModifySubAppIdStatus); the platform has no delete API for
    sub-applications.
  - Supports check mode; no API write happens in check mode, only reads.
options:
  sub_app_name:
    description: Name of the VOD sub-application, up to 40 characters.
    type: str
    required: true
  state:
    description: Whether the sub-application should exist.
    type: str
    choices: [present, absent]
    default: present
  description:
    description:
      - Sub-application description, up to 300 characters. Compared
        against the remote value and written through
        V(ModifySubAppIdInfoRequest.Description) when it differs.
    type: str
  sub_app_type:
    description:
      - Application type, written to V(CreateSubAppIdRequest.Type).
        Only used at creation.
    type: str
    choices: [AllInOne, Professional]
  mode:
    description:
      - Application mode, written to V(CreateSubAppIdRequest.Mode).
        Only used at creation.
    type: str
  storage_region:
    description:
      - Default storage region, written to
        V(CreateSubAppIdRequest.StorageRegion). Only used at creation.
    type: str
  tags:
    description:
      - Tags bound to the application, written to
        V(CreateSubAppIdRequest.Tags). Only used at creation.
    type: list
    elements: str
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
  - Requires the C(tencentcloud-sdk-python-vod) package on the controller.
  - Changing the type, mode, storage region or tags of an existing
    sub-application is not supported by the platform; only the description
    and status can be updated in place.
  - Destroying a sub-application is irreversible and the operation is
    asynchronous; this module returns as soon as the destroy request is
    accepted.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a VOD sub-application
  susunola.tencentcloud.vod_sub_app:
    region: ap-guangzhou
    sub_app_name: media-prod
    description: production media processing
    sub_app_type: Professional
    tags:
      - env=prod

- name: Update the description of a VOD sub-application
  susunola.tencentcloud.vod_sub_app:
    region: ap-guangzhou
    sub_app_name: media-prod
    description: updated description

- name: Destroy a VOD sub-application
  susunola.tencentcloud.vod_sub_app:
    region: ap-guangzhou
    sub_app_name: media-prod
    state: absent
'''

RETURN = r'''
sub_app_id:
  description: ID of the matched or newly created sub-application.
  returned: when known
  type: int
sub_app_name:
  description: Name of the managed sub-application.
  returned: always
  type: str
status:
  description: Status of the sub-application.
  returned: when a matching sub-application exists
  type: str
changed:
  description: Whether an API write happened.
  returned: always
  type: bool
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load_vod():
    from tencentcloud.vod.v20180717 import models, vod_client
    return models, vod_client


def find_sub_app(module, client, models, sub_app_name):
    """Return the serialized sub-application dict with the given name, or None."""
    request = models.DescribeSubAppIdsRequest()
    offset = 0
    while True:
        request.Offset = offset
        request.Limit = 200
        response = module.sdk_call(client.DescribeSubAppIds, request)
        items = response.SubAppIdInfoSet or []
        for item in items:
            data = item._serialize(allow_none=True)
            if data.get("SubAppIdName") == sub_app_name or data.get("Name") == sub_app_name:
                return data
        if len(items) < 200:
            break
        offset += len(items)
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "sub_app_name": {"type": "str", "required": True},
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "description": {"type": "str"},
            "sub_app_type": {"type": "str", "choices": ["AllInOne", "Professional"]},
            "mode": {"type": "str"},
            "storage_region": {"type": "str"},
            "tags": {"type": "list", "elements": "str"},
        },
        supports_check_mode=True,
    )
    module.require_sdk()
    p = module.params

    models, vod_client = _load_vod()
    client = module.create_client(vod_client.VodClient, "vod.tencentcloudapi.com")
    try:
        found = find_sub_app(module, client, models, p["sub_app_name"])

        if p["state"] == "absent":
            if found is None:
                module.exit_json(changed=False, sub_app_name=p["sub_app_name"],
                                 msg="VOD sub-application not present")
            if found.get("Status") == "Destroyed":
                module.exit_json(changed=False, sub_app_id=found.get("SubAppId"),
                                 sub_app_name=p["sub_app_name"], status="Destroyed",
                                 msg="VOD sub-application already destroyed")
            diff = maybe_diff(module, found, None)
            if module.check_mode:
                module.exit_json(
                    changed=True, **(diff or {}),
                    sub_app_id=found.get("SubAppId"),
                    sub_app_name=p["sub_app_name"],
                    msg="Would destroy VOD sub-application {0}".format(found.get("SubAppId")),
                )
            request = models.ModifySubAppIdStatusRequest()
            request.SubAppId = found["SubAppId"]
            request.Status = "Destroyed"
            module.sdk_call(client.ModifySubAppIdStatus, request)
            module.exit_json(
                changed=True, **(diff or {}),
                sub_app_id=found.get("SubAppId"),
                sub_app_name=p["sub_app_name"],
                msg="Destroy request submitted for VOD sub-application {0}".format(found.get("SubAppId")),
            )

        # state == present
        if found is not None:
            updates = []
            current_desc = found.get("Description") or ""
            desired_desc = p["description"] or ""
            if current_desc != desired_desc:
                updates.append("description")
            if found.get("Status") != "On":
                updates.append("status")
            if not updates:
                module.exit_json(
                    changed=False,
                    sub_app_id=found.get("SubAppId"),
                    sub_app_name=p["sub_app_name"],
                    status=found.get("Status"),
                    msg="VOD sub-application already present",
                )
            if module.check_mode:
                module.exit_json(
                    changed=True,
                    sub_app_id=found.get("SubAppId"),
                    sub_app_name=p["sub_app_name"],
                    msg="Would update VOD sub-application {0}: {1}".format(
                        found.get("SubAppId"), ", ".join(updates)),
                )
            if current_desc != desired_desc:
                info_request = models.ModifySubAppIdInfoRequest()
                info_request.SubAppId = found["SubAppId"]
                info_request.Description = desired_desc
                module.sdk_call(client.ModifySubAppIdInfo, info_request)
            if found.get("Status") != "On":
                status_request = models.ModifySubAppIdStatusRequest()
                status_request.SubAppId = found["SubAppId"]
                status_request.Status = "On"
                module.sdk_call(client.ModifySubAppIdStatus, status_request)
            module.exit_json(
                changed=True,
                sub_app_id=found.get("SubAppId"),
                sub_app_name=p["sub_app_name"],
                msg="Updated VOD sub-application {0}: {1}".format(
                    found.get("SubAppId"), ", ".join(updates)),
            )

        after = {"SubAppIdName": p["sub_app_name"]}
        diff = maybe_diff(module, None, after)
        if module.check_mode:
            module.exit_json(
                changed=True, **(diff or {}),
                sub_app_name=p["sub_app_name"],
                msg="Would create VOD sub-application {0}".format(p["sub_app_name"]),
            )

        request = models.CreateSubAppIdRequest()
        request.Name = p["sub_app_name"]
        if p["description"]:
            request.Description = p["description"]
        if p["sub_app_type"]:
            request.Type = p["sub_app_type"]
        if p["mode"]:
            request.Mode = p["mode"]
        if p["storage_region"]:
            request.StorageRegion = p["storage_region"]
        if p["tags"]:
            request.Tags = p["tags"]
        response = module.sdk_call(client.CreateSubAppId, request)
        sub_app_id = getattr(response, "SubAppId", None)
        module.exit_json(
            changed=True, **(diff or {}),
            sub_app_id=sub_app_id,
            sub_app_name=p["sub_app_name"],
            msg="VOD sub-application created",
        )
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
