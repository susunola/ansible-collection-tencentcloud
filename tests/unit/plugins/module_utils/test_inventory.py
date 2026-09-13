"""Unit tests for the shared multi-product inventory layer."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import inventory


class FakeFilter(object):
    def __init__(self):
        self.Name = None
        self.Values = None


class FakeRequest(object):
    pass


class FakeModels(object):
    """Stand-in for a product's ``models`` module."""

    Filter = FakeFilter
    DescribeInstancesRequest = FakeRequest
    DescribeVpcsRequest = FakeRequest
    DescribeClustersRequest = FakeRequest
    DescribeClusterInstancesRequest = FakeRequest
    DescribeClusterNodePoolsRequest = FakeRequest


class FakeItem(object):
    """Stand-in for an SDK model item."""

    def __init__(self, **fields):
        for name, value in fields.items():
            setattr(self, name, value)

    def _serialize(self, allow_none=False):
        return {name: value for name, value in vars(self).items()}


class FakeResponse(object):
    def __init__(self, **fields):
        for name, value in fields.items():
            setattr(self, name, value)


# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

def test_source_names_are_the_documented_first_batch():
    assert inventory.SOURCE_NAMES == ("cvm", "tke", "lighthouse", "vpc")


def test_every_spec_is_self_consistent():
    for name, spec in inventory.SOURCE_SPECS.items():
        assert spec.name == name
        assert spec.label
        assert spec.sdk_package.startswith("tencentcloud-sdk-python")
        assert spec.endpoint.endswith(".tencentcloudapi.com")
        assert spec.client_module.endswith(".models") is False
        assert spec.client_module.rsplit(".", 1)[-1].endswith("_client")
        assert spec.models_module.endswith(".models")
        assert spec.request_class.endswith("Request")
        assert spec.describe.startswith("Describe")
        assert spec.items_attr
        assert spec.total_attr == "TotalCount"
        assert callable(spec.normalizer)


def test_spec_client_modules_exist_in_the_documented_sdk_packages():
    """The registry must point at real SDK modules, not plausible-looking ones."""
    assert inventory.SOURCE_SPECS["cvm"].client_module == "tencentcloud.cvm.v20170312.cvm_client"
    assert inventory.SOURCE_SPECS["tke"].models_module == "tencentcloud.tke.v20180525.models"
    assert inventory.SOURCE_SPECS["lighthouse"].models_module == "tencentcloud.lighthouse.v20200324.models"
    assert inventory.SOURCE_SPECS["vpc"].request_class == "DescribeVpcsRequest"
    assert inventory.SOURCE_SPECS["vpc"].items_attr == "VpcSet"
    assert inventory.SOURCE_SPECS["tke"].items_attr == "Clusters"


def test_only_the_nested_source_declares_a_child_request():
    tke = inventory.SOURCE_SPECS["tke"]
    assert tke.child_request_class == "DescribeClusterInstancesRequest"
    assert tke.child_describe == "DescribeClusterInstances"
    assert tke.child_items_attr == "InstanceSet"
    assert tke.collector is inventory.collect_tke_nodes
    for name in ("cvm", "lighthouse", "vpc"):
        assert inventory.SOURCE_SPECS[name].child_request_class is None
        assert inventory.SOURCE_SPECS[name].child_describe is None
        assert inventory.SOURCE_SPECS[name].child_items_attr is None
        assert inventory.SOURCE_SPECS[name].collector is None


def test_resolve_sources_keeps_order_and_deduplicates():
    specs = inventory.resolve_sources(["vpc", "CVM", "cvm"])
    assert [spec.name for spec in specs] == ["vpc", "cvm"]


def test_resolve_sources_rejects_unknown_names():
    with pytest.raises(inventory.InventorySourceError, match="Unknown inventory source 'ec2'"):
        inventory.resolve_sources(["ec2"])
    with pytest.raises(inventory.InventorySourceError, match="cvm, tke, lighthouse, vpc"):
        inventory.resolve_sources(["ec2"])


def test_resolve_sources_rejects_an_empty_list():
    with pytest.raises(inventory.InventorySourceError, match="at least one"):
        inventory.resolve_sources([])
    with pytest.raises(inventory.InventorySourceError, match="at least one"):
        inventory.resolve_sources(None)


# ---------------------------------------------------------------------------
# Serialisation and tags
# ---------------------------------------------------------------------------

