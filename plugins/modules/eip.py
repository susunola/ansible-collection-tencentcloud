#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: eip
short_description: Manage Tencent Cloud elastic IP addresses (EIP)
version_added: "0.4.0"
description:
  - Allocate, update, associate, and release Tencent Cloud elastic IP
    addresses (EIP) through the VPC C(v20170312) Address APIs.
  - This module is idempotent. Running it twice leaves the resource unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) allocates the address if it does not exist and updates its
        name, tags, and instance association to match the task.
      - C(absent) releases the address if it exists. When the address is still
        bound to an instance it is disassociated first, then released.
    type: str
    choices: [present, absent]
    default: present
  eip_id:
    description:
      - ID of an existing address, e.g. C(eip-xxxxxxxx).
      - The address is matched by C(eip_id) first, then by C(address_ip), then
        by C(name).
    type: str
  address_ip:
    description:
      - Public IP address of an existing address, e.g. C(1.2.3.4).
      - Used to match the address when C(eip_id) is not given.
    type: str
  name:
    description:
      - Name of the address. Applied at allocation and enforced with
        C(ModifyAddressAttribute) on existing addresses.
      - When neither C(eip_id) nor C(address_ip) is given, the address is
        matched by name so that repeated runs stay idempotent. Address names
        are not unique; the first match wins.
    type: str
  internet_charge_type:
    description:
      - Network billing mode of the address.
      - Only applied at allocation; the C(ModifyAddressAttribute) API cannot
        change it, so it is ignored for existing addresses.
    type: str
    choices:
      - BANDWIDTH_PACKAGE
      - BANDWIDTH_POSTPAID_BY_HOUR
      - BANDWIDTH_PREPAID_BY_MONTH
      - TRAFFIC_POSTPAID_BY_HOUR
  internet_max_bandwidth_out:
    description:
      - Outbound bandwidth cap of the address in Mbps.
      - Only applied at allocation; the C(ModifyAddressAttribute) API cannot
        change it, so it is ignored for existing addresses.
    type: int
  instance_id:
    description:
      - Optional CVM instance ID, e.g. C(ins-xxxxxxxx), the address must be
        associated with.
      - When given, the address is associated with this instance,
        disassociating it from any other resource first.
      - When set to an empty string, the address is kept unassociated.
      - When omitted, the existing association is left untouched.
    type: str
  tags:
    description:
      - Tags to apply to the address as a dict, for example I(env=prod).
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
  - C(internet_charge_type) and C(internet_max_bandwidth_out) are applied at
    allocation only; changing them on an existing address is a no-op.
  - Uses the C(vpc.tencentcloudapi.com) endpoint by default.
extends_documentation_fragment: tencentcloud.cloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Allocate an EIP
  tencentcloud.cloud.eip:
    region: ap-guangzhou
    state: present
    name: web-eip
    internet_charge_type: TRAFFIC_POSTPAID_BY_HOUR
    internet_max_bandwidth_out: 10
    tags:
      env: prod

- name: Allocate an EIP and associate it with a CVM instance
  tencentcloud.cloud.eip:
    region: ap-guangzhou
    state: present
    name: web-eip
    instance_id: ins-xxxxxxxx

- name: Make sure an EIP is not associated with anything
  tencentcloud.cloud.eip:
    region: ap-guangzhou
    state: present
    address_ip: 1.2.3.4
    instance_id: ""

- name: Release an EIP (disassociates it first when bound)
  tencentcloud.cloud.eip:
    region: ap-guangzhou
    state: absent
    eip_id: eip-xxxxxxxx
'''

RETURN = r'''
eip:
  description: The address as reported by the API after the operation.
  returned: success
  type: dict
  sample:
    AddressId: eip-xxxxxxxx
    AddressName: web-eip
    AddressIp: 1.2.3.4
    AddressStatus: BIND
    InstanceId: ins-xxxxxxxx
    InternetChargeType: TRAFFIC_POSTPAID_BY_HOUR
    Bandwidth: 10
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


def build_describe_request(models, eip_id, address_ip, name):
    request = models.DescribeAddressesRequest()
    request.Limit = 100
    if eip_id:
        request.AddressIds = [eip_id]
    elif address_ip:
        ip_filter = models.Filter()
        ip_filter.Name = "address-ip"
        ip_filter.Values = [address_ip]
        request.Filters = [ip_filter]
    elif name:
        name_filter = models.Filter()
        name_filter.Name = "address-name"
        name_filter.Values = [name]
        request.Filters = [name_filter]
    return request


def _first(collection):
    return collection[0] if collection else None


def find_address(module, client, models, eip_id, address_ip, name):
    """Return the matching address dict or None."""
    request = build_describe_request(models, eip_id, address_ip, name)
    response = module.sdk_call(client.DescribeAddresses, request)
    address = _first(response.AddressSet or [])
    if address is None:
        return None
    return address._serialize(allow_none=True)


def _associate(module, client, models, address_id, instance_id):
    request = models.AssociateAddressRequest()
    request.AddressId = address_id
    request.InstanceId = instance_id
    module.sdk_call(client.AssociateAddress, request)


def _disassociate(module, client, models, address_id):
    request = models.DisassociateAddressRequest()
    request.AddressId = address_id
    module.sdk_call(client.DisassociateAddress, request)


def _update_name(module, client, models, address_id, name):
    request = models.ModifyAddressAttributeRequest()
    request.AddressId = address_id
    request.AddressName = name
    module.sdk_call(client.ModifyAddressAttribute, request)


