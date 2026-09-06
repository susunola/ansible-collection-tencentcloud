"""Unit tests for the tencentcloud_cos inventory plugin helpers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import pytest

from ansible.errors import AnsibleError

from ansible_collections.susunola.tencentcloud.plugins.inventory import (
    tencentcloud_cos as inv_mod,
)
from ansible_collections.susunola.tencentcloud.plugins.inventory.tencentcloud_cos import (
    InventoryModule,
    fetch_buckets,
    fetch_objects,
    filter_buckets,
    resolve_hostname,
)


def make_bucket(name="media-1250000000", location="ap-guangzhou", creation_date="2026-01-01"):
    return {"name": name, "location": location, "creation_date": creation_date}


def test_filter_buckets_returns_all_without_filters():
    buckets = [make_bucket("a-1", "ap-guangzhou"), make_bucket("b-1", "ap-singapore")]
    assert filter_buckets(buckets, [], None) == buckets


def test_filter_buckets_by_region():
    buckets = [make_bucket("a-1", "ap-guangzhou"), make_bucket("b-1", "ap-singapore")]
    selected = filter_buckets(buckets, ["ap-singapore"], None)
    assert [b["name"] for b in selected] == ["b-1"]


def test_filter_buckets_by_prefix():
    buckets = [make_bucket("prod-a-1"), make_bucket("dev-b-1")]
    selected = filter_buckets(buckets, [], "prod-")
    assert [b["name"] for b in selected] == ["prod-a-1"]


def test_filter_buckets_by_region_and_prefix():
    buckets = [
        make_bucket("prod-a-1", "ap-guangzhou"),
        make_bucket("prod-b-1", "ap-singapore"),
        make_bucket("dev-c-1", "ap-singapore"),
    ]
    selected = filter_buckets(buckets, ["ap-singapore"], "prod-")
    assert [b["name"] for b in selected] == ["prod-b-1"]


class FakeClient(object):
    """Stand-in for a CosS3Client with an in-memory object store."""

    def __init__(self, objects=None, truncated_pages=0):
        self.objects = list(objects or [])
        self.truncated_pages = truncated_pages
        self.list_objects_calls = []

    def list_objects(self, **kwargs):
        self.list_objects_calls.append(kwargs)
        marker = kwargs.get("Marker")
        page_size = kwargs.get("MaxKeys", 1000)
        prefix = kwargs.get("Prefix")
        pool = [k for k in self.objects if prefix is None or k.startswith(prefix)]
        start = 0
        if marker is not None:
            start = int(marker) + 1
        page = pool[start:start + page_size]
        is_truncated = start + len(page) < len(pool)
        next_marker = str(start + len(page) - 1) if is_truncated else None
        return {
            "Contents": [{"Key": k, "ETag": '"abc"', "Size": 10,
                          "LastModified": "2026-01-01T00:00:00Z",
                          "StorageClass": "STANDARD"} for k in page],
            "IsTruncated": "true" if is_truncated else "false",
            "NextMarker": next_marker,
        }


def test_fetch_objects_all_without_cap():
    client = FakeClient(objects=["a", "b", "c"])
    objects, truncated = fetch_objects(client, "media-1250000000", max_objects=0)
    assert [o["key"] for o in objects] == ["a", "b", "c"]
    assert truncated is False


def test_fetch_objects_caps_and_flags_truncation():
    client = FakeClient(objects=["a", "b", "c", "d"])
    objects, truncated = fetch_objects(client, "media-1250000000", max_objects=2)
    assert [o["key"] for o in objects] == ["a", "b"]
    assert truncated is True


def test_fetch_objects_cap_exact_not_truncated():
    client = FakeClient(objects=["a", "b"])
    objects, truncated = fetch_objects(client, "media-1250000000", max_objects=2)
    assert [o["key"] for o in objects] == ["a", "b"]
    assert truncated is False


def test_fetch_objects_prefix_passed_through():
    client = FakeClient(objects=["logs/a", "logs/b", "app/c"])
    objects, _truncated = fetch_objects(client, "media-1250000000", prefix="logs/", max_objects=0)
    assert [o["key"] for o in objects] == ["logs/a", "logs/b"]


def test_resolve_hostname_name_literal():
    bucket = make_bucket()
    assert resolve_hostname(["name"], bucket, None) == "media-1250000000"


def test_resolve_hostname_jinja_expression():
    def compose_stub(template, variables):
        return variables.get(template)

    bucket = make_bucket()
    assert resolve_hostname(["location", "name"], bucket, compose_stub) == "ap-guangzhou"


def test_resolve_hostname_none_without_value():
    bucket = make_bucket()
    assert resolve_hostname([], bucket, None) is None


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
        "hostnames": ["name"],
        "compose": {},
        "groups": {},
        "keyed_groups": [],
    }
    options.update(overrides)
    return options


def test_populate_adds_bucket_hosts_and_hostvars():
    plugin = _plugin(_populate_options())
    plugin.inventory = FakeInventory()
    composed, composed_groups, keyed_groups = [], [], []
    plugin._set_composite_vars = lambda *a, **k: composed.append((a, k))
    plugin._add_host_to_composed_groups = lambda *a, **k: composed_groups.append((a, k))
    plugin._add_host_to_keyed_groups = lambda *a, **k: keyed_groups.append((a, k))

    results = [
        make_bucket("media-1250000000", "ap-guangzhou"),
        make_bucket("backup-1250000000", "ap-singapore", creation_date="2026-02-02"),
    ]
    plugin._populate(results)

    assert plugin.inventory.hosts == ["media-1250000000", "backup-1250000000"]
    hostvars = plugin.inventory.variables["backup-1250000000"]
    assert hostvars["location"] == "ap-singapore"
    assert hostvars["region"] == "ap-singapore"
    assert hostvars["creation_date"] == "2026-02-02"
    assert len(composed) == 2
    assert len(composed_groups) == 2
    assert len(keyed_groups) == 2


def test_verify_file(tmp_path):
    plugin = InventoryModule()
    good = tmp_path / "inventory.tencentcloud_cos.yml"
    good.write_text("plugin: susunola.tencentcloud.tencentcloud_cos\n")
    bad = tmp_path / "inventory.yml"
    bad.write_text("plugin: something_else\n")
    assert plugin.verify_file(str(good)) is True
    assert plugin.verify_file(str(bad)) is False
    assert plugin.verify_file(str(tmp_path / "missing.tencentcloud_cos.yml")) is False


class FakeCosConfig(object):
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeCosClient(object):
    def __init__(self, config):
        self.config = config


def _stub_cos_sdk(monkeypatch):
    monkeypatch.setattr(inv_mod, "CosConfig", FakeCosConfig, raising=False)
    monkeypatch.setattr(inv_mod, "CosS3Client", FakeCosClient, raising=False)


CREATE_CLIENT_OPTIONS = {
    "secret_id": "akid-param",
    "secret_key": "secret-param",
    "token": None,
    "profile": None,
    "region": "ap-guangzhou",
}


def test_create_cos_client_uses_explicit_credentials(monkeypatch):
    _stub_cos_sdk(monkeypatch)

    def explode(*args, **kwargs):
        raise AssertionError("profile file must not be read")

    monkeypatch.setattr(inv_mod, "load_profile", explode)
    plugin = InventoryModule()
    plugin.get_option = CREATE_CLIENT_OPTIONS.get
    client = plugin._create_cos_client()
    assert client.config.kwargs["SecretId"] == "akid-param"
    assert client.config.kwargs["SecretKey"] == "secret-param"
    assert client.config.kwargs["Region"] == "ap-guangzhou"


def test_create_cos_client_falls_back_to_profile(monkeypatch):
    _stub_cos_sdk(monkeypatch)
    monkeypatch.setattr(
        inv_mod, "load_profile",
        lambda profile=None: {"secret_id": "akid-prod", "secret_key": "secret-prod"},
    )
    options = dict(CREATE_CLIENT_OPTIONS, secret_id=None, secret_key=None, profile="prod")
    plugin = InventoryModule()
    plugin.get_option = options.get
    client = plugin._create_cos_client()
    assert client.config.kwargs["SecretId"] == "akid-prod"
    assert client.config.kwargs["SecretKey"] == "secret-prod"


def test_create_cos_client_missing_everywhere_mentions_profile(monkeypatch):
    _stub_cos_sdk(monkeypatch)
    monkeypatch.setattr(inv_mod, "load_profile", lambda profile=None: {})
    options = dict(CREATE_CLIENT_OPTIONS, secret_id=None, secret_key=None)
    plugin = InventoryModule()
    plugin.get_option = options.get
    with pytest.raises(AnsibleError, match="default.configure"):
        plugin._create_cos_client()


def _noop_client():
    """Client stub; list_buckets/iter_objects are monkeypatched in the tests."""

    return object()


def test_fetch_buckets_filters_and_enriches(monkeypatch):
    buckets = [
        make_bucket("prod-a-1250000000", "ap-guangzhou"),
        make_bucket("prod-b-1250000000", "ap-singapore"),
    ]
    monkeypatch.setattr(inv_mod, "list_buckets", lambda client: buckets)
    monkeypatch.setattr(
        inv_mod, "iter_objects",
        lambda client, bucket, prefix=None: (o for o in [{"key": "x"}, {"key": "y"}]),
    )
    options = {
        "bucket_regions": ["ap-singapore"],
        "bucket_prefix": "prod-",
        "include_objects": True,
        "max_objects": 10,
        "object_prefix": None,
    }
    plugin = InventoryModule()
    plugin.get_option = options.get
    plugin._create_cos_client = _noop_client
    result = fetch_buckets(plugin)
    assert len(result) == 1
    assert result[0]["name"] == "prod-b-1250000000"
    assert [o["key"] for o in result[0]["objects"]] == ["x", "y"]
    assert result[0]["object_count"] == 2
    assert result[0]["objects_truncated"] is False


def test_fetch_buckets_without_objects_keeps_plain_buckets(monkeypatch):
    buckets = [make_bucket("prod-a-1250000000")]
    monkeypatch.setattr(inv_mod, "list_buckets", lambda client: buckets)
    options = {
        "bucket_regions": [],
        "bucket_prefix": None,
        "include_objects": False,
        "max_objects": 100,
        "object_prefix": None,
    }
    plugin = InventoryModule()
    plugin.get_option = options.get
    plugin._create_cos_client = _noop_client
    result = fetch_buckets(plugin)
    assert result == buckets
    assert "objects" not in result[0]
