# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Resolve common Tencent Cloud resource names to stable resource IDs."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
name: resource_id
short_description: Resolve Tencent Cloud resource names to IDs
version_added: "0.14.0"
description:
  - Resolves exact resource names through Tencent Cloud read APIs.
  - Returns one ID per lookup term and fails when a name is absent or ambiguous.
  - Supports VPCs, subnets, security groups, CVM instances, CLB load balancers,
    TKE clusters and TencentDB for MySQL instances.
options:
  _terms:
    description: Exact resource names to resolve.
    required: true
  resource_type:
    description: Resource family to query.
    type: str
    required: true
    choices: [vpc, subnet, security_group, cvm_instance, clb_load_balancer, tke_cluster, cdb_instance]
  vpc_id:
    description: Optional VPC scope for subnet and CLB lookups.
    type: str
  region:
    description: Tencent Cloud region, falling back to C(TENCENTCLOUD_REGION).
    type: str
    env: [{name: TENCENTCLOUD_REGION}]
  secret_id:
    description: Tencent Cloud API secret ID.
    type: str
    env: [{name: TENCENTCLOUD_SECRET_ID}]
  secret_key:
    description: Tencent Cloud API secret key.
    type: str
    env: [{name: TENCENTCLOUD_SECRET_KEY}]
  token:
    description: Temporary credential token.
    type: str
    env: [{name: TENCENTCLOUD_TOKEN}]
  profile:
    description: TCCLI credential profile used as a fallback.
    type: str
    env: [{name: TENCENTCLOUD_PROFILE}]
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Resolve a VPC by exact name
  ansible.builtin.set_fact:
    production_vpc_id: >-
      {{ lookup('susunola.tencentcloud.resource_id', 'production',
                resource_type='vpc', region='ap-guangzhou') }}

- name: Resolve a subnet inside one VPC
  ansible.builtin.set_fact:
    app_subnet_id: >-
      {{ lookup('susunola.tencentcloud.resource_id', 'app-a',
                resource_type='subnet', vpc_id=production_vpc_id,
                region='ap-guangzhou') }}
'''

RETURN = r'''
_raw:
  description: IDs corresponding to the input terms in the same order.
  type: list
  elements: str