def test_serialize_accepts_sdk_models_and_plain_mappings():
    assert inventory.serialize(FakeItem(InstanceId="ins-1")) == {"InstanceId": "ins-1"}
    assert inventory.serialize({"InstanceId": "ins-1"}) == {"InstanceId": "ins-1"}


def test_tag_mapping_normalises_every_api_shape():
    expected = {"env": "prod"}
    assert inventory.tag_mapping([{"Key": "env", "Value": "prod"}]) == expected
    assert inventory.tag_mapping({"env": "prod"}) == expected
    assert inventory.tag_mapping([FakeItem(Key="env", Value="prod")]) == expected
    assert inventory.tag_mapping(None) == {}
    assert inventory.tag_mapping([]) == {}


def test_tag_mapping_skips_entries_without_a_key():
    assert inventory.tag_mapping([{"Value": "prod"}, {"Key": "", "Value": "x"}]) == {}


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

CVM_INSTANCE = {
    "InstanceId": "ins-1",
    "InstanceName": "web-1",
    "InstanceState": "RUNNING",
    "PrivateIpAddresses": ["10.0.0.4", "10.0.0.5"],
    "PublicIpAddresses": ["1.2.3.4"],
    "Placement": {"Zone": "ap-singapore-1"},
    "Tags": [{"Key": "env", "Value": "prod"}],
}

LIGHTHOUSE_INSTANCE = {
    "InstanceId": "lhins-1",
    "InstanceName": "blog",
    "InstanceState": "RUNNING",
    "PrivateAddresses": ["10.1.0.2"],
    "PublicAddresses": ["5.6.7.8"],
    "Zone": "ap-singapore-2",
    "Tags": [{"Key": "env", "Value": "prod"}],
}

TKE_NODE = {
    "InstanceId": "ins-9",
    "LanIP": "10.2.0.9",
    "InstanceRole": "Worker",
    "InstanceState": "running",
    "NodePoolId": "np-1",
    "ClusterId": "cls-1",
    "ClusterName": "prod",
}

VPC = {
    "VpcId": "vpc-1",
    "VpcName": "prod-vpc",
    "CidrBlock": "10.0.0.0/16",
    "IsDefault": False,
    "TagSet": [{"Key": "team", "Value": "cpt"}],
}


def test_normalize_cvm_reads_addresses_zone_and_tags():
    entry = inventory.normalize_cvm("ap-singapore", CVM_INSTANCE)
    assert "tc_source" not in entry
    assert entry["tc_id"] == "ins-1"
    assert entry["tc_name"] == "web-1"
    assert entry["tc_state"] == "RUNNING"
    assert entry["tc_private_ip"] == "10.0.0.4"
    assert entry["tc_public_ip"] == "1.2.3.4"
    assert entry["tc_zone"] == "ap-singapore-1"
    assert entry["tc_tags"] == {"env": "prod"}
    assert entry["tc_region"] == "ap-singapore"


def test_normalize_lighthouse_reads_its_own_address_fields():
    entry = inventory.normalize_lighthouse("ap-singapore", LIGHTHOUSE_INSTANCE)
    assert entry["tc_id"] == "lhins-1"
    assert entry["tc_private_ip"] == "10.1.0.2"
    assert entry["tc_public_ip"] == "5.6.7.8"
    assert entry["tc_zone"] == "ap-singapore-2"


def test_normalize_tke_node_maps_lanip_and_cluster_membership():
    entry = inventory.normalize_tke_node("ap-singapore", TKE_NODE)
    assert entry["tc_id"] == "ins-9"
    assert entry["tc_private_ip"] == "10.2.0.9"
    assert entry["tc_public_ip"] is None
    assert entry["tc_role"] == "Worker"
    assert entry["tc_parent_id"] == "cls-1"
    assert entry["tc_parent_name"] == "prod"


def test_normalize_vpc_has_no_address_and_flags_the_default_vpc():
    entry = inventory.normalize_vpc("ap-singapore", VPC)
    assert entry["tc_id"] == "vpc-1"
    assert entry["tc_name"] == "prod-vpc"
    assert entry["tc_private_ip"] is None
    assert entry["tc_state"] is None
    default = dict(VPC, IsDefault=True)
    assert inventory.normalize_vpc("ap-singapore", default)["tc_state"] == "DEFAULT"


def test_every_normaliser_returns_the_same_key_set():
    keys = set(inventory.normalize_cvm("r", CVM_INSTANCE))
    assert keys == set(inventory.normalize_lighthouse("r", LIGHTHOUSE_INSTANCE))
    assert keys == set(inventory.normalize_tke_node("r", TKE_NODE))
    assert keys == set(inventory.normalize_vpc("r", VPC))
    assert "tc_id" in keys and "tc_parent_name" in keys


