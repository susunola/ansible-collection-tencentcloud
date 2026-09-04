#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tke_cluster_endpoint
short_description: Manage Tencent Cloud TKE cluster access endpoints
version_added: "0.14.0"
description: Creates or deletes a public or private Kubernetes API endpoint for a TKE cluster.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  cluster_id: {type: str, required: true, description: TKE cluster ID.}
  access: {type: str, choices: [public, private], default: private, description: Endpoint network scope.}
  subnet_id: {type: str, description: Subnet for a private endpoint.}
  domain: {type: str, description: Custom endpoint domain.}
  security_group_id: {type: str, description: Security group for the endpoint load balancer.}
  load_balancer_id: {type: str, description: Existing load balancer ID.}
  extensive_parameters: {type: dict, description: Public load-balancer parameters serialized as JSON.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tke_cluster_endpoint:
    cluster_id: cls-xxxxxxxx
    access: private
    subnet_id: subnet-xxxxxxxx
"""
RETURN = r"""endpoint: {description: Effective endpoint address and network metadata., type: dict, returned: always}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tke.v20180525 import models, tke_client

    return models, tke_client


def build_describe(models, cluster_id):
    request = models.DescribeClusterEndpointsRequest()
    request.ClusterId = cluster_id
    return request


def build_status(models, cluster_id, public):
    request = models.DescribeClusterEndpointStatusRequest()
    request.ClusterId, request.IsExtranet = cluster_id, public
    return request


def build_create(models, p):
    request = models.CreateClusterEndpointRequest()
    request.ClusterId, request.IsExtranet = p["cluster_id"], p["access"] == "public"
    request.SubnetId, request.Domain, request.SecurityGroup = p.get("subnet_id"), p.get("domain"), p.get("security_group_id")
    request.ExistedLoadBalancerId = p.get("load_balancer_id")
    if p.get("extensive_parameters") is not None:
        request.ExtensiveParameters = json.dumps(p["extensive_parameters"], sort_keys=True, separators=(",", ":"))
    return request


def build_delete(models, p):
    request = models.DeleteClusterEndpointRequest()
    request.ClusterId, request.IsExtranet = p["cluster_id"], p["access"] == "public"
    return request


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeClusterEndpoints, build_describe(models, p["cluster_id"]))
    public = p["access"] == "public"
    address = response.ClusterExternalEndpoint if public else response.ClusterIntranetEndpoint
    if not address:
        return None
    return {
        "ClusterId": p["cluster_id"],
        "Access": p["access"],
        "Endpoint": address,
        "Domain": response.ClusterExternalDomain if public else response.ClusterIntranetDomain,
        "SecurityGroup": response.SecurityGroup if public else response.IntranetSecurityGroup,
        "SubnetId": None if public else response.ClusterIntranetSubnetId,
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "cluster_id": {"required": True},
            "access": {"choices": ["public", "private"], "default": "private"},
            "subnet_id": {},
            "domain": {},
            "security_group_id": {},
            "load_balancer_id": {},
            "extensive_parameters": {"type": "dict"},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TkeClient, "tke.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        present = p["state"] == "present"
        target = {"ClusterId": p["cluster_id"], "Access": p["access"]}
        if (present and current) or (not present and not current):
            module.exit_json(changed=False, endpoint=current)
        diff = maybe_diff(module, current, target if present else None)
        if not module.check_mode:
            module.sdk_call(
                client.CreateClusterEndpoint if present else client.DeleteClusterEndpoint, build_create(models, p) if present else build_delete(models, p)
            )
            current = find(module, client, models, p) if present else None
        module.exit_json(changed=True, **(diff or {}), endpoint=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
