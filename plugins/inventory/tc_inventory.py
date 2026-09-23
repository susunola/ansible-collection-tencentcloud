# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
name: tc_inventory
short_description: Unified Tencent Cloud asset inventory across CVM, TKE, Lighthouse, VPC, CLB, CDB, CBS and COS
version_added: "1.3.0"
description:
  - Build one Ansible inventory from several Tencent Cloud products at once,
    so that managing *existing* resources does not start with one query layer
    per product.
  - The per-product sources (C(tencentcloud_cvm), C(tencentcloud_tke), ...)
    remain the right tool when a playbook targets a single product and needs
    its product-specific options. This plugin is for the "inventory the
    estate" case, where one source file, one credential block and one cache
    entry should cover compute, network, storage and load balancing together.
  - Every host carries a standardised field set regardless of the product it
    came from (see O(hostnames) and the C(tc_*) variables below), so
    O(keyed_groups) and O(compose) expressions do not need a per-product
    branch. The raw API fields are kept as well, so nothing is lost.
options:
  plugin:
    description: Marks this file as a unified Tencent Cloud inventory source.
    type: str
    required: true
    choices: ["tc_inventory", "susunola.tencentcloud.tc_inventory"]
  sources:
    description:
      - Products to include, as a list.
      - >
        Valid values are C(cvm) (CVM instances), C(tke) (TKE cluster nodes),
        C(lighthouse) (Lighthouse instances), C(vpc) (VPCs), C(clb) (CLB load
        balancers), C(cdb) (CDB MySQL instances), C(cbs) (CBS disks) and
        C(cos) (COS buckets).
      - Sources are queried in the order given, which also decides which
        product's fields win when O(dedupe) merges two entries for the same
        resource.
    type: list
    elements: str
    default: ["cvm"]
  regions:
    description:
      - Regions to query, applied to every configured source.
      - Falls back to C(TENCENTCLOUD_REGION).
    type: list
    elements: str
    env:
      - name: TENCENTCLOUD_REGION
  filters:
    description:
      - API filters to narrow a source, keyed by source name.
      - >
        Each value is a list of C({name, values}) entries passed straight to
        that product's C(Describe*) API, for example
        C({cvm: [{name: instance-state, values: ["RUNNING"]}]}).
      - >
        Filters are per source on purpose: the filter namespace differs per
        product, so one shared list would be rejected by the products it does
        not apply to.
      - Naming a source that is not in O(sources) is an error.
    type: dict
    default: {}
  hostnames:
    description:
      - Ordered list of hostname sources; the first entry producing a value
        wins.
      - The literals C(private-ip), C(public-ip), C(id) and C(name) read the
        standardised fields described below; any other entry is evaluated as
        a Jinja2 expression against the host variables.
      - The default order covers every source, including the ones with no
        address of their own (a VPC is named after its C(VpcName)).
    type: list
    elements: str
    default: ["private-ip", "public-ip", "name", "id"]
  dedupe:
    description:
      - Whether to fold entries that share a resource ID into a single host.
      - >
        Overlap is real rather than theoretical: a TKE worker node is also a
        CVM instance, so both sources report the same C(i-xxxxxxxx). Merging
        keeps one host per resource, unions C(tc_sources) and merges list
        fields; the first source listed in O(sources) wins for scalars.
      - Set to C(false) to keep one host per source entry, for example when a
        VPC and an instance deliberately share a display name.
    type: bool
    default: true
  source_groups:
    description:
      - Whether to add every host to a C(tc_SOURCE) group, for example
        C(tc_cvm) or C(tc_vpc).
      - With O(dedupe) a host that several products report joins every
        matching group.
    type: bool
    default: true
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
  - >
    Requires the C(tencentcloud-sdk-python) distribution on the controller;
    the C(cvm), C(tke), C(lighthouse), C(vpc), C(clb), C(cdb) and C(cbs)
    clients ship in it.
  - >
    The C(cos) source additionally requires the C(cos-python-sdk-v5)
    distribution, because COS is not part of the API 3.0 family and has its
    own client model. It is the only source that ignores O(filters): the COS
    service call is region-scoped, so narrowing is done by O(regions).
  - The C(tke) source yields cluster I(worker and master) nodes rather than
    clusters, because a cluster has no address to connect to. Each node
    carries C(tc_parent_id) and C(tc_parent_name) for its cluster, plus the
    raw C(ClusterVersion), C(ClusterStatus), C(ClusterNodeNum) and
    C(NodePoolName) fields, so C(keyed_groups) can group by cluster or pool.
  - The C(vpc) source yields VPCs, which have no run state and no address;
    C(tc_state) is C(DEFAULT) for the default VPC of a region and C(null)
    otherwise, and C(CidrBlock) stays available as a raw field.
  - >
    C(clb) and C(cdb) report their run state as an integer; it is mapped to
    the same vocabulary the other sources use (C(CREATING), C(RUNNING),
    C(ISOLATING), C(ISOLATED)) and passed through as a string when the API
    grows a value this plugin does not know yet. For C(clb) the VIP is
    classified from C(LoadBalancerType): C(OPEN) fills C(tc_public_ip), any
    other value fills C(tc_private_ip).
  - >
    C(cbs) fills C(tc_parent_id) with the CVM the disk is attached to and
    C(tc_role) with its usage (C(SYSTEM_DISK) or C(DATA_DISK)); C(cos) fills
    C(tc_role) with the owning product reported by COS and leaves
    C(tc_tags) empty, because bucket tags need one extra call per bucket.
  - The cache key covers the query configuration (O(sources), O(regions),
    O(filters), O(dedupe)) in addition to the source file path, so editing
    any of them is a cache miss instead of a stale inventory.
  - Defined host variables - the standardised set is C(tc_source),
    C(tc_sources), C(tc_region), C(tc_id), C(tc_name), C(tc_state),
    C(tc_private_ip), C(tc_public_ip), C(tc_zone), C(tc_tags), C(tc_role),
    C(tc_parent_id) and C(tc_parent_name); fields a product has no concept of
    are C(null) rather than absent. C(tc_role) carries the product-specific
    sub-kind when the product has one - a TKE node role, a CBS disk usage, a
    CLB network type or a COS bucket product type.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
