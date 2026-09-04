# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
name: tencentcloud_cos
short_description: Tencent Cloud COS bucket and object dynamic inventory source
version_added: "0.14.0"
description:
  - List the Tencent Cloud Object Storage (COS) buckets of the account and
    expose them as Ansible hosts, keyed by the (globally unique) bucket name.
  - Buckets are listed account-wide through the COS GetService API, so no
    per-region scan is needed; the bucket's C(location) is attached as a host
    variable for grouping.
  - When O(include_objects) is set, each bucket host also carries an
    C(objects) list (capped by O(max_objects)) and an C(object_count), which
    is handy for lifecycle, backup and audit playbooks.
options:
  plugin:
    description: Marks this file as a Tencent Cloud COS inventory source.
    type: str
    required: true
    choices: ["tencentcloud_cos", "susunola.tencentcloud.tencentcloud_cos"]
  region:
    description:
      - Region used to build the COS client. COS bucket listing is
        account-wide, so this only selects the client endpoint, not the
        buckets returned.
      - Falls back to C(TENCENTCLOUD_REGION).
    type: str
    default: ap-guangzhou
    env:
      - name: TENCENTCLOUD_REGION
  bucket_regions:
    description:
      - Restrict the inventory to buckets whose C(location) is in this list,
        e.g. C([ap-guangzhou, ap-singapore]). When empty every bucket of the
        account is listed.
    type: list
    elements: str
    default: []
  bucket_prefix:
    description: Only include buckets whose name starts with this prefix.
    type: str
  include_objects:
    description:
      - When true, each bucket host carries an C(objects) list and an
        C(object_count) host variable. The listing is capped by O(max_objects)
        per bucket.
    type: bool
    default: false
  object_prefix:
    description:
      - When O(include_objects) is set, only list objects whose key starts
        with this prefix.
    type: str
  max_objects:
    description:
      - Maximum number of objects listed per bucket when O(include_objects)
        is set. C(0) means no limit.
    type: int
    default: 100
  hostnames:
    description:
      - Ordered list of hostname sources; the first entry producing a value wins.
      - The literal values C(name) and C(full-name) select the bucket name;
        any other entry is evaluated as a Jinja2 expression against the
        bucket variables.
    type: list
    elements: str
    default: ["name"]
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
  - Requires the C(cos-python-sdk-v5) package on the controller.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
# Minimal source file, e.g. inventory.tencentcloud_cos.yml
plugin: susunola.tencentcloud.tencentcloud_cos

# Only buckets in Singapore, with their objects, grouped by region
plugin: susunola.tencentcloud.tencentcloud_cos
bucket_regions:
  - ap-singapore
include_objects: true
max_objects: 500
keyed_groups:
  - key: location
    prefix: cos
compose:
  ansible_host: name
'''

from itertools import islice

from ansible.errors import AnsibleError
from ansible.plugins.inventory import BaseInventoryPlugin, Cacheable, Constructable

from ansible_collections.susunola.tencentcloud.plugins.module_utils.client import load_profile
from ansible_collections.susunola.tencentcloud.plugins.module_utils.cos import (
    iter_objects,
    list_buckets,
)

try:
    from qcloud_cos import CosConfig, CosS3Client
    HAS_COS_SDK = True
except ImportError:
    HAS_COS_SDK = False

SDK_IMP_ERR = "The cos-python-sdk-v5 package is required on the Ansible controller."


def filter_buckets(buckets, bucket_regions, bucket_prefix):
    """Return the buckets matching the region and name-prefix filters."""
    selected = []
    for bucket in buckets:
        if bucket_regions and (bucket.get("location") or "") not in bucket_regions:
            continue
        if bucket_prefix and not (bucket.get("name") or "").startswith(bucket_prefix):
            continue
        selected.append(bucket)
    return selected


def fetch_objects(client, bucket, prefix=None, max_objects=100):
    """Return up to ``max_objects`` objects of a bucket as plain dicts.

    :returns: (objects, truncated) where ``truncated`` is True when more
        objects exist beyond the cap (or beyond the API's first response).
        ``max_objects == 0`` means no limit.
    """
    iterator = iter_objects(client, bucket, prefix=prefix)
    if max_objects and max_objects > 0:
        objects = list(islice(iterator, max_objects + 1))
        truncated = len(objects) > max_objects
        return objects[:max_objects], truncated
    objects = list(iterator)
    return objects, False


def resolve_hostname(hostnames, bucket, compose):
    """Return the first usable hostname from the configured sources."""
    for entry in hostnames or []:
        if entry in ("name", "full-name"):
            value = bucket.get("name")
        else:
            value = compose(entry, bucket)
        if value:
            return str(value)
    return None


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    NAME = "tencentcloud_cos"

    def verify_file(self, path):
        if super().verify_file(path):
            return path.endswith(("tencentcloud_cos.yml", "tencentcloud_cos.yaml"))
        return False

    def parse(self, inventory, loader, path, cache=True):
        if not HAS_COS_SDK:
            raise AnsibleError(SDK_IMP_ERR)
        super().parse(inventory, loader, path, cache=cache)
        self._read_config_data(path)

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
            results = fetch_buckets(self)
        if cache_needs_update:
            self._cache[cache_key] = results
        self._populate(results)

    def _create_cos_client(self):
        """Build a COS client directly from the SDK."""
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
        config = CosConfig(
            Region=self.get_option("region"),
            SecretId=secret_id,
            SecretKey=secret_key,
            Token=self.get_option("token"),
            Timeout=60,
        )
        return CosS3Client(config)

    def _populate(self, results):
        strict = self.get_option("strict")
        hostnames = self.get_option("hostnames")
        for bucket in results:
            hostname = resolve_hostname(hostnames, bucket, self._compose)
            if not hostname:
                continue
            self.inventory.add_host(hostname)
            hostvars = dict(bucket)
            hostvars["region"] = bucket.get("location")
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


def fetch_buckets(plugin):
    """Return the (filtered, optionally object-enriched) bucket list."""
    client = plugin._create_cos_client()
    buckets = list_buckets(client)
    buckets = filter_buckets(
        buckets,
        plugin.get_option("bucket_regions"),
        plugin.get_option("bucket_prefix"),
    )
    if not plugin.get_option("include_objects"):
        return buckets
    max_objects = plugin.get_option("max_objects") or 0
    object_prefix = plugin.get_option("object_prefix")
    for bucket in buckets:
        full_name = bucket["name"]
        objects, truncated = fetch_objects(client, full_name, prefix=object_prefix,
                                           max_objects=max_objects)
        bucket["objects"] = objects
        bucket["object_count"] = len(objects)
        bucket["objects_truncated"] = truncated
    return buckets
