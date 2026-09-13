"""Unit tests for the unified tc_inventory plugin."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest

from ansible.errors import AnsibleError

from ansible_collections.susunola.tencentcloud.plugins.inventory import (
    tc_inventory as inv_mod,
)
from ansible_collections.susunola.tencentcloud.plugins.inventory.tc_inventory import (
    InventoryModule,
)
from ansible_collections.susunola.tencentcloud.plugins.module_utils.inventory import (
    SOURCE_SPECS,
    InventorySourceError,
    describe_entry,
    merge_entries,
)


class FakeInventory(object):
    """Mirrors the parts of InventoryData the plugin relies on.

    Two behaviours matter and are deliberately reproduced rather than
    stubbed away, because both have already caused a live failure:

    * adding a known host twice is a no-op;
    * ``add_host(..., group=...)`` does **not** create the group. Recent
      ansible-core raises ``Could not find group <name> in inventory`` when
      the group is absent (its docstring still claims otherwise), so a plugin
      that forgets ``add_group()`` passes every test and fails in production.
    """

    def __init__(self):
        self.hosts = []
        self.groups = {}
        self.variables = {}

    def add_group(self, group):
        self.groups.setdefault(group, [])

    def add_host(self, hostname, group=None):
        if group is not None and group not in self.groups:
            raise AnsibleError("Could not find group {0} in inventory".format(group))
        if hostname not in self.hosts:
            self.hosts.append(hostname)
        if group:
            members = self.groups.setdefault(group, [])
            if hostname not in members:
                members.append(hostname)

    def set_variable(self, hostname, key, value):
        self.variables.setdefault(hostname, {})[key] = value


def _plugin(options):
    plugin = InventoryModule()
    plugin.get_option = lambda name: options[name]
    return plugin


def _options(**overrides):
    options = {
        "sources": ["cvm"],
        "regions": ["ap-singapore"],
        "filters": {},
        "hostnames": ["private-ip", "public-ip", "name", "id"],
        "dedupe": True,
        "source_groups": True,
        "secret_id": "akid-param",
        "secret_key": "secret-param",
        "token": None,
        "profile": None,
        "cache": False,
        "strict": False,
        "compose": {},
        "groups": {},
        "keyed_groups": [],
    }
    options.update(overrides)
    return options


def test_verify_file_accepts_only_its_own_suffix(tmp_path):
    plugin = InventoryModule()
    good = tmp_path / "inventory.tc_inventory.yml"
    good.write_text("plugin: susunola.tencentcloud.tc_inventory\n")
    bad = tmp_path / "inventory.yml"
    bad.write_text("plugin: tc_inventory\n")
    assert plugin.verify_file(str(good)) is True
    assert plugin.verify_file(str(bad)) is False
    assert plugin.verify_file(str(tmp_path / "missing.tc_inventory.yml")) is False


# ---------------------------------------------------------------------------
# Option handling
# ---------------------------------------------------------------------------

def test_specs_reject_an_unknown_source():
    plugin = _plugin(_options(sources=["cvm", "rds"]))
    with pytest.raises(AnsibleError, match="Unknown inventory source 'rds'"):
        plugin._specs()


def test_specs_keep_the_configured_order():
    plugin = _plugin(_options(sources=["vpc", "cvm"]))
    assert [spec.name for spec in plugin._specs()] == ["vpc", "cvm"]


def test_source_filters_accept_only_enabled_sources():
    plugin = _plugin(_options(sources=["cvm"], filters={"vpc": []}))
    with pytest.raises(AnsibleError, match="not an enabled source"):
        plugin._source_filters(plugin._specs())


def test_source_filters_reject_a_bare_list():
    plugin = _plugin(_options(filters=[{"name": "instance-state", "values": ["RUNNING"]}]))
    with pytest.raises(AnsibleError, match="must be a mapping of source name"):
        plugin._source_filters(plugin._specs())


def test_source_filters_returns_only_configured_entries():
    filters = {"cvm": [{"name": "instance-state", "values": ["RUNNING"]}]}
    plugin = _plugin(_options(sources=["cvm", "vpc"], filters=filters))
    assert plugin._source_filters(plugin._specs()) == filters


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def test_fetch_source_builds_a_client_per_source_and_normalises(monkeypatch):
    seen = {}

    def fake_build_client(spec, region, secret_id, secret_key, token):
        seen["client"] = (spec.name, region, secret_id, secret_key, token)
        return "client-for-" + spec.name

    def fake_collect(spec, client, filters):
        seen["collect"] = (client, filters)
        return [{"InstanceId": "ins-1", "InstanceName": "web-1", "PrivateIpAddresses": ["10.0.0.4"]}]

    monkeypatch.setattr(inv_mod, "resolve_credentials", lambda *a, **k: ("akid", "secret", "tok"))
    monkeypatch.setattr(inv_mod, "build_client", fake_build_client)
    monkeypatch.setattr(inv_mod, "collect_source", fake_collect)

    plugin = _plugin(_options())
    entries = plugin._fetch_source(SOURCE_SPECS["cvm"], "ap-singapore", [{"name": "zone"}])
    assert seen["client"] == ("cvm", "ap-singapore", "akid", "secret", "tok")
    assert seen["collect"] == ("client-for-cvm", [{"name": "zone"}])
    assert entries[0]["tc_id"] == "ins-1"
    assert entries[0]["tc_region"] == "ap-singapore"
    assert entries[0]["tc_source"] == "cvm"


def test_fetch_source_wraps_inventory_errors_as_ansible_errors(monkeypatch):
    def explode(spec, client, filters):
        raise InventorySourceError("The tencentcloud-sdk-python-vpc package is required")

    monkeypatch.setattr(inv_mod, "resolve_credentials", lambda *a, **k: ("id", "key", None))
    monkeypatch.setattr(inv_mod, "build_client", lambda *a, **k: "client")
    monkeypatch.setattr(inv_mod, "collect_source", explode)

    plugin = _plugin(_options())
    with pytest.raises(AnsibleError, match="tencentcloud-sdk-python-vpc"):
        plugin._fetch_source(SOURCE_SPECS["vpc"], "ap-singapore", None)


def _entry(source, **fields):
    return describe_entry(SOURCE_SPECS[source], "ap-singapore", fields)


def test_fetch_all_queries_every_source_in_every_region_with_its_own_filters():
    plugin = _plugin(_options(sources=["cvm", "vpc"], regions=["ap-singapore", "ap-guangzhou"],
                              filters={"cvm": [{"name": "zone"}]}))
    calls = []

    def fake_fetch_source(spec, region, filters):
        calls.append((spec.name, region, filters))
        return [_entry(spec.name, VpcId="vpc-1")] if spec.name == "vpc" else []

    plugin._fetch_source = fake_fetch_source
    results = plugin._fetch_all(
        plugin._specs(), ["ap-singapore", "ap-guangzhou"],
        {"cvm": [{"name": "zone"}]}, dedupe=True)
    assert calls == [
        ("cvm", "ap-singapore", [{"name": "zone"}]),
        ("vpc", "ap-singapore", None),
        ("cvm", "ap-guangzhou", [{"name": "zone"}]),
        ("vpc", "ap-guangzhou", None),
    ]
    assert sorted(results) == ["ap-guangzhou", "ap-singapore"]
    assert results["ap-singapore"][0]["tc_id"] == "vpc-1"


def test_fetch_all_merges_across_sources_when_dedupe_is_on():
    plugin = _plugin(_options(sources=["cvm", "tke"]))
    plugin._fetch_source = lambda spec, region, filters: [
        _entry(spec.name, InstanceId="ins-1", InstanceName="web-1") if spec.name == "cvm"
        else _entry("tke", InstanceId="ins-1", ClusterId="cls-1", ClusterName="prod")
    ]

    deduped = plugin._fetch_all(plugin._specs(), ["ap-singapore"], {}, dedupe=True)
    assert len(deduped["ap-singapore"]) == 1
    assert deduped["ap-singapore"][0]["tc_sources"] == ["cvm", "tke"]

    kept = plugin._fetch_all(plugin._specs(), ["ap-singapore"], {}, dedupe=False)
    assert len(kept["ap-singapore"]) == 2


# ---------------------------------------------------------------------------
# Populating
# ---------------------------------------------------------------------------

def test_populate_adds_hosts_hostvars_and_source_groups():
    plugin = _plugin(_options())
    plugin.inventory = FakeInventory()
    composed, composed_groups, keyed = [], [], []
    plugin._set_composite_vars = lambda *a, **k: composed.append((a, k))
    plugin._add_host_to_composed_groups = lambda *a, **k: composed_groups.append((a, k))
    plugin._add_host_to_keyed_groups = lambda *a, **k: keyed.append((a, k))

    results = {"ap-singapore": [
        _entry("cvm", InstanceId="ins-1", InstanceName="web-1",
               PrivateIpAddresses=["10.0.0.4"], PublicIpAddresses=["1.2.3.4"]),
        _entry("cvm", InstanceId="ins-2", InstanceName="db-1"),
    ]}
    plugin._populate(results)

    assert plugin.inventory.hosts == ["10.0.0.4", "db-1"]
    assert plugin.inventory.groups == {"tc_cvm": ["10.0.0.4", "db-1"]}
    hostvars = plugin.inventory.variables["10.0.0.4"]
    assert hostvars["tc_id"] == "ins-1"
    assert hostvars["tc_name"] == "web-1"
    assert hostvars["tc_public_ip"] == "1.2.3.4"
    assert hostvars["InstanceName"] == "web-1"
    assert hostvars["region"] == "ap-singapore"
    assert len(composed) == 2
    assert len(composed_groups) == 2
    assert len(keyed) == 2


def test_populate_puts_a_merged_host_in_every_source_group():
    plugin = _plugin(_options())
    plugin.inventory = FakeInventory()
    plugin._set_composite_vars = lambda *a, **k: None
    plugin._add_host_to_composed_groups = lambda *a, **k: None
    plugin._add_host_to_keyed_groups = lambda *a, **k: None

    merged = merge_entries([
        _entry("cvm", InstanceId="ins-1", PrivateIpAddresses=["10.0.0.4"]),
        _entry("tke", InstanceId="ins-1", LanIP="10.0.0.4", ClusterId="cls-1"),
    ])
    assert merged[0]["tc_sources"] == ["cvm", "tke"]

    plugin._populate({"ap-singapore": merged})
    assert set(plugin.inventory.groups) == {"tc_cvm", "tc_tke"}
    assert plugin.inventory.groups["tc_tke"] == ["10.0.0.4"]


def test_populate_can_skip_source_groups():
    plugin = _plugin(_options(source_groups=False))
    plugin.inventory = FakeInventory()
    plugin._set_composite_vars = lambda *a, **k: None
    plugin._add_host_to_composed_groups = lambda *a, **k: None
    plugin._add_host_to_keyed_groups = lambda *a, **k: None

    plugin._populate({"ap-singapore": [_entry("cvm", InstanceId="ins-1", PrivateIpAddresses=["10.0.0.4"])]})
    assert plugin.inventory.groups == {}
    assert plugin.inventory.hosts == ["10.0.0.4"]


def test_populate_skips_entries_without_a_usable_hostname():
    plugin = _plugin(_options(hostnames=["private-ip"]))
    plugin.inventory = FakeInventory()
    plugin._set_composite_vars = lambda *a, **k: None
    plugin._add_host_to_composed_groups = lambda *a, **k: None
    plugin._add_host_to_keyed_groups = lambda *a, **k: None

    plugin._populate({"ap-singapore": [_entry("vpc", VpcId="vpc-1", VpcName="prod-vpc")]})
    assert plugin.inventory.hosts == []


def test_populate_iterates_regions_in_a_stable_order():
    """Region order follows sorted() keys, not the order of the results dict."""
    plugin = _plugin(_options(regions=["ap-singapore", "ap-guangzhou"]))
    plugin.inventory = FakeInventory()
    plugin._set_composite_vars = lambda *a, **k: None
    plugin._add_host_to_composed_groups = lambda *a, **k: None
    plugin._add_host_to_keyed_groups = lambda *a, **k: None

    plugin._populate({
        "ap-singapore": [_entry("cvm", InstanceId="ins-1", PrivateIpAddresses=["10.0.0.1"])],
        "ap-guangzhou": [_entry("cvm", InstanceId="ins-2", PrivateIpAddresses=["10.0.1.1"])],
    })
    assert plugin.inventory.hosts == ["10.0.1.1", "10.0.0.1"]


# ---------------------------------------------------------------------------
# parse() orchestration and caching
# ---------------------------------------------------------------------------

def _parse_plugin(options, inventory=None):
    """Return a plugin wired for parse(): no file, no cache plugin, recording."""
    plugin = _plugin(options)
    plugin.inventory = inventory or FakeInventory()
    plugin._read_config_data = lambda path: None
    plugin.load_cache_plugin = lambda: None
    plugin._cache = {}
    plugin.populated = []
    plugin._populate = plugin.populated.append
    return plugin


def test_parse_requires_regions():
    plugin = _parse_plugin(_options(regions=[]))
    with pytest.raises(AnsibleError, match="TENCENTCLOUD_REGION"):
        plugin.parse(plugin.inventory, None, "/tmp/inventory.tc_inventory.yml")


def test_parse_fetches_and_populates_without_caching():
    plugin = _parse_plugin(_options())
    plugin._fetch_all = lambda specs, regions, filters, dedupe: {"ap-singapore": ["entry"]}
    plugin.parse(plugin.inventory, None, "/tmp/inventory.tc_inventory.yml")
    assert plugin.populated == [{"ap-singapore": ["entry"]}]
    assert plugin._cache == {}


def test_parse_serves_a_matching_cache_entry_and_refreshes_on_a_miss():
    options = _options(cache=True)
    plugin = _parse_plugin(options)
    calls = []

    def fake_fetch(specs, regions, filters, dedupe):
        calls.append(list(regions))
        return {"ap-singapore": ["entry"]}

    plugin._fetch_all = fake_fetch
    plugin.parse(plugin.inventory, None, "/tmp/inventory.tc_inventory.yml")
    assert calls == [["ap-singapore"]]
    assert len(plugin._cache) == 1

    # Second run: same configuration, so the cache answers.
    plugin.parse(plugin.inventory, None, "/tmp/inventory.tc_inventory.yml")
    assert calls == [["ap-singapore"]]

    # Third run: the region changed, so the configuration-aware key misses.
    plugin.get_option = lambda name: _options(
        cache=True, regions=["ap-guangzhou"])[name]
    plugin.parse(plugin.inventory, None, "/tmp/inventory.tc_inventory.yml")
    assert calls == [["ap-singapore"], ["ap-guangzhou"]]
    assert len(plugin._cache) == 2


def test_parse_refreshes_when_the_caller_disables_the_cache():
    plugin = _parse_plugin(_options(cache=True))
    calls = []

    def fake_fetch(specs, regions, filters, dedupe):
        calls.append(1)
        return {"ap-singapore": ["entry"]}

    plugin._fetch_all = fake_fetch
    plugin.parse(plugin.inventory, None, "/tmp/inventory.tc_inventory.yml")
    plugin.parse(plugin.inventory, None, "/tmp/inventory.tc_inventory.yml", cache=False)
    assert len(calls) == 2