# Every CVM instance in two regions, the classic entry point
plugin: susunola.tencentcloud.tc_inventory
sources: [cvm]
regions:
  - ap-guangzhou
  - ap-singapore

# The whole estate: compute, containers, lightweight servers, networks,
# load balancers, databases and disks. Group by product once instead of
# writing one source file per product.
plugin: susunola.tencentcloud.tc_inventory
sources:
  - cvm
  - tke
  - lighthouse
  - vpc
  - clb
  - cdb
  - cbs
regions:
  - ap-singapore
keyed_groups:
  - key: tc_source
    prefix: tc
    separator: ""
  - key: tc_state
    prefix: state
    separator: ""
compose:
  ansible_host: tc_public_ip | default(tc_private_ip)

# Narrow two products differently; filters are keyed by source because the
# filter namespaces do not overlap.
plugin: susunola.tencentcloud.tc_inventory
sources: [cvm, vpc]
regions:
  - ap-guangzhou
filters:
  cvm:
    - name: instance-state
      values: ["RUNNING"]
  vpc:
    - name: vpc-id
      values: ["vpc-xxxxxxxx"]

# Storage and load balancing. COS needs cos-python-sdk-v5 on the controller
# and is narrowed by region, not by filters.
plugin: susunola.tencentcloud.tc_inventory
sources:
  - cbs
  - cos
regions:
  - ap-hongkong
keyed_groups:
  - key: tc_role
    prefix: kind
    separator: "_"
compose:
  ansible_host: tc_private_ip

# Report the estate rather than connect to it: name hosts after the resource
# id, and keep the raw API fields for later inventory-driven reporting.
plugin: susunola.tencentcloud.tc_inventory
sources: [cvm, tke, lighthouse, vpc]
regions:
  - ap-singapore
hostnames:
  - id