def test_normalisers_tolerate_missing_fields():
    """A half-populated API response must not raise."""
    for normalize in (inventory.normalize_cvm, inventory.normalize_lighthouse,
                      inventory.normalize_tke_node, inventory.normalize_vpc):
        entry = normalize("r", {})
        assert entry["tc_id"] is None
        assert entry["tc_tags"] == {}


def test_normalize_uses_the_spec_normaliser():
    entry = inventory.normalize(inventory.SOURCE_SPECS["vpc"], "r", VPC)
    assert entry["tc_id"] == "vpc-1"


def test_describe_entry_keeps_raw_fields_and_adds_the_standard_set():
    entry = inventory.describe_entry(inventory.SOURCE_SPECS["cvm"], "ap-singapore", CVM_INSTANCE)
    assert entry["InstanceName"] == "web-1"
    assert entry["tc_name"] == "web-1"
    assert entry["tc_source"] == "cvm"
    assert entry["tc_sources"] == ["cvm"]


def test_describe_entry_accepts_sdk_models():
    item = FakeItem(InstanceId="ins-1", InstanceName="web-1")
    entry = inventory.describe_entry(inventory.SOURCE_SPECS["cvm"], "r", item)
    assert entry["InstanceName"] == "web-1"
    assert entry["tc_id"] == "ins-1"


# ---------------------------------------------------------------------------
# Merging
# ---------------------------------------------------------------------------

def _entry(source, **fields):
    return inventory.describe_entry(inventory.SOURCE_SPECS[source], "r", fields)


def test_merge_entries_folds_a_tke_node_into_its_cvm_instance():
    cvm = _entry("cvm", InstanceId="ins-1", InstanceName="web-1", PrivateIpAddresses=["10.0.0.4"])
    node = _entry("tke", InstanceId="ins-1", LanIP="10.0.0.4", InstanceRole="Worker",
                  ClusterId="cls-1", ClusterName="prod")
    merged = inventory.merge_entries([cvm, node])
    assert len(merged) == 1
    assert merged[0]["tc_sources"] == ["cvm", "tke"]
    assert merged[0]["tc_name"] == "web-1"
    assert merged[0]["tc_role"] == "Worker"
    assert merged[0]["tc_parent_name"] == "prod"


def test_merge_entries_keeps_the_first_value_for_scalars():
    first = _entry("cvm", InstanceId="ins-1", InstanceName="from-cvm", InstanceState="RUNNING")
    second = _entry("tke", InstanceId="ins-1", InstanceName="from-tke", InstanceState="running")
    merged = inventory.merge_entries([first, second])
    assert merged[0]["tc_name"] == "from-cvm"
    assert merged[0]["tc_state"] == "RUNNING"


def test_merge_entries_keeps_entries_that_have_no_id_apart():
    a = _entry("vpc", VpcId=None, VpcName="shared-name")
    b = _entry("lighthouse", InstanceId=None, InstanceName="shared-name")
    assert len(inventory.merge_entries([a, b])) == 2


def test_merge_entries_preserves_discovery_order():
    entries = [
        _entry("cvm", InstanceId="ins-1"),
        _entry("vpc", VpcId="vpc-1"),
        _entry("tke", InstanceId="ins-1"),
    ]
    merged = inventory.merge_entries(entries)
    assert [entry["tc_id"] for entry in merged] == ["ins-1", "vpc-1"]


def test_merge_entries_unions_list_fields_and_does_not_clobber_with_empties():
    a = _entry("cvm", InstanceId="ins-1", InstanceName="web-1", PublicIpAddresses=["1.1.1.1"])
    b = _entry("tke", InstanceId="ins-1", InstanceName=None, PublicIpAddresses=["2.2.2.2"])
    merged = inventory.merge_entries([a, b])[0]
    assert merged["tc_name"] == "web-1"
    assert merged["PublicIpAddresses"] == ["1.1.1.1", "2.2.2.2"]


# ---------------------------------------------------------------------------
# Cache key and hostnames
# ---------------------------------------------------------------------------

def test_build_cache_key_is_stable_across_mapping_order():
    one = inventory.build_cache_key("tc_inventory", "/i.yml", {"regions": ["a"], "sources": ["cvm"]})
    two = inventory.build_cache_key("tc_inventory", "/i.yml", {"sources": ["cvm"], "regions": ["a"]})
    assert one == two


