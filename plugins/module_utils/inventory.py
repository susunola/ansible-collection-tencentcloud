# -*- coding: utf-8 -*-
"""Shared multi-product query layer behind the dynamic inventory plugins.

The per-product inventory plugins (``tencentcloud_cvm``, ``tencentcloud_tke``,
…) each answer one question well, but they cannot answer "show me every
existing resource I can manage" — a play that wants compute *and* network
assets needs one source file per product, one credential block per file and
one cache entry per file, and the resulting hosts have no fields in common.

This module is the shared half of the unified ``tc_inventory`` plugin:

* **Query** — a source registry (:data:`SOURCE_SPECS`) describing, per
  product, which SDK package/client/request/response to use, plus collectors
  built on :class:`~ansible_collections.susunola.tencentcloud.plugins.module_utils.paging.Paginator`.
  Nested products (TKE lists nodes *inside* clusters) get their own collector
  instead of a flat ``Describe*`` walk.
* **Standardised fields** — every entry carries the same ``tc_*`` key set
  (``tc_source`` / ``tc_region`` / ``tc_id`` / ``tc_name`` / ``tc_state`` /
  ``tc_private_ip`` / ``tc_public_ip`` / ``tc_zone`` / ``tc_tags`` /
  ``tc_role`` / ``tc_parent_id`` / ``tc_parent_name``) regardless of product,
  so ``keyed_groups`` and ``compose`` expressions do not need a per-product
  branch. The raw API fields are kept alongside them, so nothing is lost.
* **De-duplication** — :func:`merge_entries` folds entries that share a
  ``tc_id`` into one host. This matters because Tencent Cloud resources
  genuinely overlap: a TKE worker node *is* a CVM instance and reports the
  same ``i-xxxx`` id from both products.
* **Cache keying** — :func:`build_cache_key` hashes the query *configuration*
  (sources, regions, filters) instead of just the source path, so changing
  ``regions`` or ``filters`` cannot silently serve a stale inventory.

The implementation lives here rather than in ``plugin_utils`` because
ansible-test's ``import`` test lets module-side code import only
``plugins.module_utils``; ``plugin_utils.inventory`` re-exports it for the
controller-side plugin. See ``plugins/plugin_utils/README.md``.

The SDK is **never imported at module level**: clients and model modules are
resolved through :func:`importlib.import_module` at query time. That keeps
this module — and the plugin that uses it — importable and unit-testable
without the ``tencentcloud`` package installed, the same property the
per-product plugins achieve with their ``HAS_TENCENTCLOUD_SDK`` gates.

Layering: imports ``module_utils.client`` and ``module_utils.paging``.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import hashlib
import importlib
import json

from ansible_collections.susunola.tencentcloud.plugins.module_utils.client import (
    load_profile,
)
from ansible_collections.susunola.tencentcloud.plugins.module_utils.paging import (
    Paginator,
)

PAGE_SIZE = 100


class InventorySourceError(Exception):
    """A source cannot be queried: unknown name, missing SDK, bad option."""


class SourceSpec(object):
    """Static description of one inventory source.

    :param name: source name as written in the ``sources`` option.
    :param label: human-readable product name used in documentation.
    :param sdk_package: distribution that provides the client, for error
        messages when it is not installed.
    :param endpoint: API endpoint host of the product.
    :param client_module: dotted path of the module holding the client class.
    :param client_class: name of the client class inside that module.
    :param models_module: dotted path of the request/response models module.
    :param request_class: request model used to walk the collection.
    :param describe: client method that performs the walk.
    :param items_attr: response attribute holding the page of items.
    :param total_attr: response attribute holding the total count.
    :param normalizer: callable(region, item) -> standardised ``tc_*`` dict.
    :param child_request_class: request model for the nested walk, when the
        product does not expose its assets in one flat ``Describe*`` call.
    :param child_describe: client method performing that nested walk.
    :param child_items_attr: response attribute holding the nested page.
    :param collector: callable replacing the default flat collector.
    :param string_paging: whether this product's API rejects integer
        ``Offset``/``Limit``. The four first-batch products are not
        consistent here: CVM, TKE and Lighthouse declare both as ``int64``
        and answer ``InvalidParameter`` for a string, while VPC declares both
        as ``string`` and answers ``InvalidParameter`` for an integer. The
        flag keeps that per-product fact in the registry instead of in the
        request builder.
    """

    def __init__(self, name, label, sdk_package, endpoint, client_module,
                 client_class, models_module, request_class, describe,
                 items_attr, total_attr, normalizer, child_request_class=None,
                 child_describe=None, child_items_attr=None, collector=None,
                 string_paging=False):
        self.name = name
        self.label = label
        self.sdk_package = sdk_package
        self.endpoint = endpoint
        self.client_module = client_module
        self.client_class = client_class
        self.models_module = models_module
        self.request_class = request_class
        self.describe = describe
        self.items_attr = items_attr
        self.total_attr = total_attr
        self.normalizer = normalizer
        self.child_request_class = child_request_class
        self.child_describe = child_describe
        self.child_items_attr = child_items_attr
        self.collector = collector
        self.string_paging = string_paging

    def __repr__(self):
        return "<SourceSpec {0}>".format(self.name)


# ---------------------------------------------------------------------------
# Response handling
# ---------------------------------------------------------------------------

def serialize(item):
    """Convert an SDK model (or an already-plain mapping) to a plain dict."""
    if hasattr(item, "_serialize"):
        return item._serialize(allow_none=True)
    return dict(item)


def tag_mapping(tags):
    """Normalise an API-shaped tag list or mapping into a plain mapping.

    Tencent Cloud returns tags as ``[{"Key": ..., "Value": ...}]`` on CVM and
    Lighthouse and as ``TagSet`` on VPC; both shapes (and an already-plain
    mapping) end up as one dict, which is what ``keyed_groups`` and
    ``selectattr`` consume most easily.
    """
    if isinstance(tags, dict):
        return dict(tags)
    result = {}
    for entry in tags or []:
        if isinstance(entry, dict):
            key = entry.get("Key")
            value = entry.get("Value")
        else:
            key = getattr(entry, "Key", None)
            value = getattr(entry, "Value", None)
        if key:
            result[key] = value
    return result


def _first(mapping, *names):
    """Return the first non-empty value among ``names``."""
    for name in names:
        value = mapping.get(name)
        if value not in (None, "", [], {}):
            return value
    return None


def _plain_list(value):
    """Return ``value`` as a list of plain scalars."""
    if not value:
        return []
    if not isinstance(value, (list, tuple)):
        value = [value]
    return [item for item in value if item not in (None, "")]


def _first_of(values):
    """Return the first usable entry of an API address list."""
    for value in _plain_list(values):
        return value
    return None


def _nested(mapping, key, *names):
    """Return the first non-empty scalar of a nested mapping."""
    nested = mapping.get(key)
    if isinstance(nested, dict):
        return _first(nested, *names)
    return None


# ---------------------------------------------------------------------------
# Per-product normalisers
#
# Each returns the same key set so that a playbook can treat every host
# uniformly; keys that a product has no concept of stay None rather than
# being absent, so ``hostvars[host].tc_zone`` never raises.
# ---------------------------------------------------------------------------

def normalize_cvm(region, item):
    """Standardise one CVM instance."""
    return {
        "tc_region": region,
        "tc_id": _first(item, "InstanceId"),
        "tc_name": _first(item, "InstanceName"),
        "tc_state": _first(item, "InstanceState"),
        "tc_private_ip": _first_of(item.get("PrivateIpAddresses")),
        "tc_public_ip": _first_of(item.get("PublicIpAddresses")),
        "tc_zone": _nested(item, "Placement", "Zone"),
        "tc_tags": tag_mapping(item.get("Tags") or []),
        "tc_role": None,
        "tc_parent_id": None,
        "tc_parent_name": None,
    }


def normalize_lighthouse(region, item):
    """Standardise one Lighthouse (lightweight application server) instance."""
    return {
        "tc_region": region,
        "tc_id": _first(item, "InstanceId"),
        "tc_name": _first(item, "InstanceName"),
        "tc_state": _first(item, "InstanceState"),
        "tc_private_ip": _first_of(item.get("PrivateAddresses")),
        "tc_public_ip": _first_of(item.get("PublicAddresses")),
        "tc_zone": _first(item, "Zone"),
        "tc_tags": tag_mapping(item.get("Tags") or []),
        "tc_role": None,
        "tc_parent_id": None,
        "tc_parent_name": None,
    }


def normalize_tke_node(region, item):
    """Standardise one TKE cluster node.

    A node has a private address (``LanIP``) and no public address of its
    own, and belongs to a cluster, which fills the ``tc_parent_*`` pair.
    """
    return {
        "tc_region": region,
        "tc_id": _first(item, "InstanceId"),
        "tc_name": _first(item, "InstanceId"),
        "tc_state": _first(item, "InstanceState"),
        "tc_private_ip": _first(item, "LanIP"),
        "tc_public_ip": None,
        "tc_zone": None,
        "tc_tags": tag_mapping(item.get("Tags") or []),
        "tc_role": _first(item, "InstanceRole"),
        "tc_parent_id": _first(item, "ClusterId"),
        "tc_parent_name": _first(item, "ClusterName"),
    }


def normalize_vpc(region, item):
    """Standardise one VPC.

    A VPC has no run state and no address of its own; ``CidrBlock`` stays
    available as a raw field, and ``IsDefault`` tells the two kinds apart.
    """
    return {
        "tc_region": region,
        "tc_id": _first(item, "VpcId"),
        "tc_name": _first(item, "VpcName"),
        "tc_state": "DEFAULT" if item.get("IsDefault") else None,
        "tc_private_ip": None,
        "tc_public_ip": None,
        "tc_zone": None,
        "tc_tags": tag_mapping(item.get("TagSet") or []),
        "tc_role": None,
        "tc_parent_id": None,
        "tc_parent_name": None,
    }


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------

def build_filter(models, entry):
    """Build one API ``Filter`` object from a ``{name, values}`` mapping."""
    api_filter = models.Filter()
    api_filter.Name = entry.get("name")
    values = entry.get("values") or []
    api_filter.Values = values if isinstance(values, list) else [values]
    return api_filter


def build_request(request_class, models, filters, offset, limit, extra=None,
                  string_paging=False):
    """Build one page request, applying filters and product-specific fields.

    ``string_paging`` serialises ``Offset``/``Limit`` as strings for the
    products that declare them that way (VPC); the default keeps them as
    integers, which is what CVM, TKE and Lighthouse require.
    """
    request = request_class()
    if string_paging:
        request.Offset = str(offset)
        request.Limit = str(limit)
    else:
        request.Offset = offset
        request.Limit = limit
    if filters:
        request.Filters = [build_filter(models, entry) for entry in filters]
    for name, value in (extra or {}).items():
        setattr(request, name, value)
    return request


def _paged(spec, client, models, filters, page_size, request_class, extra=None,
           describe=None, items_attr=None):
    """Walk one paginated ``Describe*`` call and return plain dicts.

    ``describe`` and ``items_attr`` default to the spec's own listing call and
    response field; a source that walks a nested collection (TKE nodes inside
    clusters) passes its child equivalents.
    """
    paginator = Paginator(
        page_size,
        lambda offset, limit: build_request(
            request_class, models, filters, offset, limit, extra,
            string_paging=spec.string_paging),
        getattr(client, describe or spec.describe),
        lambda response: getattr(response, items_attr or spec.items_attr) or [],
        lambda response: getattr(response, spec.total_attr),
    )
    items, _total = paginator.fetch_all()
    return [serialize(item) for item in items]


def collect_flat(spec, client, models, filters, page_size=PAGE_SIZE):
    """Return every item of a product that lists its assets in one call."""
    return _paged(spec, client, models, filters, page_size,
                  getattr(models, spec.request_class))


def _fetch_node_pools(client, models, cluster_id):
    """Return the ``NodePoolId -> Name`` map of one cluster.

    ``DescribeClusterNodePools`` returns every pool in one response.
    """
    request = models.DescribeClusterNodePoolsRequest()
    request.ClusterId = cluster_id
    response = client.DescribeClusterNodePools(request)
    pools = {}
    for item in (response.NodePoolSet or []):
        data = serialize(item)
        if data.get("NodePoolId"):
            pools[data["NodePoolId"]] = data.get("Name")
    return pools


def collect_tke_nodes(spec, client, models, filters, page_size=PAGE_SIZE):
    """Return every node of every cluster, annotated with its cluster.

    TKE has no region-wide node listing: nodes are reachable only through
    their cluster, and the node pool name only through a third call. The
    cluster and pool names are added to the node itself so the resulting host
    can be grouped by either without a second lookup.
    """
    clusters = collect_flat(spec, client, models, filters, page_size)
    nodes = []
    for cluster in clusters:
        cluster_id = cluster.get("ClusterId")
        if not cluster_id:
            continue
        pools = _fetch_node_pools(client, models, cluster_id)
        for node in _paged(
                spec, client, models, filters, page_size,
                getattr(models, spec.child_request_class),
                {"ClusterId": cluster_id},
                describe=spec.child_describe,
                items_attr=spec.child_items_attr):
            node["ClusterId"] = cluster_id
            node["ClusterName"] = cluster.get("ClusterName")
            node["ClusterStatus"] = cluster.get("ClusterStatus")
            node["ClusterVersion"] = cluster.get("ClusterVersion")
            node["ClusterNodeNum"] = cluster.get("ClusterNodeNum")
            pool_id = node.get("NodePoolId")
            node["NodePoolName"] = pools.get(pool_id) if pool_id else None
            nodes.append(node)
    return nodes


SOURCE_SPECS = {
    "cvm": SourceSpec(
        name="cvm",
        label="CVM instances",
        sdk_package="tencentcloud-sdk-python-cvm",
        endpoint="cvm.tencentcloudapi.com",
        client_module="tencentcloud.cvm.v20170312.cvm_client",
        client_class="CvmClient",
        models_module="tencentcloud.cvm.v20170312.models",
        request_class="DescribeInstancesRequest",
        describe="DescribeInstances",
        items_attr="InstanceSet",
        total_attr="TotalCount",
        normalizer=normalize_cvm,
    ),
    "tke": SourceSpec(
        name="tke",
        label="TKE cluster nodes",
        sdk_package="tencentcloud-sdk-python-tke",
        endpoint="tke.tencentcloudapi.com",
        client_module="tencentcloud.tke.v20180525.tke_client",
        client_class="TkeClient",
        models_module="tencentcloud.tke.v20180525.models",
        request_class="DescribeClustersRequest",
        describe="DescribeClusters",
        items_attr="Clusters",
        total_attr="TotalCount",
        normalizer=normalize_tke_node,
        child_request_class="DescribeClusterInstancesRequest",
        child_describe="DescribeClusterInstances",
        child_items_attr="InstanceSet",
        collector=collect_tke_nodes,
    ),
    "lighthouse": SourceSpec(
        name="lighthouse",
        label="Lighthouse instances",
        sdk_package="tencentcloud-sdk-python-lighthouse",
        endpoint="lighthouse.tencentcloudapi.com",
        client_module="tencentcloud.lighthouse.v20200324.lighthouse_client",
        client_class="LighthouseClient",
        models_module="tencentcloud.lighthouse.v20200324.models",
        request_class="DescribeInstancesRequest",
        describe="DescribeInstances",
        items_attr="InstanceSet",
        total_attr="TotalCount",
        normalizer=normalize_lighthouse,
    ),
    "vpc": SourceSpec(
        name="vpc",
        label="VPCs",
        sdk_package="tencentcloud-sdk-python-vpc",
        endpoint="vpc.tencentcloudapi.com",
        client_module="tencentcloud.vpc.v20170312.vpc_client",
        client_class="VpcClient",
        models_module="tencentcloud.vpc.v20170312.models",
        request_class="DescribeVpcsRequest",
        describe="DescribeVpcs",
        items_attr="VpcSet",
        total_attr="TotalCount",
        normalizer=normalize_vpc,
        string_paging=True,
    ),
}

SOURCE_NAMES = tuple(SOURCE_SPECS)


# ---------------------------------------------------------------------------
# Entry points used by the inventory plugin
# ---------------------------------------------------------------------------

def resolve_sources(names):
    """Validate and de-duplicate source names, preserving the given order."""
    if not names:
        raise InventorySourceError(
            "Set sources to at least one of: {0}.".format(
                ", ".join(SOURCE_NAMES)))
    specs = []
    seen = set()
    for name in names:
        key = str(name).strip().lower()
        if key not in SOURCE_SPECS:
            raise InventorySourceError(
                "Unknown inventory source '{0}'. Valid sources: {1}.".format(
                    name, ", ".join(SOURCE_NAMES)))
        if key not in seen:
            seen.add(key)
            specs.append(SOURCE_SPECS[key])
    return specs


def load_models(spec):
    """Import the models module of a source, with a package-named error."""
    try:
        return importlib.import_module(spec.models_module)
    except ImportError as exc:
        raise InventorySourceError(
            "The {0} package is required on the Ansible controller to query "
            "the '{1}' source ({2}).".format(
                spec.sdk_package, spec.name, exc))


def build_client(spec, region, secret_id, secret_key, token=None):
    """Build a product client for one region.

    The SDK is imported here rather than at module level so that this module
    stays importable without it.
    """
    try:
        client_module = importlib.import_module(spec.client_module)
        credential_module = importlib.import_module("tencentcloud.common.credential")
        http_profile_module = importlib.import_module(
            "tencentcloud.common.profile.http_profile")
        client_profile_module = importlib.import_module(
            "tencentcloud.common.profile.client_profile")
    except ImportError as exc:
        raise InventorySourceError(
            "The {0} package is required on the Ansible controller to query "
            "the '{1}' source ({2}).".format(
                spec.sdk_package, spec.name, exc))
    http_profile = http_profile_module.HttpProfile()
    http_profile.endpoint = spec.endpoint
    http_profile.reqTimeout = 60
    client_profile = client_profile_module.ClientProfile()
    client_profile.httpProfile = http_profile
    client_profile.language = "en-US"
    credential = credential_module.Credential(secret_id, secret_key, token)
    return getattr(client_module, spec.client_class)(
        credential, region, client_profile)


def resolve_credentials(secret_id=None, secret_key=None, token=None,
                        profile=None):
    """Resolve ``(secret_id, secret_key, token)`` for the inventory plugin.

    Options and their environment variables win; the TCCLI profile is the
    fallback, exactly as in the per-product inventory plugins. It is wrapped
    here because ``client.create_client`` needs an ``AnsibleModule`` and an
    inventory plugin has none.
    """
    if not secret_id or not secret_key:
        data = load_profile(profile)
        secret_id = secret_id or data.get("secret_id")
        secret_key = secret_key or data.get("secret_key")
        token = token or data.get("token")
    if not secret_id or not secret_key:
        raise InventorySourceError(
            "Set secret_id and secret_key, their TENCENTCLOUD_* environment "
            "variables, or the secret_id/secret_key keys of a profile in "
            "~/.tencentcloud/default.configure.")
    return secret_id, secret_key, token


def collect_source(spec, client, filters=None, page_size=PAGE_SIZE):
    """Return the raw items of one source in one region.

    :param spec: the :class:`SourceSpec` to query.
    :param client: an already-constructed product client.
    :param filters: API filters for this source, as ``[{name, values}]``.
    """
    models = load_models(spec)
    collector = spec.collector or collect_flat
    return collector(spec, client, models, filters, page_size)


def describe_entry(spec, region, item):
    """Return one host entry: the raw API fields plus the standardised set.

    ``item`` may be an SDK model or an already-plain mapping; either way the
    result is a plain dict that Ansible can store as host variables.
    """
    raw = serialize(item)
    entry = dict(raw)
    entry["tc_source"] = spec.name
    entry["tc_sources"] = [spec.name]
    entry.update(normalize(spec, region, raw))
    return entry


def normalize(spec, region, item):
    """Return the standardised ``tc_*`` subset of one item."""
    return spec.normalizer(region, item)


def _is_empty(value):
    return value in (None, "", [], {})


def merge_entries(entries):
    """Fold entries sharing a ``tc_id`` into one host, first entry winning.

    Overlap is real, not hypothetical: a TKE worker node is also a CVM
    instance and both products report the same ``i-xxxx``. Merging keeps one
    host per resource, unions ``tc_sources`` and merges list-valued raw
    fields, while leaving fields only one product knows about untouched.
    """
    merged = {}
    order = []
    for entry in entries:
        key = entry.get("tc_id") or (entry.get("tc_source"), entry.get("tc_name"))
        target = merged.get(key)
        if target is None:
            target = dict(entry)
            target["tc_sources"] = list(entry.get("tc_sources") or [])
            merged[key] = target
            order.append(key)
            continue
        for source in entry.get("tc_sources") or []:
            if source not in target["tc_sources"]:
                target["tc_sources"].append(source)
        for name, value in entry.items():
            if name == "tc_sources":
                continue
            current = target.get(name)
            if isinstance(current, list) and isinstance(value, list):
                target[name] = list(dict.fromkeys(current + value))
            elif _is_empty(current) and not _is_empty(value):
                target[name] = value
    return [merged[key] for key in order]


def build_cache_key(plugin_name, path, configuration):
    """Return a cache key covering both the source file and its query config.

    ``Cacheable.get_cache_key`` hashes the plugin name and the path only, so
    editing ``regions`` or ``filters`` keeps serving the cached inventory
    until it expires. Hashing the query configuration as well makes a
    configuration change a cache miss, which is what a user expects.
    """
    payload = json.dumps(
        {"path": path, "configuration": configuration},
        sort_keys=True, default=str,
    )
    digest = hashlib.sha256(payload.encode("utf-8"), usedforsecurity=False)
    return "{0}_{1}".format(plugin_name, digest.hexdigest()[:12])


LITERAL_HOSTNAMES = {
    "private-ip": "tc_private_ip",
    "public-ip": "tc_public_ip",
    "id": "tc_id",
    "name": "tc_name",
}


def hostname_of(hostnames, entry, compose):
    """Return the first usable hostname for one entry.

    The literals ``private-ip`` / ``public-ip`` / ``id`` / ``name`` read the
    standardised fields directly; anything else is a Jinja2 expression
    evaluated against the host entry.
    """
    for source in hostnames or []:
        if source in LITERAL_HOSTNAMES:
            value = entry.get(LITERAL_HOSTNAMES[source])
        else:
            value = compose(source, entry)
        if value:
            return str(value)
    return None


__all__ = [
    "InventorySourceError",
    "LITERAL_HOSTNAMES",
    "PAGE_SIZE",
    "SOURCE_NAMES",
    "SOURCE_SPECS",
    "SourceSpec",
    "build_cache_key",
    "build_client",
    "build_filter",
    "build_request",
    "collect_flat",
    "collect_source",
    "collect_tke_nodes",
    "describe_entry",
    "hostname_of",
    "load_models",
    "merge_entries",
    "normalize",
    "normalize_cvm",
    "normalize_lighthouse",
    "normalize_tke_node",
    "normalize_vpc",
    "resolve_credentials",
    "resolve_sources",
    "serialize",
    "tag_mapping",
]
