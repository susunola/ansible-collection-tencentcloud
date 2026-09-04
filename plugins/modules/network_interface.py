#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: network_interface
short_description: Manage Tencent Cloud elastic network interfaces
version_added: "0.13.0"
description:
  - Create, update and delete Tencent Cloud VPC elastic network interfaces
    (ENI) through the C(vpc.v20170312) API.
  - This module is idempotent. Running it twice leaves the interface
    unchanged and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
  - An interface is identified by O(network_interface_id) or by
    O(name) + O(subnet_id). The name, description and bound security
    groups are enforced on an existing interface with
    V(ModifyNetworkInterfaceAttribute).
options:
  state:
    description:
      - C(present) creates the interface when it does not exist and
        enforces O(name), O(description) and O(security_group_ids) on an
        existing interface.
      - C(absent) deletes the interface with V(DeleteNetworkInterface).
    type: str
    choices: [present, absent]
    default: present
  network_interface_id:
    description:
      - ID of an existing interface, e.g. C(eni-xxxxxxxx).
      - When given, the module operates on that interface; otherwise it is
        matched by O(name) inside O(subnet_id).
    type: str
  name:
    description:
      - Name of the interface, written to
        V(CreateNetworkInterfaceRequest.NetworkInterfaceName) and
        V(ModifyNetworkInterfaceAttributeRequest.NetworkInterfaceName).
      - Required when creating the interface.
    type: str
  vpc_id:
    description:
      - ID of the VPC the interface belongs to, written to
        V(CreateNetworkInterfaceRequest.VpcId).
      - Required when creating the interface.
    type: str
  subnet_id:
    description:
      - ID of the subnet the interface belongs to, written to
        V(CreateNetworkInterfaceRequest.SubnetId).
      - Required when creating the interface.
    type: str
  description:
    description:
      - Description of the interface, written to
        V(CreateNetworkInterfaceRequest.NetworkInterfaceDescription) and
        V(ModifyNetworkInterfaceAttributeRequest.NetworkInterfaceDescription).
    type: str
  security_group_ids:
    description:
      - Security groups bound to the interface, written to
        V(CreateNetworkInterfaceRequest.SecurityGroupIds) and enforced
        with V(ModifyNetworkInterfaceAttributeRequest.SecurityGroupIds).
      - When the interface exists, the bound set is reconciled to exactly
        this list.
    type: list
    elements: str
    default: []
  secondary_private_ip_count:
    description:
      - Number of extra private IPs to allocate, written to
        V(CreateNetworkInterfaceRequest.SecondaryPrivateIpAddressCount).
      - Only applied at creation.
    type: int
  tags:
    description:
      - Tags to apply to the interface as a dict, for example I(env=prod).
      - Only applied at creation.
    type: dict
    default: {}
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
  - Requires the C(tencentcloud-sdk-python-vpc) package on the controller.
  - An interface that is attached to an instance cannot be deleted; detach
    it first.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create an elastic network interface
  susunola.tencentcloud.network_interface:
    region: ap-guangzhou
    state: present
    name: web-eni
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    description: Web tier interface
    security_group_ids:
      - sg-xxxxxxxx
    tags:
      env: prod

- name: Move it to a different security group
  susunola.tencentcloud.network_interface:
    region: ap-guangzhou
    state: present
    name: web-eni
    subnet_id: subnet-xxxxxxxx
    security_group_ids:
      - sg-yyyyyyyy

- name: Delete the interface
  susunola.tencentcloud.network_interface:
    region: ap-guangzhou
    state: absent
    name: web-eni
    subnet_id: subnet-xxxxxxxx
'''

RETURN = r'''
network_interface:
  description: The interface as reported by V(DescribeNetworkInterfaces)
    after the operation.
  returned: success
  type: dict
  sample:
    NetworkInterfaceId: eni-xxxxxxxx
    NetworkInterfaceName: web-eni
    VpcId: vpc-xxxxxxxx
    SubnetId: subnet-xxxxxxxx
    GroupSet: [sg-xxxxxxxx]
    PrivateIpAddressSet:
      - PrivateIpAddress: 10.0.0.10
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_vpc():
    from tencentcloud.vpc.v20170312 import models, vpc_client
    return models, vpc_client


def build_describe_request(models, interface_id, subnet_id, name):
    request = models.DescribeNetworkInterfacesRequest()
    request.Limit = 100
    if interface_id:
        request.NetworkInterfaceIds = [interface_id]
    return request


def _first(collection):
    return collection[0] if collection else None


def _serialize(item):
    return item._serialize(allow_none=True)


