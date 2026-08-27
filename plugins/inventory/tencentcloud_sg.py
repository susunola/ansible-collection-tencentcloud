# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
name: tencentcloud_sg
short_description: Tencent Cloud security group dynamic inventory source
version_added: "0.12.0"
description:
  - List the instances attached to Tencent Cloud security groups and expose
    them as Ansible hosts.
  - The inventory is built from the network interfaces; every primary or
    secondary ENI that belongs to a listed security group contributes its
    instance as a host.
  - Hosts are keyed by the first private IP of the ENI, falling back to the
    instance ID when the ENI reports no address. An instance attached to
    several security groups is deduplicated; its C(sg_ids) host variable
    lists every security group it belongs to.
options:
  plugin:
    description: Marks this file as a Tencent Cloud security group inventory source.
    type: str
    required: true
    choices: ["tencentcloud_sg", "susunola.tencentcloud.tencentcloud_sg"]
  regions:
    description:
      - Regions to query for security groups.
      - Falls back to C(TENCENTCLOUD_REGION).
    type: list
    elements: str
    env:
      - name: TENCENTCLOUD_REGION
  security_group_ids:
    description:
      - Restrict the inventory to these security groups, e.g.
        C([sg-xxxxxxxx]). When empty every security group of the region is
        walked.
    type: list
    elements: str
    default: []
  include_sgless:
    description:
      - Whether to include ENIs that carry no matching security group when
        O(security_group_ids) is empty. Has no effect when
        O(security_group_ids) is set.
    type: bool
    default: false
  hostnames:
    description:
      - Ordered list of hostname sources; the first entry producing a value wins.
      - The literal values C(private-ip) and C(instance-id) select those
        fields; any other entry is evaluated as a Jinja2 expression against
        the host variables.
    type: list
    elements: str
    default: ["private-ip", "instance-id"]
  secret_id:
    description: Tencent Cloud API secret ID. Falls back to C(TENCENTCLOUD_SECRET_ID).
    type: str
    env:
      - name: TENCENTCLOUD_SECRET_ID
  secret_key:
    description: Tencent Cloud API secret key. Falls back to C(TENCENTCLOUD_SECRET_KEY).
    type: str
    env:
      - name: TENCENTCLOUD_SECRET_KEY
  token:
    description: Temporary credential token. Falls back to C(TENCENTCLOUD_TOKEN).
    type: str
    env:
      - name: TENCENTCLOUD_TOKEN
  profile:
    description:
      - TCCLI credential profile section of C(~/.tencentcloud/default.configure)
        used as a fallback for O(secret_id) and O(secret_key).
      - Falls back to C(TENCENTCLOUD_PROFILE).
    type: str
    env:
      - name: TENCENTCLOUD_PROFILE
extends_documentation_fragment:
  - constructed
  - inventory_cache
notes:
  - Requires the C(tencentcloud-sdk-python-vpc) package on the controller.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
# Minimal source file, e.g. inventory.tencentcloud_sg.yml
plugin: susunola.tencentcloud.tencentcloud_sg
regions:
  - ap-guangzhou

# Only the bastion security group; group hosts by SG id
plugin: susunola.tencentcloud.tencentcloud_sg
regions:
  - ap-guangzhou
security_group_ids:
  - sg-xxxxxxxx
keyed_groups:
  - key: sg_ids
    prefix: sg
compose:
  ansible_host: instance_id
