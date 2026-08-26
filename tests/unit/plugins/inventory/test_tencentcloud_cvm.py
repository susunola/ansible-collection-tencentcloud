"""Unit tests for the tencentcloud_cvm inventory plugin helpers."""

from ansible_collections.tencentcloud.cloud.plugins.inventory.tencentcloud_cvm import (
    InventoryModule,
    build_describe_request,
    fetch_instances,
    resolve_hostname,
    serialize_instance,
)


class FakeFilter(object):
    pass


class FakeRequest(object):
    pass


class FakeModels(object):
    Filter = FakeFilter
    DescribeInstancesRequest = FakeRequest


class FakeSdkInstance(object):
    def __init__(self, instance_id, private_ips=None, public_ips=None):
        self.InstanceId = instance_id
        self.PrivateIpAddresses = private_ips or []
        self.PublicIpAddresses = public_ips or []

    def _serialize(self, allow_none=True):
        return {
            "InstanceId": self.InstanceId,
            "PrivateIpAddresses": self.PrivateIpAddresses,
            "PublicIpAddresses": self.PublicIpAddresses,
        }


class FakeResponse(object):
    def __init__(self, instances, total):
        self.InstanceSet = instances
        self.TotalCount = total


class FakeClient(object):
    def __init__(self, pages, total):
        self.pages = pages
        self.total = total
        self.offsets = []

    def DescribeInstances(self, request):
        self.offsets.append(request.Offset)
        idx = self.offsets.index(request.Offset)
        return FakeResponse(self.pages[idx], self.total)


def compose_stub(template, variables):
    """Minimal Jinja stand-in resolving a bare variable name."""
    return variables.get(template)


def test_build_describe_request_without_filters():
    request = build_describe_request(FakeModels, [], 0, 100)
    assert request.Offset == 0
    assert request.Limit == 100
    assert not hasattr(request, "Filters")


def test_build_describe_request_with_filters():
    filters = [
        {"name": "instance-state", "values": ["RUNNING"]},
        {"name": "zone", "values": "ap-guangzhou-1"},
    ]
    request = build_describe_request(FakeModels, filters, 0, 100)
    assert len(request.Filters) == 2
    assert request.Filters[0].Name == "instance-state"
    assert request.Filters[0].Values == ["RUNNING"]
    # scalar values are normalised to a list
    assert request.Filters[1].Values == ["ap-guangzhou-1"]


def test_serialize_instance_sdk_object():
    instance = FakeSdkInstance("ins-1", ["10.0.0.1"])
    assert serialize_instance(instance)["InstanceId"] == "ins-1"


def test_serialize_instance_plain_dict():
    instance = {"InstanceId": "ins-2", "PrivateIpAddresses": ["10.0.0.2"]}
    assert serialize_instance(instance) == instance


def test_fetch_instances_paginates():
    pages = [
        [FakeSdkInstance("ins-1", ["10.0.0.1"]), FakeSdkInstance("ins-2", ["10.0.0.2"])],
        [FakeSdkInstance("ins-3", ["10.0.0.3"])],
    ]
    client = FakeClient(pages, total=3)
    instances = fetch_instances(client, FakeModels, [], page_size=2)
    assert [i["InstanceId"] for i in instances] == ["ins-1", "ins-2", "ins-3"]
    assert client.offsets == [0, 2]


def test_fetch_instances_empty():
    client = FakeClient([[]], total=0)
    assert fetch_instances(client, FakeModels, []) == []


def test_resolve_hostname_private_ip_first():
    instance = {"PrivateIpAddresses": ["10.0.0.1"], "PublicIpAddresses": ["1.2.3.4"]}
    hostname = resolve_hostname(["private-ip", "public-ip"], instance, compose_stub)
    assert hostname == "10.0.0.1"


def test_resolve_hostname_falls_back_to_public_ip():
    instance = {"PrivateIpAddresses": [], "PublicIpAddresses": ["1.2.3.4"]}
    hostname = resolve_hostname(["private-ip", "public-ip"], instance, compose_stub)
    assert hostname == "1.2.3.4"


def test_resolve_hostname_jinja_expression():
    instance = {"InstanceName": "web-01", "PrivateIpAddresses": ["10.0.0.1"]}
    hostname = resolve_hostname(["InstanceName", "private-ip"], instance, compose_stub)
    assert hostname == "web-01"


def test_resolve_hostname_none_without_addresses():
    instance = {"PrivateIpAddresses": [], "PublicIpAddresses": []}
    assert resolve_hostname(["private-ip", "public-ip"], instance, compose_stub) is None


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
        "hostnames": ["private-ip", "public-ip"],
        "compose": {},
        "groups": {},
        "keyed_groups": [],
    }
    options.update(overrides)
    return options


def test_populate_adds_hosts_and_hostvars():
    plugin = _plugin(_populate_options())
    plugin.inventory = FakeInventory()
    plugin._compose = compose_stub
    composed, composed_groups, keyed_groups = [], [], []
    plugin._set_composite_vars = lambda *a, **k: composed.append((a, k))
    plugin._add_host_to_composed_groups = lambda *a, **k: composed_groups.append((a, k))
    plugin._add_host_to_keyed_groups = lambda *a, **k: keyed_groups.append((a, k))

    results = {
        "ap-guangzhou": [
            {"InstanceId": "ins-1", "PrivateIpAddresses": ["10.0.0.1"], "PublicIpAddresses": []},
            {"InstanceId": "ins-2", "PrivateIpAddresses": [], "PublicIpAddresses": ["1.2.3.4"]},
            {"InstanceId": "ins-3", "PrivateIpAddresses": [], "PublicIpAddresses": []},
        ]
    }
    plugin._populate(results)

    # ins-3 has no usable address and is skipped
    assert plugin.inventory.hosts == ["10.0.0.1", "1.2.3.4"]
    hostvars = plugin.inventory.variables["10.0.0.1"]
    assert hostvars["InstanceId"] == "ins-1"
    assert hostvars["region"] == "ap-guangzhou"
    # Constructable hooks ran for every added host
    assert len(composed) == 2
    assert len(composed_groups) == 2
    assert len(keyed_groups) == 2


def test_populate_strict_is_forwarded():
    plugin = _plugin(_populate_options(strict=True))
    plugin.inventory = FakeInventory()
    plugin._compose = compose_stub
    seen = {}
    plugin._set_composite_vars = lambda c, v, h, strict=False: seen.setdefault("strict", strict)
    plugin._add_host_to_composed_groups = lambda *a, **k: None
    plugin._add_host_to_keyed_groups = lambda *a, **k: None

    results = {"ap-guangzhou": [{"InstanceId": "ins-1", "PrivateIpAddresses": ["10.0.0.1"]}]}
    plugin._populate(results)
    assert seen["strict"] is True


def test_verify_file(tmp_path):
    plugin = InventoryModule()
    good = tmp_path / "inventory.tencentcloud_cvm.yml"
    good.write_text("plugin: tencentcloud.cloud.tencentcloud_cvm\n")
    bad = tmp_path / "inventory.yml"
    bad.write_text("plugin: something_else\n")
    assert plugin.verify_file(str(good)) is True
    assert plugin.verify_file(str(bad)) is False
    assert plugin.verify_file(str(tmp_path / "missing.tencentcloud_cvm.yml")) is False