def find_interface(module, client, models, interface_id, subnet_id, name):
    """Return the matching interface dict or None."""
    request = build_describe_request(models, interface_id, subnet_id, name)
    response = module.sdk_call(client.DescribeNetworkInterfaces, request)
    if interface_id:
        item = _first(response.NetworkInterfaceSet or [])
        return _serialize(item) if item is not None else None
    for item in response.NetworkInterfaceSet or []:
        current = _serialize(item)
        if current.get("NetworkInterfaceName") == name:
            if not subnet_id or current.get("SubnetId") == subnet_id:
                return current
    return None


def build_create_request(models, params):
    request = models.CreateNetworkInterfaceRequest()
    request.VpcId = params["vpc_id"]
    request.NetworkInterfaceName = params["name"]
    request.SubnetId = params["subnet_id"]
    if params["description"] is not None:
        request.NetworkInterfaceDescription = params["description"]
    if params["security_group_ids"]:
        request.SecurityGroupIds = params["security_group_ids"]
    if params["secondary_private_ip_count"] is not None:
        request.SecondaryPrivateIpAddressCount = params["secondary_private_ip_count"]
    if params["tags"]:
        request.Tags = _build_tags(models, params["tags"])
    return request


def _build_tags(models, tags):
    result = []
    for key, value in sorted(tags.items()):
        tag = models.Tag()
        tag.Key = key
        tag.Value = value
        result.append(tag)
    return result


def _create(module, client, models, params):
    request = build_create_request(models, params)
    response = module.sdk_call(client.CreateNetworkInterface, request)
    return getattr(response, "NetworkInterface", None) or getattr(response, "NetworkInterfaceId", None)


def _update(module, client, models, params, interface_id):
    request = models.ModifyNetworkInterfaceAttributeRequest()
    request.NetworkInterfaceId = interface_id
    if params["name"]:
        request.NetworkInterfaceName = params["name"]
    if params["description"] is not None:
        request.NetworkInterfaceDescription = params["description"]
    if params["security_group_ids"] is not None:
        request.SecurityGroupIds = params["security_group_ids"]
    module.sdk_call(client.ModifyNetworkInterfaceAttribute, request)


def _delete(module, client, models, interface_id):
    request = models.DeleteNetworkInterfaceRequest()
    request.NetworkInterfaceId = interface_id
    module.sdk_call(client.DeleteNetworkInterface, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "network_interface_id": {"type": "str"},
            "name": {"type": "str"},
            "vpc_id": {"type": "str"},
            "subnet_id": {"type": "str"},
            "description": {"type": "str"},
            "security_group_ids": {"type": "list", "elements": "str", "default": []},
            "secondary_private_ip_count": {"type": "int"},
            "tags": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    interface_id = module.params["network_interface_id"]
    name = module.params["name"]
    subnet_id = module.params["subnet_id"]

    if not interface_id and not name:
        module.fail_json(msg="network_interface_id or name is required to identify the interface")

    models, vpc_client = _load_vpc()
    client = module.create_client(vpc_client.VpcClient, "vpc.tencentcloudapi.com")

    try:
        current = find_interface(module, client, models, interface_id, subnet_id, name)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="Network interface already absent")
        target_id = current["NetworkInterfaceId"]
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete network interface")
        _delete(module, client, models, target_id)
        module.exit_json(changed=True, **(diff or {}), network_interface=None, msg="Network interface deleted")

    # state == present
    if current is None:
        missing = [key for key in ("name", "vpc_id", "subnet_id") if not module.params[key]]
        if missing:
            module.fail_json(msg="%s is required when creating a network interface" % ", ".join(missing))
        desired = {
            "NetworkInterfaceName": name,
            "VpcId": module.params["vpc_id"],
            "SubnetId": subnet_id,
        }
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create network interface")
        _create(module, client, models, module.params)
        current = find_interface(module, client, models, None, subnet_id, name)
        module.exit_json(changed=True, **(diff or {}), network_interface=current, msg="Network interface created")

    target_id = current["NetworkInterfaceId"]
    drift = {}
    if name and current.get("NetworkInterfaceName") != name:
        drift["NetworkInterfaceName"] = name
    if module.params["description"] is not None and current.get("NetworkInterfaceDescription") != module.params["description"]:
        drift["NetworkInterfaceDescription"] = module.params["description"]
    if module.params["security_group_ids"]:
        current_groups = sorted(_stringify(current.get("GroupSet") or []))
        desired_groups = sorted(module.params["security_group_ids"])
        if current_groups != desired_groups:
            drift["GroupSet"] = module.params["security_group_ids"]
    if drift:
        diff = maybe_diff(
            module,
            {key: current.get(key) for key in drift},
            drift,
        )
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would update network interface")
        _update(module, client, models, module.params, target_id)
        updated = find_interface(module, client, models, target_id, None, None)
        module.exit_json(changed=True, **(diff or {}), network_interface=updated, msg="Network interface updated")

    module.exit_json(changed=False, network_interface=current, msg="Network interface is up to date")


def _stringify(values):
    return [str(value) for value in values]


def main():
    run_module()


if __name__ == "__main__":
    main()