'''

from ansible.errors import AnsibleError
from ansible.plugins.inventory import BaseInventoryPlugin, Cacheable, Constructable

from ansible_collections.susunola.tencentcloud.plugins.module_utils.client import load_profile
from ansible_collections.susunola.tencentcloud.plugins.module_utils.paging import Paginator

try:
    from tencentcloud.vpc.v20170312 import models as vpc_models, vpc_client
    from tencentcloud.common import credential as tc_credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    HAS_TENCENTCLOUD_SDK = True
except ImportError:
    HAS_TENCENTCLOUD_SDK = False


SDK_IMP_ERR = "The tencentcloud-sdk-python-vpc package is required on the Ansible controller."

PAGE_SIZE = 100


def build_list_sgs_request(models, security_group_ids, offset, limit):
    request = models.DescribeSecurityGroupsRequest()
    request.Offset = offset
    request.Limit = limit
    if security_group_ids:
        request.SecurityGroupIds = security_group_ids
    return request


def list_security_groups(client, models, security_group_ids):
    """Return the security groups of the region as plain dicts."""
    paginator = Paginator(
        PAGE_SIZE,
        lambda offset, limit: build_list_sgs_request(
            models, security_group_ids, offset, limit),
        client.DescribeSecurityGroups,
        lambda response: response.SecurityGroupSet,
        lambda response: response.TotalCount,
    )
    items, _total = paginator.fetch_all()
    return [serialize(item) for item in items]


def build_list_enis_request(models, security_group_id, offset, limit):
    request = models.DescribeNetworkInterfacesRequest()
    request.Offset = offset
    request.Limit = limit
    if security_group_id:
        sg_filter = models.Filter()
        sg_filter.Name = "security-group-id"
        sg_filter.Values = [security_group_id]
        request.Filters = [sg_filter]
    return request


def list_network_interfaces(client, models, security_group_id):
    """Return the ENIs of one security group (or all ENIs when None)."""
    paginator = Paginator(
        PAGE_SIZE,
        lambda offset, limit: build_list_enis_request(
            models, security_group_id, offset, limit),
        client.DescribeNetworkInterfaces,
        lambda response: response.NetworkInterfaceSet,
        lambda response: response.TotalCount,
    )
    items, _total = paginator.fetch_all()
    return [serialize(item) for item in items]


def eni_private_ip(eni):
    addresses = eni.get("PrivateIpAddresses") or []
    for address in addresses:
        if isinstance(address, dict) and address.get("PrivateIpAddress"):
            return str(address["PrivateIpAddress"])
    return None


def serialize(item):
    if hasattr(item, "_serialize"):
        return item._serialize(allow_none=True)
    return dict(item)


def eni_hostname(eni, hostnames, compose):
    """Return the first usable hostname for an ENI."""
    for entry in hostnames or []:
        if entry == "private-ip":
            address = eni_private_ip(eni)
            if address:
                return address
        elif entry == "instance-id":
            if eni.get("InstanceId"):
                return str(eni["InstanceId"])
        else:
            value = compose(entry, eni)
            if value:
                return str(value)
    return None


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    NAME = "tencentcloud_sg"

    def verify_file(self, path):
        if super().verify_file(path):
            return path.endswith(("tencentcloud_sg.yml", "tencentcloud_sg.yaml"))
        return False

    def parse(self, inventory, loader, path, cache=True):
        if not HAS_TENCENTCLOUD_SDK:
            raise AnsibleError(SDK_IMP_ERR)
        super().parse(inventory, loader, path, cache=cache)
        self._read_config_data(path)

        regions = self.get_option("regions")
        if not regions:
            raise AnsibleError("Set regions or the TENCENTCLOUD_REGION environment variable.")
        security_group_ids = self.get_option("security_group_ids") or []

        use_cache = self.get_option("cache") and cache
        cache_needs_update = use_cache
        results = None
        if use_cache:
            self.load_cache_plugin()
            cache_key = self.get_cache_key(path)
            try:
                results = self._cache[cache_key]
                cache_needs_update = False
            except KeyError:
                pass
        if results is None:
            results = {}
            for region in regions:
                client = self._create_client(region)
                hosts = {}
                groups = list_security_groups(client, vpc_models, security_group_ids)
                for group in groups:
                    group_id = group.get("SecurityGroupId")
                    enis = list_network_interfaces(client, vpc_models, group_id)
                    for eni in enis:
                        if not eni.get("InstanceId"):
                            continue
                        hostname = eni_hostname(eni, self.get_option("hostnames"), self._compose)
                        if not hostname:
                            continue
                        entry = hosts.setdefault(hostname, {
                            "hostname": hostname,
                            "instance_id": eni["InstanceId"],
                            "region": region,
                            "sg_ids": [],
                            "sg_names": [],
                        })
                        if group_id not in entry["sg_ids"]:
                            entry["sg_ids"].append(group_id)
                            entry["sg_names"].append(group.get("SecurityGroupName"))
                        entry["eni_ids"] = list(dict.fromkeys(
                            entry.get("eni_ids", []) + [eni["NetworkInterfaceId"]]
                        ))
                results[region] = list(hosts.values())
        if cache_needs_update:
            self._cache[cache_key] = results
        self._populate(results)

    def _create_client(self, region):
        """Build a VPC client for one region directly from the SDK."""
        secret_id = self.get_option("secret_id")
        secret_key = self.get_option("secret_key")
        if not secret_id or not secret_key:
            profile = load_profile(self.get_option("profile"))
            secret_id = secret_id or profile.get("secret_id")
            secret_key = secret_key or profile.get("secret_key")
        if not secret_id or not secret_key:
            raise AnsibleError(
                "Set secret_id and secret_key, their TENCENTCLOUD_* environment "
                "variables, or the secret_id/secret_key keys of a profile in "
                "~/.tencentcloud/default.configure."
            )
        http_profile = HttpProfile()
        http_profile.endpoint = "vpc.tencentcloudapi.com"
        http_profile.reqTimeout = 60
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        client_profile.language = "en-US"
        credential = tc_credential.Credential(secret_id, secret_key, self.get_option("token"))
        return vpc_client.VpcClient(credential, region, client_profile)

    def _populate(self, results):
        strict = self.get_option("strict")
        for region in sorted(results):
            for hostvars in results[region]:
                hostname = hostvars.pop("hostname", None)
                if not hostname:
                    continue
                self.inventory.add_host(hostname)
                hostvars = dict(hostvars)
                hostvars["region"] = region
                for key, value in hostvars.items():
                    self.inventory.set_variable(hostname, key, value)
                self._set_composite_vars(
                    self.get_option("compose"), hostvars, hostname, strict=strict
                )
                self._add_host_to_composed_groups(
                    self.get_option("groups"), hostvars, hostname, strict=strict
                )
                self._add_host_to_keyed_groups(
                    self.get_option("keyed_groups"), hostvars, hostname, strict=strict
                )
