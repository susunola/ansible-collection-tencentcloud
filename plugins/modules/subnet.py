#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: subnet
short_description: Manage Tencent Cloud VPC subnets
version_added: "0.4.0"
description:
  - Create, update, and delete Tencent Cloud VPC subnets.
  - This module is idempotent. Running it twice leaves the resource unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the subnet if it does not exist and updates its
        name, broadcast flag and tags to match the task.
      - C(absent) deletes the subnet if it exists. Deleting a subnet that
        still contains resources (for example CVM instances) fails; release
        those resources first.
    type: str
    choices: [present, absent]
    default: present
  subnet_id:
    description:
      - ID of an existing subnet, e.g. C(subnet-xxxxxxxx).
      - When given, the module operates on that subnet and C(name) is used as
        the desired name to enforce.
    type: str
  vpc_id:
    description:
      - ID of the VPC the subnet belongs to, e.g. C(vpc-xxxxxxxx).
      - Required when creating a subnet; immutable afterwards. When the subnet
        already exists, a mismatching value is ignored with a warning.
      - Together with C(name) it is also used to match an existing subnet when
        C(subnet_id) is not given.
    type: str
  name:
    description:
      - Name of the subnet. Required when C(state=present).
    type: str
  cidr_block:
    description:
      - IPv4 CIDR block of the subnet, e.g. C(10.0.1.0/24). It must be within
        the VPC CIDR and must not overlap with other subnets in the VPC.
      - Required when creating a subnet; immutable afterwards. When the subnet
        already exists, a mismatching value is ignored with a warning.
    type: str
  zone:
    description:
      - Availability zone of the subnet, e.g. C(ap-guangzhou-1).
      - Required when creating a subnet; immutable afterwards. When the subnet
        already exists, a mismatching value is ignored with a warning.
    type: str
  enable_broadcast:
    description:
      - Whether to enable broadcast on the subnet.
      - The creation API does not accept this flag, so it is applied through
        C(ModifySubnetAttribute) after the subnet is created or when it
        differs from the current value.
    type: bool
  tags:
    description:
      - Tags to apply to the subnet as a dict, for example I(env=prod).
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
  - C(cidr_block), C(zone) and C(vpc_id) cannot be changed after creation;
    the module warns and leaves them untouched.
  - Uses the C(vpc.tencentcloudapi.com) endpoint by default.
extends_documentation_fragment: tencentcloud.cloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a subnet
  tencentcloud.cloud.subnet:
    region: ap-guangzhou
    state: present
    vpc_id: vpc-xxxxxxxx
    name: web-subnet
    cidr_block: 10.0.1.0/24
    zone: ap-guangzhou-1
    tags:
      env: prod
      tier: web

- name: Disable broadcast on an existing subnet (no changes applied)
  tencentcloud.cloud.subnet:
    region: ap-guangzhou
    state: present
    subnet_id: subnet-xxxxxxxx
    name: web-subnet
    enable_broadcast: false
  check_mode: true

- name: Delete a subnet
  tencentcloud.cloud.subnet:
    region: ap-guangzhou
    state: absent
    vpc_id: vpc-xxxxxxxx
    name: web-subnet
'''

RETURN = r'''
subnet:
  description: The subnet as reported by the API after the operation.
  returned: success
  type: dict
  sample:
    SubnetId: subnet-xxxxxxxx
    SubnetName: web-subnet
    VpcId: vpc-xxxxxxxx
    CidrBlock: 10.0.1.0/24
    Zone: ap-guangzhou-1
    IsDefault: false
    EnableBroadcast: false
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


def build_describe_request(models, subnet_id, vpc_id, name):
    request = models.DescribeSubnetsRequest()
    request.Limit = 100
    if subnet_id:
        request.SubnetIds = [subnet_id]
        return request
    filters = []
    if vpc_id:
        vpc_filter = models.Filter()
        vpc_filter.Name = "vpc-id"
        vpc_filter.Values = [vpc_id]
        filters.append(vpc_filter)
    if name:
        name_filter = models.Filter()
        name_filter.Name = "subnet-name"
        name_filter.Values = [name]
        filters.append(name_filter)
    if filters:
        request.Filters = filters
    return request


def _first(collection):
    return collection[0] if collection else None


def find_subnet(module, client, models, subnet_id, vpc_id, name):
    """Return the matching subnet dict or None."""
    request = build_describe_request(models, subnet_id, vpc_id, name)
    response = module.sdk_call(client.DescribeSubnets, request)
    subnet = _first(response.SubnetSet or [])
    if subnet is None:
        return None
    return subnet._serialize(allow_none=True)


def _update(module, client, models, subnet_id, name, enable_broadcast):
    """Update the subnet name and/or broadcast flag.

    The API types ``EnableBroadcast`` as a string (``"true"``/``"false"``),
    not a boolean.
    """
    request = models.ModifySubnetAttributeRequest()
    request.SubnetId = subnet_id
    request.SubnetName = name
    if enable_broadcast is not None:
        request.EnableBroadcast = "true" if enable_broadcast else "false"
    module.sdk_call(client.ModifySubnetAttribute, request)