'''

import importlib

from ansible.errors import AnsibleError
from ansible.module_utils.common.text.converters import to_native
from ansible.plugins.lookup import LookupBase

from ansible_collections.susunola.tencentcloud.plugins.module_utils.client import load_profile

try:
    from tencentcloud.common import credential as tc_credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    HAS_TENCENTCLOUD_SDK = True
except ImportError:
    tc_credential = ClientProfile = HttpProfile = None
    HAS_TENCENTCLOUD_SDK = False


RESOURCE_SPECS = {
    "vpc": ("vpc.v20170312", "VpcClient", "vpc.tencentcloudapi.com", "DescribeVpcs", "VpcSet", "VpcId", "VpcName"),
    "subnet": ("vpc.v20170312", "VpcClient", "vpc.tencentcloudapi.com", "DescribeSubnets", "SubnetSet", "SubnetId", "SubnetName"),
    "security_group": ("vpc.v20170312", "VpcClient", "vpc.tencentcloudapi.com", "DescribeSecurityGroups", "SecurityGroupSet", "SecurityGroupId", "SecurityGroupName"),
    "cvm_instance": ("cvm.v20170312", "CvmClient", "cvm.tencentcloudapi.com", "DescribeInstances", "InstanceSet", "InstanceId", "InstanceName"),
    "clb_load_balancer": ("clb.v20180317", "ClbClient", "clb.tencentcloudapi.com", "DescribeLoadBalancers", "LoadBalancerSet", "LoadBalancerId", "LoadBalancerName"),
    "tke_cluster": ("tke.v20180525", "TkeClient", "tke.tencentcloudapi.com", "DescribeClusters", "Clusters", "ClusterId", "ClusterName"),
    "cdb_instance": ("cdb.v20170320", "CdbClient", "cdb.tencentcloudapi.com", "DescribeDBInstances", "Items", "InstanceId", "InstanceName"),
}


def build_request(resource_type, models, name, vpc_id=None):
    """Build the narrowest supported exact-name request."""
    request_names = {
        "vpc": "DescribeVpcsRequest",
        "subnet": "DescribeSubnetsRequest",
        "security_group": "DescribeSecurityGroupsRequest",
        "cvm_instance": "DescribeInstancesRequest",
        "clb_load_balancer": "DescribeLoadBalancersRequest",
        "tke_cluster": "DescribeClustersRequest",
        "cdb_instance": "DescribeDBInstancesRequest",
    }
    request = getattr(models, request_names[resource_type])()
    if resource_type in ("vpc", "subnet", "security_group"):
        request.Limit = "100"
    else:
        request.Limit = 100
    if resource_type == "cdb_instance":
        request.InstanceNames = [name]
    elif resource_type == "clb_load_balancer":
        request.LoadBalancerName = name
        if vpc_id:
            request.VpcId = vpc_id
    else:
        filter_names = {
            "vpc": "vpc-name",
            "subnet": "subnet-name",
            "security_group": "security-group-name",
            "cvm_instance": "instance-name",
            "tke_cluster": "cluster-name",
        }
        api_filter = models.Filter()
        api_filter.Name = filter_names[resource_type]
        api_filter.Values = [name]
        request.Filters = [api_filter]
        if resource_type == "subnet" and vpc_id:
            scope = models.Filter()
            scope.Name = "vpc-id"
            scope.Values = [vpc_id]
            request.Filters.append(scope)
    return request


def resolve_resource(client, models, resource_type, name, vpc_id=None):
    """Return one exact-match ID or raise a useful lookup error."""
    spec = RESOURCE_SPECS[resource_type]
    response = getattr(client, spec[3])(build_request(resource_type, models, name, vpc_id))
    matches = [item for item in (getattr(response, spec[4], None) or []) if getattr(item, spec[6], None) == name]
    if not matches:
        raise AnsibleError("No %s named %r was found" % (resource_type, name))
    if len(matches) > 1:
        raise AnsibleError("Multiple %s resources named %r matched; use an explicit ID" % (resource_type, name))
    return str(getattr(matches[0], spec[5]))


def sdk_error_message(resource_type, name, exc):
    detail = to_native(exc)
    code = getattr(exc, "get_code", lambda: None)()
    request_id = getattr(exc, "get_request_id", lambda: None)()
    if code:
        detail += " (%s)" % code
    if request_id:
        detail += " [RequestId: %s]" % request_id
    return "Resolve %s %r failed: %s" % (resource_type, name, detail)


class LookupModule(LookupBase):

    def run(self, terms, variables=None, **kwargs):
        if not HAS_TENCENTCLOUD_SDK:
            raise AnsibleError("The tencentcloud-sdk-python package is required on the Ansible controller.")
        self.set_options(var_options=variables, direct=kwargs)
        resource_type = self.get_option("resource_type")
        if resource_type not in RESOURCE_SPECS:
            raise AnsibleError("Unsupported resource_type %r" % resource_type)
        secret_id = self.get_option("secret_id")
        secret_key = self.get_option("secret_key")
        region = self.get_option("region")
        if not secret_id or not secret_key or not region:
            profile = load_profile(self.get_option("profile"))
            secret_id = secret_id or profile.get("secret_id")
            secret_key = secret_key or profile.get("secret_key")
            region = region or profile.get("region")
        if not secret_id or not secret_key or not region:
            raise AnsibleError("Set Tencent Cloud credentials and region explicitly, through environment variables, or in a TCCLI profile.")

        spec = RESOURCE_SPECS[resource_type]
        package = "tencentcloud.%s" % spec[0]
        models = importlib.import_module(package + ".models")
        client_module = importlib.import_module(package + "." + spec[0].split(".")[0] + "_client")
        profile = ClientProfile()
        profile.httpProfile = HttpProfile()
        profile.httpProfile.endpoint = spec[2]
        profile.httpProfile.reqTimeout = 60
        profile.language = "en-US"
        credential = tc_credential.Credential(secret_id, secret_key, self.get_option("token"))
        client = getattr(client_module, spec[1])(credential, region, profile)
        values = []
        for name in terms:
            try:
                values.append(resolve_resource(client, models, resource_type, name, self.get_option("vpc_id")))
            except AnsibleError:
                raise
            except Exception as exc:
                raise AnsibleError(sdk_error_message(resource_type, name, exc))
        return values