def test_build_cache_key_covers_the_query_configuration_and_path():
    base = inventory.build_cache_key("tc_inventory", "/i.yml", {"regions": ["a"]})
    assert base != inventory.build_cache_key("tc_inventory", "/i.yml", {"regions": ["b"]})
    assert base != inventory.build_cache_key("tc_inventory", "/j.yml", {"regions": ["a"]})
    assert base.startswith("tc_inventory_")


def test_hostname_of_prefers_the_first_source_that_yields_a_value():
    entry = {"tc_private_ip": None, "tc_public_ip": "1.2.3.4", "tc_name": "web-1", "tc_id": "ins-1"}
    assert inventory.hostname_of(["private-ip", "public-ip", "name"], entry, lambda t, v: None) == "1.2.3.4"
    assert inventory.hostname_of(["id"], entry, lambda t, v: None) == "ins-1"
    assert inventory.hostname_of(["name"], entry, lambda t, v: None) == "web-1"


def test_hostname_of_falls_back_to_jinja_and_returns_none():
    entry = {"tc_name": "web-1", "InstanceId": "ins-1"}
    assert inventory.hostname_of(["InstanceId"], entry, lambda t, v: v.get(t)) == "ins-1"
    assert inventory.hostname_of(["private-ip"], entry, lambda t, v: None) is None
    assert inventory.hostname_of([], entry, lambda t, v: None) is None
    assert inventory.hostname_of(None, entry, lambda t, v: None) is None


# ---------------------------------------------------------------------------
# Filters and collectors
# ---------------------------------------------------------------------------

def test_build_filter_accepts_a_list_or_a_scalar():
    entry = inventory.build_filter(FakeModels, {"name": "instance-state", "values": ["RUNNING"]})
    assert entry.Name == "instance-state"
    assert entry.Values == ["RUNNING"]
    scalar = inventory.build_filter(FakeModels, {"name": "zone", "values": "ap-singapore-1"})
    assert scalar.Values == ["ap-singapore-1"]


def test_build_filter_tolerates_missing_values():
    entry = inventory.build_filter(FakeModels, {"name": "zone"})
    assert entry.Values == []


class FakePagedClient(object):
    """Records the requests made against it and pages like the real API."""

    def __init__(self, items, page_total=None):
        self.items = items
        self.page_total = page_total
        self.offsets = []
        self.requests = []

    def _respond(self, request, items):
        # VPC serialises Offset/Limit as strings; every other first-batch
        # product uses integers. The raw values are recorded for assertions,
        # the coerced ones drive the fake paging.
        self.offsets.append(request.Offset)
        self.requests.append(request)
        offset, limit = int(request.Offset), int(request.Limit)
        page = items[offset:offset + limit]
        return FakeResponse(InstanceSet=page, VpcSet=page, TotalCount=len(items))


class FakeFlatClient(FakePagedClient):
    def DescribeInstances(self, request):
        return self._respond(request, self.items)

    def DescribeVpcs(self, request):
        return self._respond(request, self.items)


def test_collect_flat_walks_every_page_and_applies_filters():
    items = [FakeItem(InstanceId="ins-{0}".format(i)) for i in range(5)]
    client = FakeFlatClient(items)
    spec = inventory.SOURCE_SPECS["cvm"]
    filters = [{"name": "instance-state", "values": ["RUNNING"]}]
    collected = inventory.collect_flat(spec, client, FakeModels, filters, page_size=2)
    assert [item["InstanceId"] for item in collected] == ["ins-0", "ins-1", "ins-2", "ins-3", "ins-4"]
    assert client.offsets == [0, 2, 4]
    assert client.requests[0].Filters[0].Name == "instance-state"
    assert client.requests[0].Limit == 2


def test_collect_flat_omits_filters_when_none_are_configured():
    client = FakeFlatClient([FakeItem(InstanceId="ins-1")])
    inventory.collect_flat(inventory.SOURCE_SPECS["cvm"], client, FakeModels, None)
    assert not hasattr(client.requests[0], "Filters")


