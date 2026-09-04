"""Unit tests for the tencentcloud_tke inventory plugin helpers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest

from ansible.errors import AnsibleError

from ansible_collections.susunola.tencentcloud.plugins.inventory import (
    tencentcloud_tke as inv_mod,
)
from ansible_collections.susunola.tencentcloud.plugins.inventory.tencentcloud_tke import (
    InventoryModule,
    build_describe_clusters_request,
    build_describe_instances_request,
    fetch_cluster_instances,
    fetch_clusters,
    fetch_node_pools,
    resolve_hostname,
    serialize_instance,
)


class FakeRequest(object):
    pass


class FakeModels(object):
    DescribeClustersRequest = FakeRequest
    DescribeClusterInstancesRequest = FakeRequest
    DescribeClusterNodePoolsRequest = FakeRequest


class FakeSdkInstance(object):
    def __init__(self, instance_id, lan_ip, role="WORKER", state="Running",
                 node_pool_id=None):
        self.InstanceId = instance_id
        self.LanIP = lan_ip
        self.InstanceRole = role
        self.InstanceState = state
        self.NodePoolId = node_pool_id

    def _serialize(self, allow_none=True):
        return {
            "InstanceId": self.InstanceId,
            "LanIP": self.LanIP,
            "InstanceRole": self.InstanceRole,
            "InstanceState": self.InstanceState,
            "NodePoolId": self.NodePoolId,
        }


class FakeSdkCluster(object):
    def __init__(self, cluster_id, name, status="Running", version="1.28.3"):
        self.ClusterId = cluster_id
        self.ClusterName = name
        self.ClusterStatus = status
        self.ClusterVersion = version

    def _serialize(self, allow_none=True):
        return {
            "ClusterId": self.ClusterId,
            "ClusterName": self.ClusterName,
            "ClusterStatus": self.ClusterStatus,
            "ClusterVersion": self.ClusterVersion,
        }


class FakeSdkPool(object):
    def __init__(self, pool_id, name):
        self.NodePoolId = pool_id
        self.Name = name

    def _serialize(self, allow_none=True):
        return {"NodePoolId": self.NodePoolId, "Name": self.Name}


class FakeClustersResponse(object):
    def __init__(self, clusters, total):
        self.Clusters = clusters
        self.TotalCount = total


class FakeInstancesResponse(object):
    def __init__(self, instances, total):
        self.InstanceSet = instances
        self.TotalCount = total


class FakePoolsResponse(object):
    def __init__(self, pools):
        self.NodePoolSet = pools


class FakeClient(object):
    """In-memory TKE client recording pagination offsets."""

    def __init__(self, clusters, instances=None, pools=None):
        self.clusters = clusters
        self.instances = instances or {}
        self.pools = pools or {}
        self.cluster_offsets = []
        self.instance_offsets = []
        self.node_pool_calls = []

    def DescribeClusters(self, request):
        self.cluster_offsets.append(request.Offset)
        start = request.Offset
        page = self.clusters[start:start + request.Limit]
        return FakeClustersResponse(page, len(self.clusters))

    def DescribeClusterInstances(self, request):
        self.instance_offsets.append((request.ClusterId, request.Offset))
        instances = self.instances.get(request.ClusterId, [])
        start = request.Offset
        page = instances[start:start + request.Limit]
        return FakeInstancesResponse(page, len(instances))

    def DescribeClusterNodePools(self, request):
        self.node_pool_calls.append(request.ClusterId)
        return FakePoolsResponse(self.pools.get(request.ClusterId, []))


def compose_stub(template, variables):
    """Minimal Jinja stand-in resolving a bare variable name."""
    return variables.get(template)


def test_build_describe_clusters_request_without_ids():
    request = build_describe_clusters_request(FakeModels, [], 0, 100)
    assert request.Offset == 0
    assert request.Limit == 100
    assert not hasattr(request, "ClusterIds")


def test_build_describe_clusters_request_with_ids():
    request = build_describe_clusters_request(FakeModels, ["cls-1111"], 50, 100)
    assert request.ClusterIds == ["cls-1111"]
    assert request.Offset == 50


def test_build_describe_instances_request():
    request = build_describe_instances_request(FakeModels, "cls-1111", 0, 100)
    assert request.ClusterId == "cls-1111"
    assert request.Offset == 0
    assert request.Limit == 100


def test_serialize_instance_sdk_object():
    node = FakeSdkInstance("ins-1", "10.0.0.1")
    data = serialize_instance(node)
    assert data["InstanceId"] == "ins-1"
    assert data["LanIP"] == "10.0.0.1"


def test_serialize_instance_plain_dict():
    node = {"InstanceId": "ins-2", "LanIP": "10.0.0.2"}
    assert serialize_instance(node) == node


def test_fetch_clusters_paginates():
    clusters = [FakeSdkCluster("cls-{0}".format(i), "c{0}".format(i)) for i in range(3)]
    client = FakeClient(clusters)
    result = fetch_clusters(client, FakeModels, [], page_size=2)
    assert [c["ClusterId"] for c in result] == ["cls-0", "cls-1", "cls-2"]
    assert client.cluster_offsets == [0, 2]


def test_fetch_clusters_respects_cluster_ids():
    clusters = [FakeSdkCluster("cls-1", "one"), FakeSdkCluster("cls-2", "two")]
    client = FakeClient(clusters)
    # the fake ignores ClusterIds; the request itself carries them
    result = fetch_clusters(client, FakeModels, ["cls-2"], page_size=100)
    assert len(result) == 2
    assert client.cluster_offsets == [0]


def test_fetch_cluster_instances_paginates():
    instances = [FakeSdkInstance("ins-{0}".format(i), "10.0.0.{0}".format(i + 1))
                 for i in range(3)]
    client = FakeClient([], instances={"cls-1": instances})
    result = fetch_cluster_instances(client, FakeModels, "cls-1", page_size=2)
    assert [n["InstanceId"] for n in result] == ["ins-0", "ins-1", "ins-2"]
    assert client.instance_offsets == [("cls-1", 0), ("cls-1", 2)]


def test_fetch_node_pools_maps_id_to_name():
    pools = [FakeSdkPool("np-1", "default-pool"), FakeSdkPool("np-2", "gpu-pool")]
    client = FakeClient([], pools={"cls-1": pools})
    mapping = fetch_node_pools(client, FakeModels, "cls-1")
    assert mapping == {"np-1": "default-pool", "np-2": "gpu-pool"}
    assert client.node_pool_calls == ["cls-1"]


def test_fetch_node_pools_empty():
    client = FakeClient([], pools={"cls-1": []})
    assert fetch_node_pools(client, FakeModels, "cls-1") == {}


def test_resolve_hostname_private_ip_first():
    node = {"LanIP": "10.0.0.1", "InstanceId": "ins-1"}
    hostname = resolve_hostname(["private-ip", "instance-id"], node, compose_stub)
    assert hostname == "10.0.0.1"


def test_resolve_hostname_falls_back_to_instance_id():
    node = {"LanIP": "", "InstanceId": "ins-1"}
    hostname = resolve_hostname(["private-ip", "instance-id"], node, compose_stub)
    assert hostname == "ins-1"


def test_resolve_hostname_jinja_expression():
    node = {"InstanceId": "ins-1", "LanIP": "10.0.0.1"}
    hostname = resolve_hostname(["InstanceId"], node, compose_stub)
    assert hostname == "ins-1"


def test_resolve_hostname_none_without_value():
    node = {"LanIP": "", "InstanceId": ""}
    assert resolve_hostname(["private-ip", "instance-id"], node, compose_stub) is None


class FakeInventory(object):
    def __init__(self):
        self.hosts = []
        self.variables = {}

    def add_host(self, hostname):
        self.hosts.append(hostname)

    def set_variable(self, hostname, key, value):
        self.variables.setdefault(hostname, {})[key] = value


def _plugin(options):
    plugin = InventoryModule()
    plugin.get_option = lambda name: options[name]
    return plugin


def _populate_options(**overrides):
    options = {
        "strict": False,
        "hostnames": ["private-ip", "instance-id"],
        "compose": {},
        "groups": {},
        "keyed_groups": [],
    }
    options.update(overrides)
    return options


def test_populate_adds_node_hosts_and_hostvars():
    plugin = _plugin(_populate_options())
    plugin.inventory = FakeInventory()
    composed, composed_groups, keyed_groups = [], [], []
    plugin._set_composite_vars = lambda *a, **k: composed.append((a, k))
    plugin._add_host_to_composed_groups = lambda *a, **k: composed_groups.append((a, k))
    plugin._add_host_to_keyed_groups = lambda *a, **k: keyed_groups.append((a, k))

    results = {
        "ap-guangzhou": [
            {"InstanceId": "ins-1", "LanIP": "10.0.0.1", "ClusterId": "cls-1",
             "ClusterName": "prod", "NodePoolId": "np-1", "NodePoolName": "default-pool"},
            {"InstanceId": "ins-2", "LanIP": "", "ClusterId": "cls-1",
             "ClusterName": "prod", "NodePoolId": None, "NodePoolName": None},
        ]
    }
    plugin._populate(results)

    assert plugin.inventory.hosts == ["10.0.0.1", "ins-2"]
    hostvars = plugin.inventory.variables["10.0.0.1"]
    assert hostvars["ClusterId"] == "cls-1"
    assert hostvars["ClusterName"] == "prod"
    assert hostvars["NodePoolName"] == "default-pool"
    assert hostvars["region"] == "ap-guangzhou"
    assert len(composed) == 2
    assert len(composed_groups) == 2
    assert len(keyed_groups) == 2


def test_verify_file(tmp_path):
    plugin = InventoryModule()
    good = tmp_path / "inventory.tencentcloud_tke.yml"
    good.write_text("plugin: susunola.tencentcloud.tencentcloud_tke\n")
    bad = tmp_path / "inventory.yml"
    bad.write_text("plugin: something_else\n")
    assert plugin.verify_file(str(good)) is True
    assert plugin.verify_file(str(bad)) is False
    assert plugin.verify_file(str(tmp_path / "missing.tencentcloud_tke.yml")) is False


class FakeHttpProfile(object):
    pass


class FakeClientProfile(object):
    pass


class FakeCredentialModule(object):
    class Credential(object):
        def __init__(self, secret_id, secret_key, token=None):
            self.secret_id = secret_id
            self.secret_key = secret_key
            self.token = token


class FakeTkeClient(object):
    def __init__(self, credential, region, profile=None):
        self.credential = credential
        self.region = region
        self.profile = profile


def _stub_inventory_sdk(monkeypatch):
    monkeypatch.setattr(inv_mod, "tc_credential", FakeCredentialModule, raising=False)
    monkeypatch.setattr(inv_mod, "HttpProfile", FakeHttpProfile, raising=False)
    monkeypatch.setattr(inv_mod, "ClientProfile", FakeClientProfile, raising=False)
    monkeypatch.setattr(
        inv_mod, "tke_client", type("tke_client", (), {"TkeClient": FakeTkeClient}),
        raising=False,
    )


CREATE_CLIENT_OPTIONS = {
    "secret_id": "akid-param",
    "secret_key": "secret-param",
    "token": None,
    "profile": None,
}


def test_create_client_uses_explicit_credentials(monkeypatch):
    _stub_inventory_sdk(monkeypatch)

    def explode(*args, **kwargs):
        raise AssertionError("profile file must not be read")

    monkeypatch.setattr(inv_mod, "load_profile", explode)
    plugin = InventoryModule()
    plugin.get_option = CREATE_CLIENT_OPTIONS.get
    tke = plugin._create_client("ap-guangzhou")
    assert tke.credential.secret_id == "akid-param"
    assert tke.credential.secret_key == "secret-param"
    assert tke.region == "ap-guangzhou"


def test_create_client_falls_back_to_profile(monkeypatch):
    _stub_inventory_sdk(monkeypatch)
    monkeypatch.setattr(
        inv_mod, "load_profile",
        lambda profile=None: {"secret_id": "akid-prod", "secret_key": "secret-prod"},
    )
    options = dict(CREATE_CLIENT_OPTIONS, secret_id=None, secret_key=None, profile="prod")
    plugin = InventoryModule()
    plugin.get_option = options.get
    tke = plugin._create_client("ap-guangzhou")
    assert tke.credential.secret_id == "akid-prod"
    assert tke.credential.secret_key == "secret-prod"


def test_create_client_missing_everywhere_mentions_profile(monkeypatch):
    _stub_inventory_sdk(monkeypatch)
    monkeypatch.setattr(inv_mod, "load_profile", lambda profile=None: {})
    options = dict(CREATE_CLIENT_OPTIONS, secret_id=None, secret_key=None)
    plugin = InventoryModule()
    plugin.get_option = options.get
    with pytest.raises(AnsibleError, match="default.configure"):
        plugin._create_client("ap-guangzhou")


def test_fetch_region_filters_by_role_and_attaches_cluster_vars(monkeypatch):
    clusters = [FakeSdkCluster("cls-1", "prod")]
    instances = [
        FakeSdkInstance("ins-1", "10.0.0.1", role="WORKER", node_pool_id="np-1"),
        FakeSdkInstance("ins-2", "10.0.0.2", role="MASTER"),
        FakeSdkInstance("ins-3", "10.0.0.3", role="WORKER", node_pool_id="np-2"),
    ]
    pools = [FakeSdkPool("np-1", "default-pool"), FakeSdkPool("np-2", "gpu-pool")]
    client = FakeClient(clusters, instances={"cls-1": instances}, pools={"cls-1": pools})
    monkeypatch.setattr(
        inv_mod, "fetch_clusters",
        lambda client, models, cluster_ids, page_size=100:
            [serialize_instance(c) for c in clusters],
    )
    monkeypatch.setattr(
        inv_mod, "fetch_cluster_instances",
        lambda client, models, cluster_id, page_size=100:
            [serialize_instance(i) for i in instances],
    )
    monkeypatch.setattr(
        inv_mod, "fetch_node_pools",
        lambda client, models, cluster_id: {"np-1": "default-pool", "np-2": "gpu-pool"},
    )
    plugin = InventoryModule()
    plugin.get_option = {"instance_roles": ["WORKER"]}.get
    plugin._create_client = lambda region: client

    nodes = plugin._fetch_region("ap-guangzhou")
    assert [n["InstanceId"] for n in nodes] == ["ins-1", "ins-3"]
    assert nodes[0]["ClusterName"] == "prod"
    assert nodes[0]["NodePoolName"] == "default-pool"
    assert nodes[1]["NodePoolName"] == "gpu-pool"
