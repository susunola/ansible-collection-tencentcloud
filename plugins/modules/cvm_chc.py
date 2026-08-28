#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cvm_chc
short_description: Manage Tencent Cloud CHC physical server network configuration
version_added: "0.13.0"
description:
  - Manage Tencent Cloud CHC (Cloud Hosting Center) physical servers through
    the CHC APIs of the C(cvm.v20170312) service.
  - CHC servers are physically delivered by Tencent Cloud and cannot be
    created or destroyed through an API, so this module configures their
    out-of-band (BMC) and deployment VPC networks, updates the instance
    name, and removes the network configuration when it is no longer
    needed.
  - This module is idempotent. Running it twice leaves the server
    unchanged and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) makes sure the CHC server exists and that its BMC and
        deployment VPC configuration matches O(bmc_vpc_id),
        O(bmc_subnet_id), O(deploy_vpc_id) and O(deploy_subnet_id) when
        they are given, updating it with V(ConfigureChcAssistVpc) when it
        drifts. The instance name is enforced with V(ModifyChcAttribute)
        when O(name) differs, and the network mode is enforced with
        V(ModifyChcNetworkMode) when O(network_mode) differs.
      - C(absent) removes the BMC and deployment VPC configuration with
        V(RemoveChcAssistVpc) and V(RemoveChcDeployVpc). The physical
        server itself is not destroyed.
    type: str
    choices: [present, absent]
    default: present
  chc_id:
    description:
      - ID of the CHC server, e.g. C(chc-xxxxxxxx).
      - When given, the module operates on that server; otherwise it is
        matched by O(name) through the C(instance-name) filter.
    type: str
  name:
    description:
      - Display name of the CHC server.
      - Used to look up the server when O(chc_id) is not given, and as the
        desired name to enforce on an existing server.
    type: str
  bmc_vpc_id:
    description:
      - ID of the out-of-band (BMC) VPC, written to
        V(ConfigureChcAssistVpcRequest.BmcVirtualPrivateCloud.VpcId).
      - Only applied when it drifts from the current configuration.
    type: str
  bmc_subnet_id:
    description:
      - ID of the out-of-band (BMC) subnet, written to
        V(ConfigureChcAssistVpcRequest.BmcVirtualPrivateCloud.SubnetId).
      - Only applied when it drifts from the current configuration.
    type: str
  bmc_security_group_ids:
    description:
      - Security groups for the out-of-band (BMC) network, written to
        V(ConfigureChcAssistVpcRequest.BmcSecurityGroupIds).
      - Only applied when it drifts from the current configuration.
    type: list
    elements: str
  deploy_vpc_id:
    description:
      - ID of the deployment VPC, written to
        V(ConfigureChcAssistVpcRequest.DeployVirtualPrivateCloud.VpcId).
      - Only applied when it drifts from the current configuration.
    type: str
  deploy_subnet_id:
    description:
      - ID of the deployment subnet, written to
        V(ConfigureChcAssistVpcRequest.DeployVirtualPrivateCloud.SubnetId).
      - Only applied when it drifts from the current configuration.
    type: str
  deploy_security_group_ids:
    description:
      - Security groups for the deployment network, written to
        V(ConfigureChcAssistVpcRequest.DeploySecurityGroupIds).
      - Only applied when it drifts from the current configuration.
    type: list
    elements: str
  network_mode:
    description:
      - Network mode of the CHC server's business NIC, written to
        V(ModifyChcNetworkModeRequest.NetworkMode).
      - C(DEPLOY) puts the server in deployment network mode, C(BUSINESS)
        in business network mode.
      - Only applied when it drifts from the current configuration as
        reported by V(DescribeChcHosts).
    type: str
    choices: [DEPLOY, BUSINESS]
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
  - CHC physical servers are delivered offline; this module fails when the
    targeted server does not exist instead of attempting to create it.
  - O(state=absent) only removes the network configuration; the physical
    server and its lease are left untouched.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Attach BMC and deployment VPCs to a CHC server
  susunola.tencentcloud.cvm_chc:
    region: ap-guangzhou
    state: present
    chc_id: chc-xxxxxxxx
    bmc_vpc_id: vpc-aaaaaaaa
    bmc_subnet_id: subnet-aaaaaaaa
    deploy_vpc_id: vpc-bbbbbbbb
    deploy_subnet_id: subnet-bbbbbbbb
    deploy_security_group_ids:
      - sg-xxxxxxxx

- name: Rename it
  susunola.tencentcloud.cvm_chc:
    region: ap-guangzhou
    state: present
    chc_id: chc-xxxxxxxx
    name: chc-prod-01