def test_paging_serialisation_follows_the_product_contract():
    """Offset/Limit are not typed consistently across the first batch.

    Verified against the live API: CVM, TKE and Lighthouse answer
    ``InvalidParameter`` (``Offset`` must be ``int64``) for a string, while
    VPC answers ``InvalidParameter`` (must be ``string``) for an integer.
    The registry therefore carries the distinction per source.
    """
    assert inventory.SOURCE_SPECS["cvm"].string_paging is False
    assert inventory.SOURCE_SPECS["tke"].string_paging is False
    assert inventory.SOURCE_SPECS["lighthouse"].string_paging is False
    assert inventory.SOURCE_SPECS["vpc"].string_paging is True

    cvm = FakeFlatClient([FakeItem(InstanceId="ins-1")])
    inventory.collect_flat(inventory.SOURCE_SPECS["cvm"], cvm, FakeModels, None, page_size=20)
    assert cvm.requests[0].Offset == 0
    assert isinstance(cvm.requests[0].Offset, int)
    assert cvm.requests[0].Limit == 20

    vpc = FakeFlatClient([FakeItem(VpcId="vpc-1")])
    inventory.collect_flat(inventory.SOURCE_SPECS["vpc"], vpc, FakeModels, None, page_size=20)
    assert vpc.requests[0].Offset == "0"
    assert vpc.requests[0].Limit == "20"


def test_collect_flat_uses_the_spec_response_attributes():
    client = FakeFlatClient([FakeItem(VpcId="vpc-1")])
    collected = inventory.collect_flat(inventory.SOURCE_SPECS["vpc"], client, FakeModels, None)
    assert collected == [{"VpcId": "vpc-1"}]


class FakeTkeClient(object):
    def __init__(self, clusters, nodes, pools):
        self.clusters = clusters
        self.nodes = nodes
        self.pools = pools
        self.cluster_calls = []
        self.node_offsets = []
        self.pool_calls = []

    def DescribeClusters(self, request):
        self.cluster_calls.append(request.Offset)
        page = self.clusters[request.Offset:request.Offset + request.Limit]
        return FakeResponse(Clusters=page, TotalCount=len(self.clusters))

    def DescribeClusterInstances(self, request):
        self.node_offsets.append((request.ClusterId, request.Offset))
        nodes = self.nodes.get(request.ClusterId, [])
        page = nodes[request.Offset:request.Offset + request.Limit]
        return FakeResponse(InstanceSet=page, TotalCount=len(nodes))

    def DescribeClusterNodePools(self, request):
        self.pool_calls.append(request.ClusterId)
        return FakeResponse(NodePoolSet=self.pools.get(request.ClusterId, []))


def test_collect_tke_nodes_attaches_cluster_and_pool_metadata():
    clusters = [FakeItem(ClusterId="cls-1", ClusterName="prod", ClusterStatus="Running",
                         ClusterVersion="1.28.3", ClusterNodeNum=2)]
    nodes = {"cls-1": [FakeItem(InstanceId="ins-1", LanIP="10.0.0.1", NodePoolId="np-1"),
                       FakeItem(InstanceId="ins-2", LanIP="10.0.0.2", NodePoolId=None)]}
    pools = {"cls-1": [FakeItem(NodePoolId="np-1", Name="default-pool")]}
    client = FakeTkeClient(clusters, nodes, pools)
    collected = inventory.collect_tke_nodes(
        inventory.SOURCE_SPECS["tke"], client, FakeModels, None, page_size=10)
    assert [node["InstanceId"] for node in collected] == ["ins-1", "ins-2"]
    assert collected[0]["ClusterName"] == "prod"
    assert collected[0]["ClusterVersion"] == "1.28.3"
    assert collected[0]["ClusterNodeNum"] == 2
    assert collected[0]["NodePoolName"] == "default-pool"
    assert collected[1]["NodePoolName"] is None
    assert client.cluster_calls == [0]
    assert client.node_offsets == [("cls-1", 0)]
    assert client.pool_calls == ["cls-1"]


def test_collect_tke_nodes_pages_nodes_per_cluster_and_skips_id_less_clusters():
    clusters = [FakeItem(ClusterId="cls-1"), FakeItem(ClusterName="no-id")]
    nodes = {"cls-1": [FakeItem(InstanceId="ins-{0}".format(i)) for i in range(3)]}
    client = FakeTkeClient(clusters, nodes, {})
    collected = inventory.collect_tke_nodes(
        inventory.SOURCE_SPECS["tke"], client, FakeModels, None, page_size=2)
    assert [node["InstanceId"] for node in collected] == ["ins-0", "ins-1", "ins-2"]
    assert client.node_offsets == [("cls-1", 0), ("cls-1", 2)]


def test_collect_source_dispatches_to_the_registered_collector(monkeypatch):
    calls = []
    monkeypatch.setattr(inventory, "load_models", lambda spec: FakeModels)
    monkeypatch.setitem(
        inventory.SOURCE_SPECS["tke"].__dict__, "collector",
        lambda spec, client, models, filters, page_size=100: calls.append(spec.name) or [],
    )
    assert inventory.collect_source(inventory.SOURCE_SPECS["tke"], object()) == []
    assert calls == ["tke"]


