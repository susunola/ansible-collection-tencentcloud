#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: vpc
short_description: Manage Tencent Cloud VPCs
version_added: "0.4.0"
description:
  - Create, update, and delete Tencent Cloud Virtual Private Clouds (VPCs).
  - This module is idempotent. Running it twice leaves the resource unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the VPC if it does not exist and updates its name,
        DNS servers, domain name and tags to match the task.
      - C(absent) deletes the VPC if it exists. Deleting a VPC that still
        contains subnets or other resources fails with a C(ResourceInUse)
        error; remove those resources first.
    type: str
    choices: [present, absent]
    default: present
  vpc_id:
    description:
      - ID of an existing VPC, e.g. C(vpc-xxxxxxxx).
      - When given, the module operates on that VPC and C(name) is used as
        the desired name to enforce.
    type: str
  name:
    description:
      - Name of the VPC. Required when C(state=present).
      - When C(vpc_id) is not given, the VPC is matched by name. The API
        matches names fuzzily; this module prefers an exact match.
    type: str
  cidr_block:
    description:
      - IPv4 CIDR block of the VPC, e.g. C(10.0.0.0/16). Must fall inside
        C(10.0.0.0/12), C(172.16.0.0/12) or C(192.168.0.0/16).
      - Required when creating a VPC. Changing it after creation is a no-op;
        the VPC API does not support modifying the primary CIDR block.
    type: str
  dns_servers:
    description:
      - DNS server addresses for the VPC, up to 4 entries. The first entry is
        the primary server, the rest are backups.
      - When omitted, existing DNS servers are left untouched.
    type: list
    elements: str
  domain_name:
    description:
      - Domain name used by DHCP in the VPC.
      - When omitted, the existing domain name is left untouched.
    type: str
  tags:
    description:
      - Tags to apply to the VPC as a dict, for example I(env=prod).
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
    default: ansible-collection.tencentcloud.cloud
notes:
  - Requires the C(tencentcloud-sdk-python-vpc) package on the controller.
  - Tag reconciliation additionally requires C(tencentcloud-sdk-python-tag).
  - The primary CIDR block cannot be changed after creation; passing a
    different O(cidr_block) for an existing VPC is a no-op.
  - Uses the C(vpc.tencentcloudapi.com) endpoint by default.
extends_documentation_fragment: tencentcloud.cloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a VPC
  tencentcloud.cloud.vpc:
    region: ap-guangzhou
    state: present
    name: prod-vpc
    cidr_block: 10.0.0.0/16
    dns_servers:
      - 183.60.83.19
      - 183.60.82.98
    domain_name: prod.internal
    tags:
      env: prod

- name: Check whether the VPC would be updated (no changes applied)
  tencentcloud.cloud.vpc:
    region: ap-guangzhou
    state: present
    name: prod-vpc
    cidr_block: 10.0.0.0/16
  check_mode: true

- name: Delete a VPC
  tencentcloud.cloud.vpc:
    region: ap-guangzhou
    state: absent
    name: prod-vpc
'''

RETURN = r'''
vpc:
  description: The VPC as reported by the API after the operation.
  returned: success
  type: dict
  sample:
    VpcId: vpc-xxxxxxxx
    VpcName: prod-vpc
    CidrBlock: 10.0.0.0/16
    DnsServerSet:
      - 183.60.83.19
    DomainName: prod.internal
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


def build_describe_request(models, name, vpc_id):
    request = models.DescribeVpcsRequest()
    request.Offset = "0"
    request.Limit = "100"
    if vpc_id:
        request.VpcIds = [vpc_id]
    if name:
        name_filter = models.Filter()
        name_filter.Name = "vpc-name"
        name_filter.Values = [name]
        request.Filters = [name_filter]
    return request


def find_vpc(module, client, models, name, vpc_id):
    """Return the matching VPC dict or None.

    The ``vpc-name`` filter matches fuzzily, so an exact name match is
    preferred over the first entry of the result set.
    """
    request = build_describe_request(models, name, vpc_id)
    response = module.sdk_call(client.DescribeVpcs, request)
    vpcs = response.VpcSet or []
    if not vpcs:
        return None
    match = vpcs[0]
    if name and not vpc_id:
        for vpc in vpcs:
            if getattr(vpc, "VpcName", None) == name:
                match = vpc
                break
    return match._serialize(allow_none=True)


def _update_attributes(module, client, models, vpc_id, name, dns_servers, domain_name):
    request = models.ModifyVpcAttributeRequest()
    request.VpcId = vpc_id
    request.VpcName = name
    request.DnsServers = dns_servers
    request.DomainName = domain_name
    module.sdk_call(client.ModifyVpcAttribute, request)


