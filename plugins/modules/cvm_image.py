#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cvm_image
short_description: Manage Tencent Cloud CVM custom images
version_added: "0.12.0"
description:
  - Create, rename, describe and delete custom CVM images through the
    C(cvm.v20170312) API.
  - This module is idempotent. Running it twice leaves the image unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the image when it does not exist and updates its
        name and description when it does.
      - C(absent) deletes the image.
    type: str
    choices: [present, absent]
    default: present
  image_id:
    description:
      - ID of an existing image, e.g. C(img-xxxxxxxx).
      - When given, the module operates on that image; otherwise the image
        is matched by O(image_name) and the first match is used.
    type: str
  image_name:
    description:
      - Display name of the image.
      - Used to look up the image when O(image_id) is not given, and as the
        desired name to enforce on an existing image.
    type: str
  instance_id:
    description:
      - Instance ID (C(ins-xxxxxxxx)) to create the image from.
      - Required when the image does not exist yet; only applied at creation.
    type: str
  image_description:
    description:
      - Optional description written to V(CreateImageRequest.ImageDescription)
        and V(ModifyImageAttributeRequest.ImageDescription).
    type: str
  force_poweroff:
    description:
      - Whether the source instance is force powered off before the image is
        taken, written to V(CreateImageRequest.ForcePoweroff).
    type: bool
    default: false
  sysprep:
    description:
      - Runs Sysprep on the source Windows instance before imaging, written
        to V(CreateImageRequest.Sysprep).
    type: bool
    default: false
  delete_binded_snap:
    description:
      - Also delete the bound snapshots when deleting the image, written to
        V(DeleteImagesRequest.DeleteBindedSnap).
    type: bool
    default: false
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
  - Images are account-global, not region-scoped; the region parameter is
    still required because the CVM client is per-region.
  - Deleting an image only removes the image itself; the source instance is
    left untouched.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a custom image from a running instance
  susunola.tencentcloud.cvm_image:
    region: ap-guangzhou
    state: present
    image_name: web-prod-20260827
    instance_id: ins-xxxxxxxx
    image_description: Golden web image for production

- name: Rename an existing image
  susunola.tencentcloud.cvm_image:
    region: ap-guangzhou
    state: present
    image_name: web-prod-latest
    instance_id: ins-xxxxxxxx

- name: Delete an image
  susunola.tencentcloud.cvm_image:
    region: ap-guangzhou
    state: absent
    image_name: web-prod-20260827
'''

RETURN = r'''
image:
  description: The image as reported by V(DescribeImages) after the operation.
  returned: success
  type: dict
  sample:
    ImageId: img-xxxxxxxx
    ImageName: web-prod-20260827
    ImageState: NORMAL
    ImageType: PRIVATE_IMAGE
    ImageSize: 50
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_cvm():
    from tencentcloud.cvm.v20170312 import models, cvm_client
    return models, cvm_client


def build_describe_request(models, image_id, image_name):
    request = models.DescribeImagesRequest()
    request.Offset = 0
    request.Limit = 100
    if image_id:
        request.ImageIds = [image_id]
    elif image_name:
        name_filter = models.Filter()
        name_filter.Name = "image-name"
        name_filter.Values = [image_name]
        request.Filters = [name_filter]
    return request


def _first(collection):
    return collection[0] if collection else None


def find_image(module, client, models, image_id, image_name):
    """Return the matching image dict or None."""
    request = build_describe_request(models, image_id, image_name)
    response = module.sdk_call(client.DescribeImages, request)
    image = _first(response.ImageSet or [])
    if image is None:
        return None
    return image._serialize(allow_none=True)


def _create(module, client, models, params):
    request = models.CreateImageRequest()
    request.InstanceId = params["instance_id"]
    if params["image_name"]:
        request.ImageName = params["image_name"]
    if params["image_description"]:
        request.ImageDescription = params["image_description"]
    if params["force_poweroff"]:
        request.ForcePoweroff = "true"
    if params["sysprep"]:
        request.Sysprep = "true"
    return module.sdk_call(client.CreateImage, request)


def _update(module, client, models, image_id, image_name, image_description):
    request = models.ModifyImageAttributeRequest()
    request.ImageId = image_id
    if image_name is not None:
        request.ImageName = image_name
    if image_description is not None:
        request.ImageDescription = image_description
    module.sdk_call(client.ModifyImageAttribute, request)


def _delete(module, client, models, image_id, delete_binded_snap):
    request = models.DeleteImagesRequest()
    request.ImageIds = [image_id]
    if delete_binded_snap:
        request.DeleteBindedSnap = True
    module.sdk_call(client.DeleteImages, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "image_id": {"type": "str"},
            "image_name": {"type": "str"},
            "instance_id": {"type": "str"},
            "image_description": {"type": "str"},
            "force_poweroff": {"type": "bool", "default": False},
            "sysprep": {"type": "bool", "default": False},
            "delete_binded_snap": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    image_id = module.params["image_id"]
    image_name = module.params["image_name"]

    if state == "absent" and not image_id and not image_name:
        module.fail_json(msg="image_id or image_name is required when state=absent")

    models, cvm_client = _load_cvm()
    client = module.create_client(cvm_client.CvmClient, "cvm.tencentcloudapi.com")

    try:
        current = find_image(module, client, models, image_id, image_name)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="Image already absent")
        target_id = current["ImageId"]
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete image")
        _delete(module, client, models, target_id, module.params["delete_binded_snap"])
        module.exit_json(changed=True, **(diff or {}), image=None, msg="Image deleted")

    # state == present
    if current is None:
        if not module.params["instance_id"]:
            module.fail_json(msg="instance_id is required when creating an image")
        if not image_name:
            module.fail_json(msg="image_name is required when creating an image")
        desired = {
            "ImageName": image_name,
            "InstanceId": module.params["instance_id"],
            "ImageDescription": module.params["image_description"],
        }
        desired = {key: value for key, value in desired.items() if value is not None}
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create image")
        _create(module, client, models, module.params)
        # Re-read by the name the module just enforced to return the image.
        created = find_image(module, client, models, None, image_name)
        module.exit_json(changed=True, **(diff or {}), image=created, msg="Image created")

    target_id = current["ImageId"]
    changes = []
    if image_name and current.get("ImageName") != image_name:
        changes.append("image_name")
    description = module.params["image_description"]
    if description is not None and current.get("ImageDescription") != description:
        changes.append("image_description")

    if not changes:
        module.exit_json(changed=False, image=current, msg="Image is up to date")

    diff = maybe_diff(module, current, {
        "ImageName": image_name or current.get("ImageName"),
        "ImageDescription": description if description is not None else current.get("ImageDescription"),
    })
    if module.check_mode:
        module.exit_json(changed=True, **(diff or {}), msg="Would update image")

    _update(
        module, client, models, target_id,
        image_name if "image_name" in changes else None,
        description if "image_description" in changes else None,
    )
    updated = find_image(module, client, models, target_id, None)
    module.exit_json(changed=True, **(diff or {}), image=updated, msg="Image updated")


def main():
    run_module()


if __name__ == "__main__":
    main()