def test_collect_source_uses_the_flat_collector_for_flat_products(monkeypatch):
    monkeypatch.setattr(inventory, "load_models", lambda spec: FakeModels)
    client = FakeFlatClient([FakeItem(VpcId="vpc-1")])
    collected = inventory.collect_source(inventory.SOURCE_SPECS["vpc"], client)
    assert collected == [{"VpcId": "vpc-1"}]


# ---------------------------------------------------------------------------
# SDK access
# ---------------------------------------------------------------------------

class FakeImportlib(object):
    """Stand-in for the ``importlib`` module, so no real import happens.

    Only the name ``importlib`` inside the inventory module is replaced, so
    the rest of the interpreter keeps its real import machinery.
    """

    def __init__(self, modules):
        self.modules = modules

    def import_module(self, name):
        try:
            return self.modules[name]
        except KeyError:
            raise ImportError("No module named {0!r}".format(name))


def test_load_models_names_the_missing_package(monkeypatch):
    monkeypatch.setattr(inventory, "importlib", FakeImportlib({}))
    with pytest.raises(inventory.InventorySourceError, match="tencentcloud-sdk-python-lighthouse"):
        inventory.load_models(inventory.SOURCE_SPECS["lighthouse"])


def test_build_client_names_the_missing_package(monkeypatch):
    monkeypatch.setattr(inventory, "importlib", FakeImportlib({}))
    with pytest.raises(inventory.InventorySourceError, match="tencentcloud-sdk-python-vpc"):
        inventory.build_client(inventory.SOURCE_SPECS["vpc"], "ap-singapore", "id", "key")


class FakeCredential(object):
    def __init__(self, secret_id, secret_key, token=None):
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.token = token


class FakeHttpProfile(object):
    endpoint = None
    reqTimeout = None


class FakeClientProfile(object):
    httpProfile = None
    language = None


class FakeProductClient(object):
    def __init__(self, credential, region, profile):
        self.credential = credential
        self.region = region
        self.profile = profile


def _fake_sdk(monkeypatch):
    """Install the four SDK modules build_client imports at call time."""
    modules = {
        "tencentcloud.cvm.v20170312.cvm_client": type(
            "cvm_client", (), {"CvmClient": FakeProductClient}),
        "tencentcloud.common.credential": type(
            "credential", (), {"Credential": FakeCredential}),
        "tencentcloud.common.profile.http_profile": type(
            "http_profile", (), {"HttpProfile": FakeHttpProfile}),
        "tencentcloud.common.profile.client_profile": type(
            "client_profile", (), {"ClientProfile": FakeClientProfile}),
    }
    monkeypatch.setattr(inventory, "importlib", FakeImportlib(modules))


def test_build_client_constructs_the_product_client(monkeypatch):
    _fake_sdk(monkeypatch)
    client = inventory.build_client(
        inventory.SOURCE_SPECS["cvm"], "ap-singapore", "akid", "secret", "tok")
    assert isinstance(client, FakeProductClient)
    assert client.credential.secret_id == "akid"
    assert client.credential.token == "tok"
    assert client.region == "ap-singapore"
    assert client.profile.httpProfile.endpoint == "cvm.tencentcloudapi.com"
    assert client.profile.httpProfile.reqTimeout == 60
    assert client.profile.language == "en-US"


def test_resolve_credentials_prefers_explicit_options(monkeypatch):
    def explode(profile=None):
        raise AssertionError("the profile must not be read when options are set")

    monkeypatch.setattr(inventory, "load_profile", explode)
    assert inventory.resolve_credentials("akid", "secret", "tok", None) == ("akid", "secret", "tok")


def test_resolve_credentials_falls_back_to_the_profile(monkeypatch):
    monkeypatch.setattr(
        inventory, "load_profile",
        lambda profile=None: {"secret_id": "akid-prod", "secret_key": "secret-prod"},
    )
    assert inventory.resolve_credentials(None, None, None, "prod") == (
        "akid-prod", "secret-prod", None)


def test_resolve_credentials_raises_a_helpful_error(monkeypatch):
    monkeypatch.setattr(inventory, "load_profile", lambda profile=None: {})
    with pytest.raises(inventory.InventorySourceError, match="default.configure"):
        inventory.resolve_credentials(None, None, None, None)