def _apply_tags(module, client, tag_models, address_id, to_add, to_remove):
    """Reconcile tags through the tag service.

    The tag service model differs from the VPC model: resources are addressed
    by a plural ``ResourceIds`` list and tags by ``TagKey``/``TagValue``.
    Each tag key is processed independently.
    """
    for key, value in sorted(to_add.items()):
        request = tag_models.AttachResourcesTagRequest()
        request.ServiceType = "vpc"
        request.ResourceIds = [address_id]
        request.ResourceRegion = module.params["region"]
        request.ResourcePrefix = "eip"
        request.TagKey = key
        request.TagValue = value
        module.sdk_call(client.AttachResourcesTag, request)
    for key in to_remove:
        request = tag_models.DetachResourcesTagRequest()
        request.ServiceType = "vpc"
        request.ResourceIds = [address_id]
        request.ResourceRegion = module.params["region"]
        request.ResourcePrefix = "eip"
        request.TagKey = key
        module.sdk_call(client.DetachResourcesTag, request)


def _create(module, client, models, name, internet_charge_type, internet_max_bandwidth_out, tags):
    """Allocate a single address and return its ID."""
    request = models.AllocateAddressesRequest()
    request.AddressCount = 1
    if name:
        request.AddressName = name
    if internet_charge_type:
        request.InternetChargeType = internet_charge_type
    if internet_max_bandwidth_out is not None:
        request.InternetMaxBandwidthOut = internet_max_bandwidth_out
    if tags:
        request.Tags = build_sdk_tags(models, tags)
    response = module.sdk_call(client.AllocateAddresses, request)
    return _first(response.AddressSet or [])


def _delete(module, client, models, address_id, bound):
    """Release an address, disassociating it first when bound."""
    if bound:
        _disassociate(module, client, models, address_id)
    request = models.ReleaseAddressesRequest()
    request.AddressIds = [address_id]
    module.sdk_call(client.ReleaseAddresses, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "eip_id": {"type": "str"},
            "address_ip": {"type": "str"},
            "name": {"type": "str"},
            "internet_charge_type": {
                "type": "str",
                "choices": [
                    "BANDWIDTH_PACKAGE",
                    "BANDWIDTH_POSTPAID_BY_HOUR",
                    "BANDWIDTH_PREPAID_BY_MONTH",
                    "TRAFFIC_POSTPAID_BY_HOUR",
                ],
            },
            "internet_max_bandwidth_out": {"type": "int"},
            "instance_id": {"type": "str"},
            "tags": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    eip_id = module.params["eip_id"]
    address_ip = module.params["address_ip"]
    name = module.params["name"]
    internet_charge_type = module.params["internet_charge_type"]
    internet_max_bandwidth_out = module.params["internet_max_bandwidth_out"]
    instance_id = module.params["instance_id"]
    tags = module.params["tags"]

    if not eip_id and not address_ip and not name:
        module.fail_json(msg="eip_id, address_ip, or name is required to identify the address")

    models, vpc_client = _load_vpc()
    client = module.create_client(vpc_client.VpcClient, "vpc.tencentcloudapi.com")

    try:
        current = find_address(module, client, models, eip_id, address_ip, name)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="Address already absent")
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would release address")
        bound = bool(current.get("InstanceId"))
        try:
            _delete(module, client, models, current["AddressId"], bound)
        except Exception as exc:
            if is_idempotent_success(exc):
                module.exit_json(changed=True, **(diff or {}), msg="Address released")
            raise
        module.exit_json(changed=True, **(diff or {}), eip=None, msg="Address released")

    # state == present
    desired = {
        "name": name,
        "internet_charge_type": internet_charge_type,
        "internet_max_bandwidth_out": internet_max_bandwidth_out,
        "instance_id": instance_id,
        "tags": tags,
    }
    if current is None:
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would allocate address")
        address_id = _create(
            module, client, models, name, internet_charge_type, internet_max_bandwidth_out, tags
        )
        if instance_id:
            _associate(module, client, models, address_id, instance_id)
        created = find_address(module, client, models, address_id, None, None)
        module.exit_json(changed=True, **(diff or {}), eip=created, msg="Address allocated")

    address_id = current["AddressId"]
    current_name = current.get("AddressName")
    current_tags = current.get("TagSet") or []
    current_instance = current.get("InstanceId") or ""

    changes = []
    if name is not None and name != (current_name or ""):
        changes.append("name")
    tags_equal, to_add, to_remove = compare_tags(tags, current_tags)
    if not tags_equal:
        changes.append("tags")
    if instance_id is not None and (instance_id or "") != current_instance:
        changes.append("association")

    if not changes:
        module.exit_json(changed=False, eip=current, msg="Address is up to date")

    if module.check_mode:
        module.exit_json(changed=True, **(maybe_diff(module, current, desired) or {}), msg="Would update address")

    if "name" in changes:
        _update_name(module, client, models, address_id, name)
    if "association" in changes:
        if current_instance:
            _disassociate(module, client, models, address_id)
        if instance_id:
            _associate(module, client, models, address_id, instance_id)
    if not tags_equal:
        tag_models, tag_client = _load_tag()
        tag_client_instance = module.create_client(
            tag_client.TagClient, "tag.tencentcloudapi.com"
        )
        _apply_tags(module, tag_client_instance, tag_models, address_id, to_add, to_remove)

    updated = find_address(module, client, models, address_id, None, None)
    module.exit_json(
        changed=True,
        **(maybe_diff(module, current, desired) or {}),
        eip=updated,
        msg="Address updated",
    )


def main():
    run_module()


if __name__ == "__main__":
    main()