- name: Switch to business network mode
  susunola.tencentcloud.cvm_chc:
    region: ap-guangzhou
    state: present
    chc_id: chc-xxxxxxxx
    network_mode: BUSINESS

- name: Remove the network configuration (lease untouched)
  susunola.tencentcloud.cvm_chc:
    region: ap-guangzhou
    state: absent
    chc_id: chc-xxxxxxxx
'''

RETURN = r'''
chc_host:
  description: The CHC server as reported by V(DescribeChcHosts) after the
    operation.
  returned: success
  type: dict
  sample:
    ChcId: chc-xxxxxxxx
    InstanceName: chc-prod-01
    InstanceState: RUNNING
    DeviceType: CHC_10M
    BmcVirtualPrivateCloud:
      VpcId: vpc-aaaaaaaa
      SubnetId: subnet-aaaaaaaa
    DeployVirtualPrivateCloud:
      VpcId: vpc-bbbbbbbb
      SubnetId: subnet-bbbbbbbb
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_cvm():
    from tencentcloud.cvm.v20170312 import models, cvm_client
    return models, cvm_client


def build_describe_request(models, chc_id, name):
    request = models.DescribeChcHostsRequest()
    request.Offset = 0
    request.Limit = 100
    if chc_id:
        request.ChcIds = [chc_id]
    elif name:
        name_filter = models.Filter()
        name_filter.Name = "instance-name"
        name_filter.Values = [name]
        request.Filters = [name_filter]
    return request


def _first(collection):
    return collection[0] if collection else None


def find_host(module, client, models, chc_id, name):
    """Return the matching CHC host dict or None."""
    request = build_describe_request(models, chc_id, name)
    response = module.sdk_call(client.DescribeChcHosts, request)
    host = _first(response.ChcHostSet or [])
    if host is None:
        return None
    return host._serialize(allow_none=True)


def _network_request(models, params, vpc_key, subnet_key, sg_key):
    """Build a VirtualPrivateCloud model from the given params keys or None."""
    vpc_id = params.get(vpc_key)
    subnet_id = params.get(subnet_key)
    if not vpc_id and not subnet_id:
        return None
    network = models.VirtualPrivateCloud()
    network.VpcId = vpc_id
    network.SubnetId = subnet_id
    return network


def _current_network(host, key):
    """Return the serialized VPC dict under *key* or {}."""
    return host.get(key) or {}


def _network_drift(host, params, vpc_key, subnet_key):
    """Return True when the current VPC config differs from the params."""
    current = _current_network(host, vpc_key)
    vpc_id = params.get(vpc_key)
    subnet_id = params.get(subnet_key)
    if vpc_id and current.get("VpcId") != vpc_id:
        return True
    if subnet_id and current.get("SubnetId") != subnet_id:
        return True
    return False


def _security_group_drift(host, params, sg_key):
    """Return True when the current security groups differ from the params."""
    current = sorted(host.get(sg_key) or [])
    desired = sorted(params.get(sg_key) or [])
    return current != desired


def _configure_vpc(module, client, models, chc_id, params):
    request = models.ConfigureChcAssistVpcRequest()
    request.ChcIds = [chc_id]
    bmc_network = _network_request(models, params, "bmc_vpc_id", "bmc_subnet_id", "bmc_security_group_ids")
    if bmc_network is not None:
        request.BmcVirtualPrivateCloud = bmc_network
    if params.get("bmc_security_group_ids"):
        request.BmcSecurityGroupIds = params["bmc_security_group_ids"]
    deploy_network = _network_request(models, params, "deploy_vpc_id", "deploy_subnet_id", "deploy_security_group_ids")
    if deploy_network is not None:
        request.DeployVirtualPrivateCloud = deploy_network
    if params.get("deploy_security_group_ids"):
        request.DeploySecurityGroupIds = params["deploy_security_group_ids"]
    module.sdk_call(client.ConfigureChcAssistVpc, request)


def _rename(module, client, models, chc_id, name):
    request = models.ModifyChcAttributeRequest()
    request.ChcIds = [chc_id]
    request.InstanceName = name
    module.sdk_call(client.ModifyChcAttribute, request)


def _remove_assist(module, client, models, chc_id):
    request = models.RemoveChcAssistVpcRequest()
    request.ChcIds = [chc_id]
    module.sdk_call(client.RemoveChcAssistVpc, request)


def _remove_deploy(module, client, models, chc_id):
    request = models.RemoveChcDeployVpcRequest()
    request.ChcIds = [chc_id]
    module.sdk_call(client.RemoveChcDeployVpc, request)


