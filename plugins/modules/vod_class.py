#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: vod_class
short_description: Manage Tencent Cloud VOD media classes
version_added: "0.14.0"
description:
  - Create or remove a media classification (class) in Video on Demand
    through the C(vod.v20180717) API C(CreateClass), C(DeleteClass),
    C(ModifyClass) and C(DescribeAllClass).
  - This module is idempotent. A class is matched by its name and parent
    class id. When a matching class already exists the module makes no
    change; the platform does not allow renaming or moving an existing
    class through this module, so all fields are create-only.
  - Supports check mode; no API write happens in check mode, only reads.
options:
  class_name:
    description: Name of the media class, 1-64 characters.
    type: str
    required: true
  state:
    description: Whether the class should exist.
    type: str
    choices: [present, absent]
    default: present
  parent_id:
    description:
      - Parent class ID, written to V(CreateClassRequest.ParentId). Use -1
        for a first-level class.
    type: int
    default: -1
  sub_app_id:
    description:
      - VOD application ID, written to V(CreateClassRequest.SubAppId). Only
        required when operating on a VOD application other than the default
        one.
    type: int
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
  - Renaming or moving an existing class is not supported by the platform
    through this module; remove the class (state=absent) and re-create it
    under the new name or parent.
  - Deleting a class fails when it still contains media files or child
    classes; move or delete those first.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a first-level media class
  susunola.tencentcloud.vod_class:
    region: ap-guangzhou
    class_name: marketing

- name: Create a nested media class
  susunola.tencentcloud.vod_class:
    region: ap-guangzhou
    class_name: 2026
    parent_id: 12345

- name: Remove a media class
  susunola.tencentcloud.vod_class:
    region: ap-guangzhou
    class_name: marketing
    state: absent
'''

RETURN = r'''
class_id:
  description: ID of the matched or newly created class.
  returned: when known
  type: int
class_name:
  description: Name of the managed class.
  returned: always
  type: str
parent_id:
  description: Parent class ID of the managed class.
  returned: always
  type: int
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


def find_class(module, client, models, class_name, parent_id, sub_app_id):
    """Return the serialized VOD class dict with the given name and parent, or None."""
    request = models.DescribeAllClassRequest()
    if sub_app_id is not None:
        request.SubAppId = sub_app_id
    response = module.sdk_call(client.DescribeAllClass, request)
    for item in (response.ClassInfoSet or []):
        data = item._serialize(allow_none=True)
        if data.get("ClassName") == class_name and data.get("ParentId") == parent_id:
            return data
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "class_name": {"type": "str", "required": True},
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "parent_id": {"type": "int", "default": -1},
            "sub_app_id": {"type": "int"},
        },
        supports_check_mode=True,
    )
    module.require_sdk()
    p = module.params

    models, vod_client = _load_vod()
    client = module.create_client(vod_client.VodClient, "vod.tencentcloudapi.com")
    try:
        found = find_class(module, client, models, p["class_name"], p["parent_id"], p["sub_app_id"])

        if p["state"] == "absent":
            if found is None:
                module.exit_json(changed=False, class_name=p["class_name"], parent_id=p["parent_id"],
                                 msg="VOD class not present")
            diff = maybe_diff(module, found, None)
            if module.check_mode:
                module.exit_json(
                    changed=True, **(diff or {}),
                    class_id=found.get("ClassId"),
                    class_name=p["class_name"],
                    parent_id=p["parent_id"],
                    msg="Would delete VOD class {0}".format(found.get("ClassId")),
                )
            request = models.DeleteClassRequest()
            request.ClassId = found["ClassId"]
            if p["sub_app_id"] is not None:
                request.SubAppId = p["sub_app_id"]
            module.sdk_call(client.DeleteClass, request)
            module.exit_json(
                changed=True, **(diff or {}),
                class_id=found.get("ClassId"),
                class_name=p["class_name"],
                parent_id=p["parent_id"],
                msg="Deleted VOD class {0}".format(found.get("ClassId")),
            )

        # state == present
        if found is not None:
            module.exit_json(
                changed=False,
                class_id=found.get("ClassId"),
                class_name=p["class_name"],
                parent_id=p["parent_id"],
                msg="VOD class already present",
            )

        after = {"ClassName": p["class_name"], "ParentId": p["parent_id"]}
        diff = maybe_diff(module, None, after)
        if module.check_mode:
            module.exit_json(
                changed=True, **(diff or {}),
                class_name=p["class_name"],
                parent_id=p["parent_id"],
                msg="Would create VOD class {0}".format(p["class_name"]),
            )

        request = models.CreateClassRequest()
        request.ClassName = p["class_name"]
        request.ParentId = p["parent_id"]
        if p["sub_app_id"] is not None:
            request.SubAppId = p["sub_app_id"]
        response = module.sdk_call(client.CreateClass, request)
        class_id = getattr(response, "ClassId", None)
        module.exit_json(
            changed=True, **(diff or {}),
            class_id=class_id,
            class_name=p["class_name"],
            parent_id=p["parent_id"],
            msg="VOD class created",
        )
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