strict: false
'''

from ansible.errors import AnsibleError
from ansible.plugins.inventory import BaseInventoryPlugin, Cacheable, Constructable

from ansible_collections.susunola.tencentcloud.plugins.plugin_utils.inventory import (
    InventorySourceError,
    build_cache_key,
    build_client,
    collect_source,
    describe_entry,
    hostname_of,
    merge_entries,
    resolve_credentials,
    resolve_sources,
)


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    NAME = "tc_inventory"

    def verify_file(self, path):
        if super().verify_file(path):
            return path.endswith(("tc_inventory.yml", "tc_inventory.yaml"))
        return False

    def parse(self, inventory, loader, path, cache=True):
        super().parse(inventory, loader, path, cache=cache)
        self._read_config_data(path)

        specs = self._specs()
        regions = self.get_option("regions")
        if not regions:
            raise AnsibleError("Set regions or the TENCENTCLOUD_REGION environment variable.")
        filters = self._source_filters(specs)
        dedupe = self.get_option("dedupe")

        use_cache = self.get_option("cache") and cache
        cache_key = None
        results = None
        if use_cache:
            self.load_cache_plugin()
            # Unlike Cacheable.get_cache_key(), this key covers the query
            # configuration too: changing regions or filters must not keep
            # serving the previous inventory until the cache expires.
            cache_key = build_cache_key(self.NAME, path, {
                "sources": [spec.name for spec in specs],
                "regions": list(regions),
                "filters": filters,
                "dedupe": dedupe,
            })
            try:
                results = self._cache[cache_key]
            except KeyError:
                results = None
        if results is None:
            results = self._fetch_all(specs, regions, filters, dedupe)
            if use_cache:
                self._cache[cache_key] = results
        self._populate(results)

    def _specs(self):
        """Return the validated source specs, in the configured order."""
        try:
            return resolve_sources(self.get_option("sources"))
        except InventorySourceError as exc:
            raise AnsibleError(str(exc))

    def _source_filters(self, specs):
        """Return the per-source filter mapping, checking the source names."""
        configured = self.get_option("filters") or {}
        if not isinstance(configured, dict):
            raise AnsibleError(
                "filters must be a mapping of source name to API filter list, "
                "for example {'cvm': [{'name': 'instance-state', "
                "'values': ['RUNNING']}]}."
            )
        enabled = [spec.name for spec in specs]
        selected = {}
        for name, entries in configured.items():
            if name not in enabled:
                raise AnsibleError(
                    "filters has an entry for '{0}', which is not an enabled "
                    "source. Enabled sources: {1}.".format(name, ", ".join(enabled))
                )
            selected[name] = entries or []
        return selected

    def _fetch_all(self, specs, regions, filters, dedupe):
        """Return ``{region: [entry]}`` for every source and region."""
        results = {}
        for region in regions:
            entries = []
            for spec in specs:
                entries.extend(self._fetch_source(spec, region, filters.get(spec.name)))
            results[region] = merge_entries(entries) if dedupe else entries
        return results

    def _fetch_source(self, spec, region, filters):
        """Return the standardised entries of one source in one region."""
        try:
            secret_id, secret_key, token = resolve_credentials(
                self.get_option("secret_id"),
                self.get_option("secret_key"),
                self.get_option("token"),
                self.get_option("profile"),
            )
            client = build_client(spec, region, secret_id, secret_key, token)
            items = collect_source(spec, client, filters, region=region)
        except InventorySourceError as exc:
            raise AnsibleError(str(exc))
        return [describe_entry(spec, region, item) for item in items]

    def _populate(self, results):
        strict = self.get_option("strict")
        hostnames = self.get_option("hostnames")
        source_groups = self.get_option("source_groups")
        for region in sorted(results):
            for entry in results[region]:
                hostname = hostname_of(hostnames, entry, self._compose)
                if not hostname:
                    continue
                self.inventory.add_host(hostname)
                hostvars = dict(entry)
                hostvars["region"] = region
                for key, value in hostvars.items():
                    self.inventory.set_variable(hostname, key, value)
                if source_groups:
                    for source in hostvars.get("tc_sources") or []:
                        group = "tc_{0}".format(source)
                        # add_host() does not create the group; in recent
                        # ansible-core it raises "Could not find group" when
                        # the group is absent, despite its docstring.
                        self.inventory.add_group(group)
                        self.inventory.add_host(hostname, group=group)
                self._set_composite_vars(
                    self.get_option("compose"), hostvars, hostname, strict=strict
                )
                self._add_host_to_composed_groups(
                    self.get_option("groups"), hostvars, hostname, strict=strict
                )
                self._add_host_to_keyed_groups(
                    self.get_option("keyed_groups"), hostvars, hostname, strict=strict
                )