def _apply_tags(module, client, tag_models, subnet_id, to_add, to_remove):
    """Reconcile tags through the tag service.

    The tag service model differs from the VPC model: resources are addressed
    by a plural ``ResourceIds`` list and tags by ``TagKey``/``TagValue``.
    Each tag key is processed independently.
    """
    for key, value in sorted(to_add.items()):
        request = tag_models.AttachResourcesTagRequest()
        request.ServiceType = "vpc"
        request.ResourceIds = [subnet_id]
        request.ResourceRegion = module.params["region"]
        request.ResourcePrefix = "subnet"
        request.TagKey = key
        request.TagValue = value
        module.sdk_call(client.AttachResourcesTag, request)
    for key in to_remove:
        request = tag_models.DetachResourcesTagRequest()
        request.ServiceType = "vpc"
        request.ResourceIds = [subnet_id]
        request.ResourceRegion = module.params["region"]
        request.ResourcePrefix = "subnet"
        request.TagKey = key
        module.sdk_call(client.DetachResourcesTag, request)


def _create(module, client, models, vpc_id, name, cidr_block, zone, tags):
    request = models.CreateSubnetRequest()
    request.VpcId = vpc_id
    request.SubnetName = name
    request.CidrBlock = cidr_block
    request.Zone = zone
    if tags:
        request.Tags = build_sdk_tags(models, tags)
    response = module.sdk_call(client.CreateSubnet, request)
    return response.Subnet._serialize(allow_none=True)


def _delete(module, client, models, subnet_id):
    request = models.DeleteSubnetRequest()
    request.SubnetId = subnet_id
    module.sdk_call(client.DeleteSubnet, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "subnet_id": {"type": "str"},
            "vpc_id": {"type": "str"},
            "name": {"type": "str"},
            "cidr_block": {"type": "str"},
            "zone": {"type": "str"},
            "enable_broadcast": {"type": "bool"},
            "tags": {"type": "dict", "default": {}},
        },
        required_if=[("state", "present", ["name"])],
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    subnet_id = module.params["subnet_id"]
    vpc_id = module.params["vpc_id"]
    name = module.params["name"]
    cidr_block = module.params["cidr_block"]
    zone = module.params["zone"]
    enable_broadcast = module.params["enable_broadcast"]
    tags = module.params["tags"]

    if state == "absent" and not name and not subnet_id:
        module.fail_json(msg="name or subnet_id is required when state=absent")

    models, vpc_client = _load_vpc()
    client = module.create_client(vpc_client.VpcClient, "vpc.tencentcloudapi.com")

    try:
        current = find_subnet(module, client, models, subnet_id, vpc_id, name)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="Subnet already absent")
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete subnet")
        try:
            _delete(module, client, models, current["SubnetId"])
        except Exception as exc:
            if is_idempotent_success(exc):
                module.exit_json(changed=True, **(diff or {}), msg="Subnet deleted")
            raise
        module.exit_json(changed=True, **(diff or {}), subnet=None, msg="Subnet deleted")

    # state == present
    if current is None:
        if not vpc_id:
            module.fail_json(msg="vpc_id is required when creating a subnet")
        if not cidr_block:
            module.fail_json(msg="cidr_block is required when creating a subnet")
        if not zone:
            module.fail_json(msg="zone is required when creating a subnet")
        desired = {"name": name, "vpc_id": vpc_id, "cidr_block": cidr_block,
                   "zone": zone, "enable_broadcast": enable_broadcast, "tags": tags}
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create subnet")
        created = _create(module, client, models, vpc_id, name, cidr_block, zone, tags)
        if enable_broadcast is not None:
            # CreateSubnet does not accept a broadcast flag; apply it now.
            _update(module, client, models, created["SubnetId"], name, enable_broadcast)
            created = find_subnet(module, client, models, created["SubnetId"], None, None)
        module.exit_json(changed=True, **(diff or {}), subnet=created, msg="Subnet created")

    subnet_id = current["SubnetId"]
    current_name = current.get("SubnetName")
    current_broadcast = current.get("EnableBroadcast")
    current_tags = current.get("TagSet") or []

    # Immutable attributes: warn on drift and leave the remote value alone.
    if vpc_id and vpc_id != current.get("VpcId"):
        module.warn("vpc_id is immutable after creation; ignoring %s" % vpc_id)
    if cidr_block and cidr_block != current.get("CidrBlock"):
        module.warn("cidr_block is immutable after creation; ignoring %s" % cidr_block)
    if zone and zone != current.get("Zone"):
        module.warn("zone is immutable after creation; ignoring %s" % zone)

    changes = []
    if current_name != name:
        changes.append("name")
    if enable_broadcast is not None and bool(current_broadcast) != enable_broadcast:
        changes.append("enable_broadcast")
    tags_equal, to_add, to_remove = compare_tags(tags, current_tags)
    if not tags_equal:
        changes.append("tags")

    desired = {
        "name": name,
        "vpc_id": current.get("VpcId"),
        "cidr_block": current.get("CidrBlock"),
        "zone": current.get("Zone"),
        "enable_broadcast": enable_broadcast if enable_broadcast is not None else current_broadcast,
        "tags": tags,
    }

    if not changes:
        module.exit_json(changed=False, subnet=current, msg="Subnet is up to date")

    if module.check_mode:
        module.exit_json(changed=True, **(maybe_diff(module, current, desired) or {}), msg="Would update subnet")

    if "name" in changes or "enable_broadcast" in changes:
        _update(module, client, models, subnet_id, name, enable_broadcast)
    if not tags_equal:
        tag_models, tag_client = _load_tag()
        tag_client_instance = module.create_client(
            tag_client.TagClient, "tag.tencentcloudapi.com"
        )
        _apply_tags(module, tag_client_instance, tag_models, subnet_id, to_add, to_remove)

    updated = find_subnet(module, client, models, subnet_id, None, None)
    module.exit_json(
        changed=True,
        **(maybe_diff(module, current, desired) or {}),
        subnet=updated,
        msg="Subnet updated",
    )


def main():
    run_module()


if __name__ == "__main__":
    main()
