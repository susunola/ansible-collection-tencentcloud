# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
name: tencentcloud_cvm
short_description: Tencent Cloud CVM dynamic inventory source
version_added: "0.4.0"
description:
  - List Tencent Cloud CVM instances and expose them as Ansible hosts.
  - Hosts are keyed by private IP address, falling back to the public IP
    when the instance has no private address.
options:
  plugin:
    description: Marks this file as a Tencent Cloud CVM inventory source.
    type: str
    required: true
    choices: ["tencentcloud_cvm", "tencentcloud.cloud.tencentcloud_cvm"]
  regions:
    description:
      - Regions to query for CVM instances.
      - Falls back to C(TENCENTCLOUD_REGION).
    type: list
    elements: str
    env:
      - name: TENCENTCLOUD_REGION
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
  filters:
    description:
      - Filters passed straight to the C(DescribeInstances) API.
      - Each entry is a dict with O(filters[].name) and O(filters[].values),
        for example I(name=instance-state) with I(values=["RUNNING"]).
    type: list
    elements: dict
    default: []
    suboptions:
      name:
        description: API filter name, for example C(instance-state) or C(zone).
        type: str
        required: true
      values:
        description: Filter values.
        type: list
        elements: str
        default: []
  hostnames:
    description:
      - Ordered list of hostname sources; the first entry producing a value wins.
      - The literal values C(private-ip) and C(public-ip) select the first
        address of that kind; any other entry is evaluated as a Jinja2
        expression against the instance variables.
    type: list
    elements: str
    default: ["private-ip", "public-ip"]
extends_documentation_fragment:
  - constructed
  - inventory_cache
notes:
  - Requires the C(tencentcloud-sdk-python-cvm) package on the controller.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
# Minimal source file, e.g. inventory.tencentcloud_cvm.yml
plugin: tencentcloud.cloud.tencentcloud_cvm
regions:
  - ap-guangzhou

# Filter running instances, group by image and compose ansible_host
plugin: tencentcloud.cloud.tencentcloud_cvm
regions:
  - ap-guangzhou
filters:
  - name: instance-state
    values: ["RUNNING"]
hostnames:
  - InstanceName
  - private-ip
keyed_groups:
  - key: ImageId
    prefix: image
compose:
  ansible_host: PublicIpAddresses[0] if PublicIpAddresses else PrivateIpAddresses[0]
'''

from ansible.errors import AnsibleError
from ansible.plugins.inventory import BaseInventoryPlugin, Cacheable, Constructable

from ansible_collections.tencentcloud.cloud.plugins.module_utils.paging import Paginator

try:
    from tencentcloud.cvm.v20170312 import cvm_client, models as cvm_models
    from tencentcloud.common import credential as tc_credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    HAS_TENCENTCLOUD_SDK = True
except ImportError:
    HAS_TENCENTCLOUD_SDK = False


SDK_IMP_ERR = "The tencentcloud-sdk-python-cvm package is required on the Ansible controller."

PAGE_SIZE = 100


def build_describe_request(models, filters, offset, limit):
    """Build a DescribeInstances request from inventory options."""
    request = models.DescribeInstancesRequest()
    request.Offset = offset
    request.Limit = limit
    if filters:
        request.Filters = []
        for entry in filters:
            api_filter = models.Filter()
            api_filter.Name = entry.get("name")
            values = entry.get("values") or []
            api_filter.Values = values if isinstance(values, list) else [values]
            request.Filters.append(api_filter)
    return request


def serialize_instance(instance):
    """Convert an SDK instance model (or an already-plain dict) to a dict."""
    if hasattr(instance, "_serialize"):
        return instance._serialize(allow_none=True)
    return dict(instance)


def fetch_instances(client, models, filters, page_size=PAGE_SIZE):
    """Return all instances of one region as plain dicts, paging the API."""
    def build_request(offset, limit):
        return build_describe_request(models, filters, offset, limit)

    paginator = Paginator(
        page_size,
        build_request,
        client.DescribeInstances,
        lambda response: response.InstanceSet,
        lambda response: response.TotalCount,
    )
    items, _total = paginator.fetch_all()
    return [serialize_instance(item) for item in items]


def resolve_hostname(hostnames, instance, compose):
    """Return the first usable hostname, private IP before public IP.

    :param hostnames: ordered list of hostname sources from the config.
    :param instance: the instance as a plain dict.
    :param compose: callable(template, variables) evaluating Jinja2 entries.
    """
    for entry in hostnames or []:
        if entry == "private-ip":
            addresses = instance.get("PrivateIpAddresses") or []
            if addresses:
                return str(addresses[0])
        elif entry == "public-ip":
            addresses = instance.get("PublicIpAddresses") or []
            if addresses:
                return str(addresses[0])
        else:
            value = compose(entry, instance)
            if value:
                return str(value)
    return None


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    NAME = "tencentcloud_cvm"

    def verify_file(self, path):
        if super().verify_file(path):
            return path.endswith(("tencentcloud_cvm.yml", "tencentcloud_cvm.yaml"))
        return False

    def parse(self, inventory, loader, path, cache=True):
        if not HAS_TENCENTCLOUD_SDK:
            raise AnsibleError(SDK_IMP_ERR)
        super().parse(inventory, loader, path, cache=cache)
        self._read_config_data(path)

        regions = self.get_option("regions")
        if not regions:
            raise AnsibleError("Set regions or the TENCENTCLOUD_REGION environment variable.")

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
                results[region] = fetch_instances(
                    self._create_client(region), cvm_models, self.get_option("filters")
                )
        if cache_needs_update:
            self._cache[cache_key] = results
        self._populate(results)

    def _create_client(self, region):
        """Build a CVM client for one region directly from the SDK."""
        secret_id = self.get_option("secret_id")
        secret_key = self.get_option("secret_key")
        if not secret_id or not secret_key:
            raise AnsibleError(
                "Set secret_id and secret_key, or their TENCENTCLOUD_* environment variables."
            )
        http_profile = HttpProfile()
        http_profile.endpoint = "cvm.tencentcloudapi.com"
        http_profile.reqTimeout = 60
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        client_profile.language = "en-US"
        credential = tc_credential.Credential(secret_id, secret_key, self.get_option("token"))
        return cvm_client.CvmClient(credential, region, client_profile)

    def _populate(self, results):
        strict = self.get_option("strict")
        hostnames = self.get_option("hostnames")
        for region in sorted(results):
            for instance in results[region]:
                hostname = resolve_hostname(hostnames, instance, self._compose)
                if not hostname:
                    continue
                self.inventory.add_host(hostname)
                hostvars = dict(instance)
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
