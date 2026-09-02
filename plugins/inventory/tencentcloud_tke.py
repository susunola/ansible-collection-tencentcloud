# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
name: tencentcloud_tke
short_description: Tencent Cloud TKE dynamic inventory source (cluster nodes)
version_added: "0.14.0"
description:
  - List the nodes of Tencent Cloud TKE (Tencent Kubernetes Engine) clusters
    and expose them as Ansible hosts.
  - Every cluster of the region is walked; each cluster's instances are listed
    and only those whose C(InstanceRole) is in O(instance_roles) become hosts,
    so the default inventory is exactly the worker pool. Node-pool membership
    is resolved from the cluster's node pools and attached to the host
    variables.
  - Hosts are keyed by the first private IP (C(LanIP)) of the node, falling
    back to the instance ID when the node reports no address.
options:
  plugin:
    description: Marks this file as a Tencent Cloud TKE inventory source.
    type: str
    required: true
    choices: ["tencentcloud_tke", "susunola.tencentcloud.tencentcloud_tke"]
  regions:
    description:
      - Regions to query for TKE clusters.
      - Falls back to C(TENCENTCLOUD_REGION).
    type: list
    elements: str
    env:
      - name: TENCENTCLOUD_REGION
  cluster_ids:
    description:
      - Restrict the inventory to these cluster IDs, e.g. C([cls-xxxxxxxx]).
        When empty every cluster of the region is walked.
    type: list
    elements: str
    default: []
  instance_roles:
    description:
      - Instance roles to expose as hosts. TKE reports C(WORKER), C(MASTER)
        and C(EXTENSION); the default keeps the inventory to the worker pool.
    type: list
    elements: str
    default: ["WORKER"]
  hostnames:
    description:
      - Ordered list of hostname sources; the first entry producing a value wins.
      - The literal values C(private-ip) and C(instance-id) select the node's
        C(LanIP) and C(InstanceId); any other entry is evaluated as a Jinja2
        expression against the node variables.
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
      - Explicit options and their environment variables take precedence over
        the profile.
      - Falls back to C(TENCENTCLOUD_PROFILE).
    type: str
    env:
      - name: TENCENTCLOUD_PROFILE
extends_documentation_fragment:
  - constructed
  - inventory_cache
notes:
  - Requires the C(tencentcloud-sdk-python-tke) package on the controller.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
# Minimal source file, e.g. inventory.tencentcloud_tke.yml
plugin: susunola.tencentcloud.tencentcloud_tke
regions:
  - ap-guangzhou

# Worker nodes of one cluster only, grouped per cluster and node pool
plugin: susunola.tencentcloud.tencentcloud_tke
regions:
  - ap-guangzhou
cluster_ids:
  - cls-xxxxxxxx
keyed_groups:
  - key: ClusterId
    prefix: tke
  - key: NodePoolName
    prefix: tke_pool
compose:
  ansible_host: LanIP if LanIP else InstanceId
