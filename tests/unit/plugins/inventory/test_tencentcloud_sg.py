"""Unit tests for the tencentcloud_sg inventory plugin helpers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest

from ansible.errors import AnsibleError

from ansible_collections.susunola.tencentcloud.plugins.inventory import (
    tencentcloud_sg as inv_mod,
)
from ansible_collections.susunola.tencentcloud.plugins.inventory.tencentcloud_sg import (
    InventoryModule,
    build_list_enis_request,
    build_list_sgs_request,
    eni_hostname,
    eni_private_ip,
    list_network_interfaces,
    list_security_groups,
    serialize,
)


class FakeRequest(object):
    pass


class FakeFilter(object):
    pass


class FakeModels(object):
    Filter = FakeFilter
    DescribeSecurityGroupsRequest = FakeRequest
    DescribeNetworkInterfacesRequest = FakeRequest


class FakeSdkItem(object):
    def __init__(self, payload):
        self._payload = payload

    def _serialize(self, allow_none=True):
        return dict(self._payload)


def compose_stub(template, variables):
    return variables.get(template)


# ---------------------------------------------------------------------------
# request builders
# ---------------------------------------------------------------------------


def test_build_list_sgs_request_plain():
    request = build_list_sgs_request(FakeModels, [], 5, 100)
    assert request.Offset == 5
    assert request.Limit == 100
    assert not hasattr(request, "SecurityGroupIds")


def test_build_list_sgs_request_with_ids():
    request = build_list_sgs_request(FakeModels, ["sg-1", "sg-2"], 0, 100)
    assert request.SecurityGroupIds == ["sg-1", "sg-2"]


def test_build_list_enis_request_applies_sg_filter():
    request = build_list_enis_request(FakeModels, "sg-1", 0, 100)
    assert len(request.Filters) == 1
    assert request.Filters[0].Name == "security-group-id"
    assert request.Filters[0].Values == ["sg-1"]


def test_build_list_enis_request_without_filter():
    request = build_list_enis_request(FakeModels, None, 0, 100)
    assert not hasattr(request, "Filters")


def test_serialize_sdk_object_and_dict():
    assert serialize(FakeSdkItem({"SecurityGroupId": "sg-1"})) == {"SecurityGroupId": "sg-1"}
    assert serialize({"SecurityGroupId": "sg-2"}) == {"SecurityGroupId": "sg-2"}


# ---------------------------------------------------------------------------
# paginated listing
# ---------------------------------------------------------------------------


class FakeSgPageResponse(object):
    def __init__(self, items, total):
        self.SecurityGroupSet = items
        self.TotalCount = total


class FakeEniPageResponse(object):
    def __init__(self, items, total):
        self.NetworkInterfaceSet = items
        self.TotalCount = total


class FakeVpcClient(object):
    def __init__(self, sg_pages, eni_pages, sg_total, eni_total):
        self.sg_pages = sg_pages
        self.eni_pages = eni_pages
        self.sg_total = sg_total
        self.eni_total = eni_total
        self.sg_offsets = []
        self.eni_offsets = []
        self.eni_filters = []

    def DescribeSecurityGroups(self, request):
        self.sg_offsets.append(request.Offset)
        idx = self.sg_offsets.index(request.Offset)
        return FakeSgPageResponse(self.sg_pages[idx], self.sg_total)

    def DescribeNetworkInterfaces(self, request):
        self.eni_offsets.append(request.Offset)
        idx = self.eni_offsets.index(request.Offset)
        self.eni_filters.append(getattr(request, "Filters", None))
        return FakeEniPageResponse(self.eni_pages[idx], self.eni_total)


def test_list_security_groups_paginates():
    pages = [
        [FakeSdkItem({"SecurityGroupId": "sg-1"}), FakeSdkItem({"SecurityGroupId": "sg-2"})],
        [FakeSdkItem({"SecurityGroupId": "sg-3"})],
    ]
    client = FakeVpcClient(pages, [], sg_total=3, eni_total=0)
    groups = list_security_groups(client, FakeModels, [])
    assert [g["SecurityGroupId"] for g in groups] == ["sg-1", "sg-2", "sg-3"]
    assert client.sg_offsets == [0, 2]


def test_list_network_interfaces_paginates_with_filter():
    pages = [[FakeSdkItem({"NetworkInterfaceId": "eni-1"})], [FakeSdkItem({"NetworkInterfaceId": "eni-2"})]]
    client = FakeVpcClient([], pages, sg_total=0, eni_total=2)
    enis = list_network_interfaces(client, FakeModels, "sg-1")
    assert [eni["NetworkInterfaceId"] for eni in enis] == ["eni-1", "eni-2"]
    assert client.eni_offsets == [0, 1]
    assert client.eni_filters[0][0].Name == "security-group-id"


# ---------------------------------------------------------------------------
# hostname resolution
# ---------------------------------------------------------------------------


def test_eni_private_ip_extracts_first():
    eni = {"PrivateIpAddresses": [{"PrivateIpAddress": "10.0.0.1"}, {"PrivateIpAddress": "10.0.0.2"}]}
    assert eni_private_ip(eni) == "10.0.0.1"


def test_eni_private_ip_empty():
    assert eni_private_ip({}) is None
    assert eni_private_ip({"PrivateIpAddresses": [{"PrivateIpAddress": None}]}) is None


def test_eni_hostname_private_ip_first():
    eni = {"PrivateIpAddresses": [{"PrivateIpAddress": "10.0.0.1"}], "InstanceId": "ins-1"}
    assert eni_hostname(eni, ["private-ip", "instance-id"], compose_stub) == "10.0.0.1"


def test_eni_hostname_falls_back_to_instance_id():
    eni = {"InstanceId": "ins-1"}
    assert eni_hostname(eni, ["private-ip", "instance-id"], compose_stub) == "ins-1"


def test_eni_hostname_jinja_expression():
    eni = {"InstanceId": "ins-1", "NetworkInterfaceName": "bastion"}
    assert eni_hostname(eni, ["NetworkInterfaceName", "instance-id"], compose_stub) == "bastion"


def test_eni_hostname_none_without_identity():
    assert eni_hostname({}, ["private-ip", "instance-id"], compose_stub) is None


# ---------------------------------------------------------------------------
# populate (dedup across security groups)
# ---------------------------------------------------------------------------


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


def test_populate_deduplicates_hosts_across_security_groups():
    plugin = _plugin(_populate_options())
    plugin.inventory = FakeInventory()
    plugin._compose = compose_stub
    composed, composed_groups, keyed_groups = [], [], []
    plugin._set_composite_vars = lambda *a, **k: composed.append((a, k))
    plugin._add_host_to_composed_groups = lambda *a, **k: composed_groups.append((a, k))
    plugin._add_host_to_keyed_groups = lambda *a, **k: keyed_groups.append((a, k))

    results = {
        "ap-guangzhou": [
            {
                "hostname": "10.0.0.1",
                "instance_id": "ins-1",
                "region": "ap-guangzhou",
                "sg_ids": ["sg-web", "sg-app"],
                "sg_names": ["web", "app"],
                "eni_ids": ["eni-1"],
            },
            # a host with no resolvable identity is dropped by _populate
            {"hostname": None, "instance_id": "ins-2"},
        ]
    }
    plugin._populate(results)

    assert plugin.inventory.hosts == ["10.0.0.1"]
    hostvars = plugin.inventory.variables["10.0.0.1"]
    assert hostvars["instance_id"] == "ins-1"
    assert hostvars["sg_ids"] == ["sg-web", "sg-app"]
    assert hostvars["eni_ids"] == ["eni-1"]
    assert hostvars["region"] == "ap-guangzhou"
    # the temporary "hostname" key must not leak into hostvars
    assert "hostname" not in hostvars
    assert len(composed) == 1


def test_populate_multiple_hosts():
    plugin = _plugin(_populate_options())
    plugin.inventory = FakeInventory()
    plugin._compose = compose_stub
    plugin._set_composite_vars = lambda *a, **k: None
    plugin._add_host_to_composed_groups = lambda *a, **k: None
    plugin._add_host_to_keyed_groups = lambda *a, **k: None

    results = {
        "ap-guangzhou": [
            {"hostname": "10.0.0.1", "instance_id": "ins-1", "sg_ids": ["sg-1"]},
            {"hostname": "10.0.0.2", "instance_id": "ins-2", "sg_ids": ["sg-1"]},
        ]
    }
    plugin._populate(results)
    assert plugin.inventory.hosts == ["10.0.0.1", "10.0.0.2"]


# ---------------------------------------------------------------------------
# verify_file / create_client
# ---------------------------------------------------------------------------


def test_verify_file(tmp_path):
    plugin = InventoryModule()
    good = tmp_path / "inventory.tencentcloud_sg.yml"
    good.write_text("plugin: susunola.tencentcloud.tencentcloud_sg\n")
    bad = tmp_path / "inventory.yml"
    bad.write_text("plugin: something_else\n")
    assert plugin.verify_file(str(good)) is True
    assert plugin.verify_file(str(bad)) is False
    assert plugin.verify_file(str(tmp_path / "missing.tencentcloud_sg.yml")) is False


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


class FakeVpcClientStub(object):
    def __init__(self, credential, region, profile=None):
        self.credential = credential
        self.region = region
        self.profile = profile


def _stub_inventory_sdk(monkeypatch):
    monkeypatch.setattr(inv_mod, "tc_credential", FakeCredentialModule, raising=False)
    monkeypatch.setattr(inv_mod, "HttpProfile", FakeHttpProfile, raising=False)
    monkeypatch.setattr(inv_mod, "ClientProfile", FakeClientProfile, raising=False)
    monkeypatch.setattr(
        inv_mod, "vpc_client", type("vpc_client", (), {"VpcClient": FakeVpcClientStub}),
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
    client = plugin._create_client("ap-guangzhou")
    assert client.credential.secret_id == "akid-param"
    assert client.credential.secret_key == "secret-param"
    assert client.region == "ap-guangzhou"


def test_create_client_falls_back_to_profile(monkeypatch):
    _stub_inventory_sdk(monkeypatch)
    monkeypatch.setattr(
        inv_mod, "load_profile",
        lambda profile=None: {"secret_id": "akid-prod", "secret_key": "secret-prod"},
    )
    options = dict(CREATE_CLIENT_OPTIONS, secret_id=None, secret_key=None, profile="prod")
    plugin = InventoryModule()
    plugin.get_option = options.get
    client = plugin._create_client("ap-guangzhou")
    assert client.credential.secret_id == "akid-prod"
    assert client.credential.secret_key == "secret-prod"


def test_create_client_missing_everywhere_mentions_profile(monkeypatch):
    _stub_inventory_sdk(monkeypatch)
    monkeypatch.setattr(inv_mod, "load_profile", lambda profile=None: {})
    options = dict(CREATE_CLIENT_OPTIONS, secret_id=None, secret_key=None)
    plugin = InventoryModule()
    plugin.get_option = options.get
    with pytest.raises(AnsibleError, match="default.configure"):
        plugin._create_client("ap-guangzhou")
