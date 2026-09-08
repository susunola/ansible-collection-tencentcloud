#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_store_location
short_description: Configure Tencent Cloud DLC query-result storage locations
version_added: "0.14.0"
description:
  - Initializes the account-level DLC query-result COS location and reconciles its advanced location settings.
  - The base store location is immutable after initialization because DLC exposes no reset or delete operation.
options:
  store_location: {type: str, required: true, description: Base COSN query-result path.}
  advanced_enabled: {type: bool, description: Enable or disable advanced result storage.}
  advanced_store_location: {type: str, description: Advanced COSN result path; required when enabling advanced storage.}
  wait: {type: bool, default: true, description: Wait for readable configuration convergence.}
  waiter_delay: {type: int, default: 3, description: Seconds between polls.}
  waiter_timeout: {type: int, default: 180, description: Overall convergence timeout.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_store_location:
    store_location: cosn://analytics-results/
    advanced_enabled: true
    advanced_store_location: cosn://analytics-results/advanced/
"""
RETURN = r"""
store_location_config: {description: Effective base and advanced storage settings., type: dict, returned: always}
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def read(module, client, models):
    base = module.sdk_call(client.DescribeStoreLocation, models.DescribeStoreLocationRequest())
    advanced = module.sdk_call(client.DescribeAdvancedStoreLocation, models.DescribeAdvancedStoreLocationRequest())
    return {
        "StoreLocation": base.StoreLocation or "",
        "AdvancedEnabled": bool(int(advanced.Enable or 0)),
        "AdvancedStoreLocation": advanced.StoreLocation or "",
        "HasLakeFs": advanced.HasLakeFs,
        "LakeFsStatus": advanced.LakeFsStatus,
        "BucketType": advanced.BucketType,
    }


def create_request(models, location):
    request = models.CreateStoreLocationRequest()
    request.StoreLocation = location
    return request


def modify_request(models, enabled, location):
    request = models.ModifyAdvancedStoreLocationRequest()
    request.Enable, request.StoreLocation = 1 if enabled else 0, location
    return request


def desired(p, current=None):
    result = dict(current or {})
    result["StoreLocation"] = p["store_location"]
    if p.get("advanced_enabled") is not None:
        result["AdvancedEnabled"] = p["advanced_enabled"]
    if p.get("advanced_store_location") is not None:
        result["AdvancedStoreLocation"] = p["advanced_store_location"]
    return result


def advanced_drift(p, current):
    target, changes = desired(p, current), {}
    for source, key in (("advanced_enabled", "AdvancedEnabled"), ("advanced_store_location", "AdvancedStoreLocation")):
        if p.get(source) is not None and current.get(key) != target.get(key):
            changes[key] = (current.get(key), target.get(key))
    return changes


def wait_config(module, client, models, p, expected):
    def poll():
        current = read(module, client, models)
        return "ready" if all(current.get(k) == v for k, v in expected.items()) else "pending"

    wait_for_state(module, poll, ["ready"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    spec = {
        "store_location": {"required": True},
        "advanced_enabled": {"type": "bool"},
        "advanced_store_location": {},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 3},
        "waiter_timeout": {"type": "int", "default": 180},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if not p["store_location"].startswith("cosn://"):
        module.fail_json(msg="store_location must use a cosn:// path")
    if p.get("advanced_store_location") is not None and not p["advanced_store_location"].startswith("cosn://"):
        module.fail_json(msg="advanced_store_location must use a cosn:// path")
    if p.get("advanced_enabled") is True and not p.get("advanced_store_location"):
        module.fail_json(msg="advanced_store_location is required when advanced_enabled=true")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = read(module, client, models)
        original = dict(current)
        changed = False
        if current["StoreLocation"] and current["StoreLocation"] != p["store_location"]:
            module.fail_json(
                msg="DLC base store location is immutable after initialization",
                store_location_config=current,
                immutable_drift={"StoreLocation": (current["StoreLocation"], p["store_location"])},
            )
        if not current["StoreLocation"]:
            changed = True
            if not module.check_mode:
                module.sdk_call(client.CreateStoreLocation, create_request(models, p["store_location"]))
                if p["wait"]:
                    wait_config(module, client, models, p, {"StoreLocation": p["store_location"]})
                current = read(module, client, models)
            else:
                current["StoreLocation"] = p["store_location"]
        changes = advanced_drift(p, current)
        if changes:
            changed = True
            location = p.get("advanced_store_location") or current.get("AdvancedStoreLocation") or p["store_location"]
            enabled = p["advanced_enabled"] if p.get("advanced_enabled") is not None else current["AdvancedEnabled"]
            if not module.check_mode:
                module.sdk_call(client.ModifyAdvancedStoreLocation, modify_request(models, enabled, location))
                if p["wait"]:
                    wait_config(module, client, models, p, {k: v[1] for k, v in changes.items()})
                current = read(module, client, models)
            else:
                current.update({k: v[1] for k, v in changes.items()})
        diff_value = maybe_diff(module, original, desired(p, original)) if changed else None
        module.exit_json(changed=changed, **(diff_value or {}), store_location_config=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