'''

from ansible.errors import AnsibleError
from ansible.plugins.inventory import BaseInventoryPlugin, Cacheable, Constructable

from ansible_collections.susunola.tencentcloud.plugins.module_utils.client import load_profile
from ansible_collections.susunola.tencentcloud.plugins.module_utils.paging import Paginator

try:
    from tencentcloud.common import credential as tc_credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.tke.v20180525 import models as tke_models
    from tencentcloud.tke.v20180525 import tke_client
    HAS_TENCENTCLOUD_SDK = True
except ImportError:
    HAS_TENCENTCLOUD_SDK = False


SDK_IMP_ERR = "The tencentcloud-sdk-python-tke package is required on the Ansible controller."

PAGE_SIZE = 100


def build_describe_clusters_request(models, cluster_ids, offset, limit):
    """Build a DescribeClusters request from inventory options."""
    request = models.DescribeClustersRequest()
    request.Offset = offset
    request.Limit = limit
    if cluster_ids:
        request.ClusterIds = cluster_ids
    return request


def build_describe_instances_request(models, cluster_id, offset, limit):
    """Build a DescribeClusterInstances request for one cluster."""
    request = models.DescribeClusterInstancesRequest()
    request.ClusterId = cluster_id
    request.Offset = offset
    request.Limit = limit
    return request


def serialize_instance(instance):
    """Convert an SDK instance model (or an already-plain dict) to a dict."""
    if hasattr(instance, "_serialize"):
        return instance._serialize(allow_none=True)
    return dict(instance)


def resolve_hostname(hostnames, node, compose):
    """Return the first usable hostname, private IP before instance ID."""
    for entry in hostnames or []:
        if entry == "private-ip":
            address = node.get("LanIP")
            if address:
                return str(address)
        elif entry == "instance-id":
            if node.get("InstanceId"):
                return str(node["InstanceId"])
        else:
            value = compose(entry, node)
            if value:
                return str(value)
    return None


def fetch_clusters(client, models, cluster_ids, page_size=PAGE_SIZE):
    """Return all clusters of one region as plain dicts, paging the API."""
    def build_request(offset, limit):
        return build_describe_clusters_request(models, cluster_ids, offset, limit)

    paginator = Paginator(
        page_size,
        build_request,
        client.DescribeClusters,
        lambda response: response.Clusters,
        lambda response: response.TotalCount,
    )
    items, _total = paginator.fetch_all()
    return [serialize_instance(item) for item in items]


def fetch_cluster_instances(client, models, cluster_id, page_size=PAGE_SIZE):
    """Return every instance of one cluster as plain dicts, paging the API."""
    def build_request(offset, limit):
        return build_describe_instances_request(models, cluster_id, offset, limit)

    paginator = Paginator(
        page_size,
        build_request,
        client.DescribeClusterInstances,
        lambda response: response.InstanceSet,
        lambda response: response.TotalCount,
    )
    items, _total = paginator.fetch_all()
    return [serialize_instance(item) for item in items]


def fetch_node_pools(client, models, cluster_id):
    """Return the NodePoolId -> Name map of one cluster.

    ``DescribeClusterNodePools`` returns every pool in one response, so no
    pagination is needed.
    """
    request = models.DescribeClusterNodePoolsRequest()
    request.ClusterId = cluster_id
    response = client.DescribeClusterNodePools(request)
    pools = {}
    for item in (response.NodePoolSet or []):
        data = serialize_instance(item)
        if data.get("NodePoolId"):
            pools[data["NodePoolId"]] = data.get("Name")
    return pools


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    NAME = "tencentcloud_tke"

    def verify_file(self, path):
        if super().verify_file(path):
            return path.endswith(("tencentcloud_tke.yml", "tencentcloud_tke.yaml"))
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
                results[region] = self._fetch_region(region)
        if cache_needs_update:
            self._cache[cache_key] = results
        self._populate(results)

    def _fetch_region(self, region):
        """Return the cluster-node list of one region as plain dicts."""
        client = self._create_client(region)
        clusters = fetch_clusters(
            client, tke_models, self.get_option("cluster_ids")
        )
        instance_roles = set(self.get_option("instance_roles"))
        nodes = []
        for cluster in clusters:
            cluster_id = cluster.get("ClusterId")
            if not cluster_id:
                continue
            pools = fetch_node_pools(client, tke_models, cluster_id)
            for node in fetch_cluster_instances(client, tke_models, cluster_id):
                if node.get("InstanceRole") not in instance_roles:
                    continue
                node["ClusterId"] = cluster_id
                node["ClusterName"] = cluster.get("ClusterName")
                node["ClusterStatus"] = cluster.get("ClusterStatus")
                node["ClusterVersion"] = cluster.get("ClusterVersion")
                pool_id = node.get("NodePoolId")
                node["NodePoolName"] = pools.get(pool_id) if pool_id else None
                nodes.append(node)
        return nodes

    def _create_client(self, region):
        """Build a TKE client for one region directly from the SDK."""
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
        http_profile.endpoint = "tke.tencentcloudapi.com"
        http_profile.reqTimeout = 60
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        client_profile.language = "en-US"
        credential = tc_credential.Credential(secret_id, secret_key, self.get_option("token"))
        return tke_client.TkeClient(credential, region, client_profile)

    def _populate(self, results):
        strict = self.get_option("strict")
        hostnames = self.get_option("hostnames")
        for region in sorted(results):
            for node in results[region]:
                hostname = resolve_hostname(hostnames, node, self._compose)
                if not hostname:
                    continue
                self.inventory.add_host(hostname)
                hostvars = dict(node)
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