def _set_network_mode(module, client, models, chc_id, network_mode):
    request = models.ModifyChcNetworkModeRequest()
    request.ChcIds = [chc_id]
    request.NetworkMode = network_mode
    module.sdk_call(client.ModifyChcNetworkMode, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "chc_id": {"type": "str"},
            "name": {"type": "str"},
            "bmc_vpc_id": {"type": "str"},
            "bmc_subnet_id": {"type": "str"},
            "bmc_security_group_ids": {"type": "list", "elements": "str"},
            "deploy_vpc_id": {"type": "str"},
            "deploy_subnet_id": {"type": "str"},
            "deploy_security_group_ids": {"type": "list", "elements": "str"},
            "network_mode": {"type": "str", "choices": ["DEPLOY", "BUSINESS"]},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    chc_id = module.params["chc_id"]
    name = module.params["name"]

    if not chc_id and not name:
        module.fail_json(msg="chc_id or name is required to identify the CHC server")

    models, cvm_client = _load_cvm()
    client = module.create_client(cvm_client.CvmClient, "cvm.tencentcloudapi.com")

    try:
        current = find_host(module, client, models, chc_id, name)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="CHC server already absent")
        target_id = current["ChcId"]
        # Removing a VPC configuration that is not attached is a no-op at
        # the API level, but report changed only when something was set.
        has_bmc = bool(current.get("BmcVirtualPrivateCloud") or current.get("BmcSecurityGroupIds"))
        has_deploy = bool(current.get("DeployVirtualPrivateCloud") or current.get("DeploySecurityGroupIds"))
        if not has_bmc and not has_deploy:
            module.exit_json(changed=False, chc_host=current, msg="CHC server has no network configuration")
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would remove CHC network configuration")
        if has_bmc:
            _remove_assist(module, client, models, target_id)
        if has_deploy:
            _remove_deploy(module, client, models, target_id)
        module.exit_json(changed=True, **(diff or {}), chc_host=None, msg="CHC network configuration removed")

    # state == present
    if current is None:
        module.fail_json(
            msg="CHC server not found; CHC servers are physically delivered "
                "by Tencent Cloud and cannot be created through an API",
            chc_id=chc_id,
            name=name,
        )

    target_id = current["ChcId"]
    drifted = (
        _network_drift(current, module.params, "bmc_vpc_id", "bmc_subnet_id")
        or _security_group_drift(current, module.params, "bmc_security_group_ids")
        or _network_drift(current, module.params, "deploy_vpc_id", "deploy_subnet_id")
        or _security_group_drift(current, module.params, "deploy_security_group_ids")
    )
    if drifted:
        desired = {}
        if module.params.get("bmc_vpc_id"):
            desired["BmcVirtualPrivateCloud"] = {
                "VpcId": module.params["bmc_vpc_id"],
                "SubnetId": module.params.get("bmc_subnet_id"),
            }
        if module.params.get("bmc_security_group_ids"):
            desired["BmcSecurityGroupIds"] = module.params["bmc_security_group_ids"]
        if module.params.get("deploy_vpc_id"):
            desired["DeployVirtualPrivateCloud"] = {
                "VpcId": module.params["deploy_vpc_id"],
                "SubnetId": module.params.get("deploy_subnet_id"),
            }
        if module.params.get("deploy_security_group_ids"):
            desired["DeploySecurityGroupIds"] = module.params["deploy_security_group_ids"]
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would configure CHC VPC networks")
        _configure_vpc(module, client, models, target_id, module.params)
        updated = find_host(module, client, models, target_id, None)
        module.exit_json(changed=True, **(diff or {}), chc_host=updated, msg="CHC VPC networks configured")

    if name and current.get("InstanceName") != name:
        diff = maybe_diff(module, current, {"InstanceName": name})
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would rename CHC server")
        _rename(module, client, models, target_id, name)
        updated = find_host(module, client, models, target_id, None)
        module.exit_json(changed=True, **(diff or {}), chc_host=updated, msg="CHC server renamed")

    network_mode = module.params.get("network_mode")
    if network_mode and current.get("NetworkMode") != network_mode:
        diff = maybe_diff(module, current, {"NetworkMode": network_mode})
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would switch CHC network mode")
        _set_network_mode(module, client, models, target_id, network_mode)
        updated = find_host(module, client, models, target_id, None)
        module.exit_json(changed=True, **(diff or {}), chc_host=updated, msg="CHC network mode switched")

    module.exit_json(changed=False, chc_host=current, msg="CHC server is up to date")


def main():
    run_module()


if __name__ == "__main__":
    main()
