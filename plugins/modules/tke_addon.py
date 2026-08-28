#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: tke_addon
short_description: Manage a Tencent Kubernetes Engine addon
version_added: "0.13.0"
description: Installs, updates and removes a TKE addon with idempotent version and values management.
options:
  state: {description: Desired addon lifecycle state., type: str, choices: [present, absent], default: present}
  cluster_id: {description: ID of the parent TKE cluster., type: str, required: true}
  name: {description: Addon name from the TKE addon catalog., type: str, required: true}
  version: {description: Addon version to install or enforce., type: str}
  values: {description: Addon values as a mapping or raw JSON string., type: raw, default: {}}
  update_strategy: {description: Update strategy in Tencent Cloud API JSON shape., type: raw}
  retries: {description: Number of retries for transient SDK failures., type: int, default: 5}
  waiter_delay: {description: Seconds between state-polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent value appended to SDK requests., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tke_addon:
    cluster_id: cls-abc123
    name: cbs
    version: 1.4.0
    values: {replicaCount: 2}
'''
RETURN = r'''
addon: {description: Addon metadata, type: dict, returned: always}
'''

import json

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_tke():
    from tencentcloud.tke.v20180525 import models, tke_client

    return models, tke_client


def _raw(value):
    if isinstance(value, str):
        try:
            return json.dumps(json.loads(value), sort_keys=True, separators=(",", ":"))
        except ValueError:
            return value
    return json.dumps(value or {}, sort_keys=True, separators=(",", ":"))


def describe_addon(module, client, models, cluster_id, name):
    request = models.DescribeAddonRequest()
    request.ClusterId, request.AddonName = cluster_id, name
    try:
        response = module.sdk_call(client.DescribeAddon, request)
    except Exception as exc:
        if getattr(exc, "get_code", lambda: "")() in ("ResourceNotFound", "ResourceNotFound.Addon"):
            return None
        raise
    addon = getattr(response, "Addon", None) or getattr(response, "AddonInfo", None)
    return json.loads(addon.to_json_string()) if addon else None


def build_install_request(models, params):
    request = models.InstallAddonRequest()
    request.ClusterId, request.AddonName = params["cluster_id"], params["name"]
    request.AddonVersion, request.RawValues = params["version"], _raw(params["values"])
    return request


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "cluster_id": {"type": "str", "required": True},
            "name": {"type": "str", "required": True},
            "version": {"type": "str"},
            "values": {"type": "raw", "default": {}},
            "update_strategy": {"type": "raw"},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, tke_client = _load_tke()
    client = module.create_client(tke_client.TkeClient, "tke.tencentcloudapi.com")
    try:
        current = describe_addon(module, client, models, p["cluster_id"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, addon=None, msg="TKE addon already absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), addon=current, msg="Would delete TKE addon")
            request = models.DeleteAddonRequest()
            request.ClusterId, request.AddonName = p["cluster_id"], p["name"]
            module.sdk_call(client.DeleteAddon, request)
            module.exit_json(changed=True, **(diff or {}), addon=None, msg="TKE addon deleted")
        desired = {"AddonName": p["name"], "AddonVersion": p["version"], "RawValues": _raw(p["values"])}
        if current is None:
            if not p["version"]:
                module.fail_json(msg="version is required to install a TKE addon")
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), addon=None, msg="Would install TKE addon")
            module.sdk_call(client.InstallAddon, build_install_request(models, p))
            module.exit_json(changed=True, **(diff or {}), addon=describe_addon(module, client, models, p["cluster_id"], p["name"]), msg="TKE addon installed")
        version_drift = p["version"] is not None and current.get("AddonVersion") != p["version"]
        values_drift = _raw(current.get("RawValues")) != _raw(p["values"])
        if not version_drift and not values_drift:
            module.exit_json(changed=False, addon=current, msg="TKE addon is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), addon=current, msg="Would update TKE addon")
        request = models.UpdateAddonRequest()
        request.ClusterId, request.AddonName = p["cluster_id"], p["name"]
        request.AddonVersion, request.RawValues = p["version"] or current.get("AddonVersion"), _raw(p["values"])
        if p["update_strategy"] is not None:
            request.UpdateStrategy = _raw(p["update_strategy"])
        module.sdk_call(client.UpdateAddon, request)
        module.exit_json(changed=True, **(diff or {}), addon=describe_addon(module, client, models, p["cluster_id"], p["name"]), msg="TKE addon updated")
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )


def main():
    run_module()


if __name__ == "__main__":
    main()
