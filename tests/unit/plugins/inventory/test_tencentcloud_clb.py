"""Unit tests for the tencentcloud_clb inventory plugin helpers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest

from ansible.errors import AnsibleError

from ansible_collections.susunola.tencentcloud.plugins.inventory import (
    tencentcloud_clb as inv_mod,
)
from ansible_collections.susunola.tencentcloud.plugins.inventory.tencentcloud_clb import (
    InventoryModule,
    backend_hostname,
    build_describe_lbs_request,
    list_backends,
    list_load_balancers,
    serialize,
)


class FakeRequest(object):
    pass


class FakeModels(object):
    DescribeLoadBalancersRequest = FakeRequest
    DescribeListenersRequest = FakeRequest
    DescribeTargetsRequest = FakeRequest


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


def test_build_describe_lbs_request_plain():
    request = build_describe_lbs_request(FakeModels, [], 10, 100)
    assert request.Offset == 10
    assert request.Limit == 100
    assert not hasattr(request, "LoadBalancerIds")


def test_build_describe_lbs_request_with_ids():
    request = build_describe_lbs_request(FakeModels, ["lb-1", "lb-2"], 0, 100)
    assert request.LoadBalancerIds == ["lb-1", "lb-2"]


def test_serialize_sdk_object_and_dict():
    assert serialize(FakeSdkItem({"LoadBalancerId": "lb-1"})) == {"LoadBalancerId": "lb-1"}
    assert serialize({"LoadBalancerId": "lb-2"}) == {"LoadBalancerId": "lb-2"}


# ---------------------------------------------------------------------------
# paginated listing
# ---------------------------------------------------------------------------


class FakeLbPageResponse(object):
    def __init__(self, items, total):
        self.LoadBalancerSet = items
        self.TotalCount = total


class FakeLbClient(object):
    def __init__(self, pages, total):
        self.pages = pages
        self.total = total
        self.offsets = []

    def DescribeLoadBalancers(self, request):
        self.offsets.append(request.Offset)
        idx = self.offsets.index(request.Offset)
        return FakeLbPageResponse(self.pages[idx], self.total)


def test_list_load_balancers_paginates():
    pages = [
        [FakeSdkItem({"LoadBalancerId": "lb-1"}), FakeSdkItem({"LoadBalancerId": "lb-2"})],
        [FakeSdkItem({"LoadBalancerId": "lb-3"})],
    ]
    client = FakeLbClient(pages, total=3)
    lbs = list_load_balancers(client, FakeModels, [])
    assert [lb["LoadBalancerId"] for lb in lbs] == ["lb-1", "lb-2", "lb-3"]
    assert client.offsets == [0, 2]


def test_list_load_balancers_empty():
    client = FakeLbClient([[]], total=0)
    assert list_load_balancers(client, FakeModels, []) == []


# ---------------------------------------------------------------------------
# backend walk
# ---------------------------------------------------------------------------


class FakeListener(object):
    def __init__(self, listener_id, protocol, port):
        self.ListenerId = listener_id
        self.Protocol = protocol
        self.Port = port


class FakeTarget(object):
    def __init__(self, instance_id, private_ips=None):
        self.InstanceId = instance_id
        self.PrivateIpAddresses = private_ips or []

    def _serialize(self, allow_none=True):
        return {
            "InstanceId": self.InstanceId,
            "PrivateIpAddresses": self.PrivateIpAddresses,
        }


class FakeTargetGroup(object):
    def __init__(self, listener_id, targets):
        self.ListenerId = listener_id
        self.Targets = targets


class FakeListenersResponse(object):
    def __init__(self, listeners):
        self.Listeners = listeners


class FakeTargetsResponse(object):
    def __init__(self, groups):
        self.Targets = groups


class FakeWalkClient(object):
    def __init__(self, listeners, groups):
        self.listeners = listeners
        self.groups = groups
        self.requests = []

    def DescribeListeners(self, request):
        self.requests.append("listeners")
        assert request.LoadBalancerId == "lb-1"
        return FakeListenersResponse(self.listeners)

    def DescribeTargets(self, request):
        self.requests.append("targets")
        assert request.LoadBalancerId == "lb-1"
        return FakeTargetsResponse(self.groups)


def test_list_backends_attaches_listener_meta():
    client = FakeWalkClient(
        listeners=[
            FakeListener("lbl-http", "HTTP", 80),
            FakeListener("lbl-tcp", "TCP", 443),
        ],
        groups=[
            FakeTargetGroup("lbl-http", [FakeTarget("ins-1", ["10.0.0.1"])]),
            FakeTargetGroup("lbl-tcp", [FakeTarget("ins-2", ["10.0.0.2"])]),
        ],
    )
    backends = list_backends(client, FakeModels, "lb-1")
    assert len(backends) == 2
    assert backends[0]["listener_id"] == "lbl-http"
    assert backends[0]["protocol"] == "HTTP"
    assert backends[0]["listener_port"] == 80
    assert backends[1]["protocol"] == "TCP"
    assert backends[1]["listener_port"] == 443


def test_list_backends_unknown_listener_gets_none_meta():
    client = FakeWalkClient(
        listeners=[FakeListener("lbl-http", "HTTP", 80)],
        groups=[FakeTargetGroup("lbl-unknown", [FakeTarget("ins-9", ["10.0.0.9"])])],
    )
    backends = list_backends(client, FakeModels, "lb-1")
    assert backends[0]["protocol"] is None
    assert backends[0]["listener_port"] is None


def test_list_backends_empty():
    client = FakeWalkClient(listeners=[], groups=[])
    assert list_backends(client, FakeModels, "lb-1") == []


# ---------------------------------------------------------------------------
# hostname resolution
# ---------------------------------------------------------------------------


def test_backend_hostname_private_ip_first():
    backend = {"PrivateIpAddresses": ["10.0.0.1"], "InstanceId": "ins-1"}
    assert backend_hostname(backend, ["private-ip", "instance-id"], compose_stub) == "10.0.0.1"


def test_backend_hostname_falls_back_to_instance_id():
    backend = {"PrivateIpAddresses": [], "InstanceId": "ins-1"}
    assert backend_hostname(backend, ["private-ip", "instance-id"], compose_stub) == "ins-1"


def test_backend_hostname_jinja_expression():
    backend = {"InstanceId": "ins-1", "lb_name": "web-lb"}
    assert backend_hostname(backend, ["lb_name", "instance-id"], compose_stub) == "web-lb"


def test_backend_hostname_none_without_identity():
    assert backend_hostname({}, ["private-ip", "instance-id"], compose_stub) is None


# ---------------------------------------------------------------------------
# populate
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


def test_populate_adds_backend_hosts_with_lb_meta():
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
                "InstanceId": "ins-1",
                "PrivateIpAddresses": ["10.0.0.1"],
                "lb_id": "lb-1",
                "lb_name": "web-lb",
                "lb_vips": ["1.2.3.4"],
                "protocol": "HTTP",
                "listener_port": 80,
            },
            # no address and no instance id -> skipped
            {"PrivateIpAddresses": [], "lb_id": "lb-1"},
        ]
    }
    plugin._populate(results)

    assert plugin.inventory.hosts == ["10.0.0.1"]
    hostvars = plugin.inventory.variables["10.0.0.1"]
    assert hostvars["lb_id"] == "lb-1"
    assert hostvars["lb_vips"] == ["1.2.3.4"]
    assert hostvars["protocol"] == "HTTP"
    assert hostvars["region"] == "ap-guangzhou"
    assert len(composed) == 1


# ---------------------------------------------------------------------------
# verify_file / create_client
# ---------------------------------------------------------------------------


def test_verify_file(tmp_path):
    plugin = InventoryModule()
    good = tmp_path / "inventory.tencentcloud_clb.yml"
    good.write_text("plugin: susunola.tencentcloud.tencentcloud_clb\n")
    bad = tmp_path / "inventory.yml"
    bad.write_text("plugin: something_else\n")
    assert plugin.verify_file(str(good)) is True
    assert plugin.verify_file(str(bad)) is False
    assert plugin.verify_file(str(tmp_path / "missing.tencentcloud_clb.yml")) is False


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


class FakeClbClient(object):
    def __init__(self, credential, region, profile=None):
        self.credential = credential
        self.region = region
        self.profile = profile


def _stub_inventory_sdk(monkeypatch):
    monkeypatch.setattr(inv_mod, "tc_credential", FakeCredentialModule, raising=False)
    monkeypatch.setattr(inv_mod, "HttpProfile", FakeHttpProfile, raising=False)
    monkeypatch.setattr(inv_mod, "ClientProfile", FakeClientProfile, raising=False)
    monkeypatch.setattr(
        inv_mod, "clb_client", type("clb_client", (), {"ClbClient": FakeClbClient}),
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
