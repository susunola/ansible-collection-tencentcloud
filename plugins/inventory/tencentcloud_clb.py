# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
name: tencentcloud_clb
short_description: Tencent Cloud CLB dynamic inventory source (backend instances)
version_added: "0.12.0"
description:
  - List the CVM instances registered as backends of Tencent Cloud CLB load
    balancers and expose them as Ansible hosts.
  - Useful for rolling deploys and maintenance windows; the inventory is
    derived from the load-balancing topology instead of a region-wide scan.
  - Hosts are keyed by the first private IP of the backend, falling back to
    the instance ID when the backend reports no address.
options:
  plugin:
    description: Marks this file as a Tencent Cloud CLB inventory source.
    type: str
    required: true
    choices: ["tencentcloud_clb", "susunola.tencentcloud.tencentcloud_clb"]
  regions:
    description:
      - Regions to query for load balancers.
      - Falls back to C(TENCENTCLOUD_REGION).
    type: list
    elements: str
    env:
      - name: TENCENTCLOUD_REGION
  load_balancer_ids:
    description:
      - Restrict the inventory to these load balancer IDs, e.g.
        C([lb-xxxxxxxx]). When empty every load balancer of the region is
        walked.
    type: list
    elements: str
    default: []
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
  - Requires the C(tencentcloud-sdk-python-clb) package on the controller.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
# Minimal source file, e.g. inventory.tencentcloud_clb.yml
plugin: susunola.tencentcloud.tencentcloud_clb
regions:
  - ap-guangzhou

# Only one load balancer; group hosts by listener protocol and port
plugin: susunola.tencentcloud.tencentcloud_clb
regions:
  - ap-guangzhou
load_balancer_ids:
  - lb-xxxxxxxx
keyed_groups:
  - key: protocol
    prefix: protocol
  - key: "listener_port"
    prefix: port
compose:
  ansible_host: instance_id
'''

from ansible.errors import AnsibleError
from ansible.plugins.inventory import BaseInventoryPlugin, Cacheable, Constructable

from ansible_collections.susunola.tencentcloud.plugins.module_utils.client import load_profile
from ansible_collections.susunola.tencentcloud.plugins.module_utils.paging import Paginator

try:
    from tencentcloud.clb.v20180317 import clb_client, models as clb_models
    from tencentcloud.common import credential as tc_credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    HAS_TENCENTCLOUD_SDK = True
except ImportError:
    HAS_TENCENTCLOUD_SDK = False


SDK_IMP_ERR = "The tencentcloud-sdk-python-clb package is required on the Ansible controller."

PAGE_SIZE = 100


def build_describe_lbs_request(models, load_balancer_ids, offset, limit):
    request = models.DescribeLoadBalancersRequest()
    request.Offset = offset
    request.Limit = limit
    if load_balancer_ids:
        request.LoadBalancerIds = load_balancer_ids
    return request


def list_load_balancers(client, models, load_balancer_ids):
    """Return all load balancers of the region as plain dicts."""
    paginator = Paginator(
        PAGE_SIZE,
        lambda offset, limit: build_describe_lbs_request(
            models, load_balancer_ids, offset, limit),
        client.DescribeLoadBalancers,
        lambda response: response.LoadBalancerSet,
        lambda response: response.TotalCount,
    )
    items, _total = paginator.fetch_all()
    return [serialize(item) for item in items]


def list_backends(client, models, load_balancer_id):
    """Return the backend targets of one load balancer.

    Walks DescribeListeners (one request per load balancer) then
    DescribeTargets for the whole load balancer; the response groups the
    backends per listener.
    """
    listeners_request = models.DescribeListenersRequest()
    listeners_request.LoadBalancerId = load_balancer_id
    listeners_response = client.DescribeListeners(listeners_request)
    listener_protocols = {}
    for listener in listeners_response.Listeners or []:
        listener_protocols[listener.ListenerId] = {
            "protocol": listener.Protocol,
            "port": listener.Port,
        }
    targets_request = models.DescribeTargetsRequest()
    targets_request.LoadBalancerId = load_balancer_id
    targets_response = client.DescribeTargets(targets_request)
    backends = []
    for group in targets_response.Targets or []:
        listener_id = group.ListenerId
        meta = listener_protocols.get(listener_id, {"protocol": None, "port": None})
        for target in group.Targets or []:
            serialized = serialize(target)
            serialized.update({
                "listener_id": listener_id,
                "protocol": meta["protocol"],
                "listener_port": meta["port"],
            })
            backends.append(serialized)
    return backends


def serialize(item):
    if hasattr(item, "_serialize"):
        return item._serialize(allow_none=True)
    return dict(item)


def backend_hostname(backend, hostnames, compose):
    """Return the first usable hostname for a backend target."""
    for entry in hostnames or []:
        if entry == "private-ip":
            addresses = backend.get("PrivateIpAddresses") or []
            if addresses:
                return str(addresses[0])
        elif entry == "instance-id":
            if backend.get("InstanceId"):
                return str(backend["InstanceId"])
        else:
            value = compose(entry, backend)
            if value:
                return str(value)
    return None


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    NAME = "tencentcloud_clb"

    def verify_file(self, path):
        if super().verify_file(path):
            return path.endswith(("tencentcloud_clb.yml", "tencentcloud_clb.yaml"))
        return False

    def parse(self, inventory, loader, path, cache=True):
        if not HAS_TENCENTCLOUD_SDK:
            raise AnsibleError(SDK_IMP_ERR)
        super().parse(inventory, loader, path, cache=cache)
        self._read_config_data(path)

        regions = self.get_option("regions")
        if not regions:
            raise AnsibleError("Set regions or the TENCENTCLOUD_REGION environment variable.")
        load_balancer_ids = self.get_option("load_balancer_ids") or []

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
                backends = []
                for load_balancer in list_load_balancers(client, clb_models, load_balancer_ids):
                    lb_meta = {
                        "lb_id": load_balancer.get("LoadBalancerId"),
                        "lb_name": load_balancer.get("LoadBalancerName"),
                        "lb_vips": load_balancer.get("LoadBalancerVips") or [],
                    }
                    for backend in list_backends(client, clb_models, lb_meta["lb_id"]):
                        backend.update(lb_meta)
                        backends.append(backend)
                results[region] = backends
        if cache_needs_update:
            self._cache[cache_key] = results
        self._populate(results)

    def _create_client(self, region):
        """Build a CLB client for one region directly from the SDK."""
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
        http_profile.endpoint = "clb.tencentcloudapi.com"
        http_profile.reqTimeout = 60
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        client_profile.language = "en-US"
        credential = tc_credential.Credential(secret_id, secret_key, self.get_option("token"))
        return clb_client.ClbClient(credential, region, client_profile)

    def _populate(self, results):
        strict = self.get_option("strict")
        hostnames = self.get_option("hostnames")
        for region in sorted(results):
            for backend in results[region]:
                hostname = backend_hostname(backend, hostnames, self._compose)
                if not hostname:
                    continue
                self.inventory.add_host(hostname)
                hostvars = dict(backend)
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