def _apply_tags(module, client, tag_models, vpc_id, to_add, to_remove):
    """Reconcile tags through the tag service.

    The tag service model differs from the VPC model: resources are addressed
    by a plural ``ResourceIds`` list and tags by ``TagKey``/``TagValue``.
    Each tag key is processed independently.
    """
    for key, value in sorted(to_add.items()):
        request = tag_models.AttachResourcesTagRequest()
        request.ServiceType = "vpc"
        request.ResourceIds = [vpc_id]
        request.ResourceRegion = module.params["region"]
        request.ResourcePrefix = "vpc"
        request.TagKey = key
        request.TagValue = value
        module.sdk_call(client.AttachResourcesTag, request)
    for key in to_remove:
        request = tag_models.DetachResourcesTagRequest()
        request.ServiceType = "vpc"
        request.ResourceIds = [vpc_id]
        request.ResourceRegion = module.params["region"]
        request.ResourcePrefix = "vpc"
        request.TagKey = key
        module.sdk_call(client.DetachResourcesTag, request)


def _create(module, client, models, name, cidr_block, dns_servers, domain_name, tags):
    request = models.CreateVpcRequest()
    request.VpcName = name
    request.CidrBlock = cidr_block
    if dns_servers is not None:
        request.DnsServers = dns_servers
    if domain_name is not None:
        request.DomainName = domain_name
    if tags:
        request.Tags = build_sdk_tags(models, tags)
    response = module.sdk_call(client.CreateVpc, request)
    return response.Vpc._serialize(allow_none=True)


def _delete(module, client, models, vpc_id):
    request = models.DeleteVpcRequest()
    request.VpcId = vpc_id
    module.sdk_call(client.DeleteVpc, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "vpc_id": {"type": "str"},
            "name": {"type": "str"},
            "cidr_block": {"type": "str"},
            "dns_servers": {"type": "list", "elements": "str"},
            "domain_name": {"type": "str"},
            "tags": {"type": "dict", "default": {}},
        },
        required_if=[("state", "present", ["name"])],
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    vpc_id = module.params["vpc_id"]
    name = module.params["name"]
    cidr_block = module.params["cidr_block"]
    dns_servers = module.params["dns_servers"]
    domain_name = module.params["domain_name"]
    tags = module.params["tags"]

    if state == "absent" and not name and not vpc_id:
        module.fail_json(msg="name or vpc_id is required when state=absent")

    models, vpc_client = _load_vpc()
    client = module.create_client(vpc_client.VpcClient, "vpc.tencentcloudapi.com")

    try:
        current = find_vpc(module, client, models, name, vpc_id)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="VPC already absent")
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete VPC")
        try:
            _delete(module, client, models, current["VpcId"])
        except Exception as exc:
            if is_idempotent_success(exc):
                module.exit_json(changed=True, **(diff or {}), msg="VPC deleted")
            raise
        module.exit_json(changed=True, **(diff or {}), vpc=None, msg="VPC deleted")

    # state == present
    desired = {"name": name, "dns_servers": dns_servers, "domain_name": domain_name, "tags": tags}
    if current is None:
        if not cidr_block:
            module.fail_json(msg="cidr_block is required when creating a VPC")
        desired["cidr_block"] = cidr_block
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create VPC")
        created = _create(module, client, models, name, cidr_block, dns_servers, domain_name, tags)
        module.exit_json(changed=True, **(diff or {}), vpc=created, msg="VPC created")

    current_vpc_id = current["VpcId"]
    current_name = current.get("VpcName")
    current_dns = current.get("DnsServerSet") or []
    current_domain = current.get("DomainName") or ""
    current_tags = current.get("TagSet") or []

    # The primary CIDR block is immutable; report it as-is in the diff.
    desired["cidr_block"] = current.get("CidrBlock")

    changes = []
    if current_name != name:
        changes.append("name")
    if dns_servers is not None and list(dns_servers) != list(current_dns):
        changes.append("dns_servers")
    if domain_name is not None and domain_name != current_domain:
        changes.append("domain_name")
    tags_equal, to_add, to_remove = compare_tags(tags, current_tags)
    if not tags_equal:
        changes.append("tags")

    if not changes:
        module.exit_json(changed=False, vpc=current, msg="VPC is up to date")

    if module.check_mode:
        module.exit_json(changed=True, **(maybe_diff(module, current, desired) or {}), msg="Would update VPC")

    if any(key in changes for key in ("name", "dns_servers", "domain_name")):
        # ModifyVpcAttribute rewrites all three attributes; pass the current
        # values for attributes the task does not manage so they survive.
        effective_dns = dns_servers if dns_servers is not None else current_dns
        effective_domain = domain_name if domain_name is not None else current_domain
        _update_attributes(module, client, models, current_vpc_id, name, effective_dns, effective_domain)
    if not tags_equal:
        tag_models, tag_client = _load_tag()
        tag_client_instance = module.create_client(
            tag_client.TagClient, "tag.tencentcloudapi.com"
        )
        _apply_tags(module, tag_client_instance, tag_models, current_vpc_id, to_add, to_remove)

    updated = find_vpc(module, client, models, None, current_vpc_id)
    module.exit_json(
        changed=True,
        **(maybe_diff(module, current, desired) or {}),
        vpc=updated,
        msg="VPC updated",
    )


def main():
    run_module()


if __name__ == "__main__":
    main()
