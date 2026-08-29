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
  values: {description: "Addon values as a mapping or raw JSON/YAML string. When omitted on an existing addon, values are not managed.", type: raw}
  values_file: {description: Controller-side JSON or YAML file containing addon values., type: path}
  values_format: {description: Format used for O(values_file) or a string O(values)., type: str, choices: [auto, json, yaml], default: auto}
  update_strategy: {description: Strategy used to apply addon values., type: str, choices: [merge, replace], default: merge}
  api_dry_run: {description: Run the TKE API DryRun validation before installation or update., type: bool, default: false}
  allow_downgrade: {description: Allow changing to a numerically lower addon version., type: bool, default: false}
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
addon: {description: Addon metadata with raw values redacted, type: dict, returned: always}
'''

import base64
import json
import time

try:
    import yaml
except ImportError:
    yaml = None

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found


def _load_tke():
    from tencentcloud.tke.v20180525 import models, tke_client

    return models, tke_client


def _values_json(value):
    if isinstance(value, str):
        try:
            return json.dumps(json.loads(value), sort_keys=True, separators=(",", ":"))
        except ValueError:
            return value
    return json.dumps(value or {}, sort_keys=True, separators=(",", ":"))


def _safe_load_yaml(value):
    if yaml is None:
        raise ValueError("PyYAML is required to parse YAML addon values (install PyYAML)")
    try:
        return yaml.safe_load(value)
    except yaml.YAMLError as exc:
        raise ValueError("Invalid YAML addon values: %s" % exc)


def load_values(params):
    value = params.get("values")
    if params.get("values_file"):
        with open(params["values_file"], "r", encoding="utf-8") as stream:
            value = stream.read()
    if value is None or not isinstance(value, str):
        return value
    value_format = params.get("values_format", "auto")
    if value_format == "json":
        return json.loads(value)
    if value_format == "yaml":
        return _safe_load_yaml(value)
    try:
        return json.loads(value)
    except ValueError:
        return _safe_load_yaml(value)


def _raw(value):
    return base64.b64encode(_values_json(value).encode("utf-8")).decode("ascii")


def _canonical_raw(value):
    if not value:
        return _values_json({})
    try:
        value = base64.b64decode(value, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        pass
    return _values_json(value)


def _safe(addon):
    if addon is None:
        return None
    result = dict(addon)
    if "RawValues" in result:
        result["RawValues"] = "<redacted>"
    return result


def describe_addon(module, client, models, cluster_id, name):
    request = models.DescribeAddonRequest()
    request.ClusterId, request.AddonName = cluster_id, name
    try:
        response = module.sdk_call(client.DescribeAddon, request)
    except Exception as exc:
        if is_not_found(exc):
            return None
        raise
    addons = list(getattr(response, "Addons", None) or [])
    addon = next((item for item in addons if getattr(item, "AddonName", None) == name), None)
    return json.loads(addon.to_json_string()) if addon else None


def wait_for_addon(module, client, models, cluster_id, name, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        addon = describe_addon(module, client, models, cluster_id, name)
        if absent and addon is None:
            return None
        if not absent and addon:
            phase = str(addon.get("Phase") or "").lower()
            if phase == "succeeded":
                return addon
            if phase in ("installfailed", "upgradfailed", "upgradefailed"):
                module.fail_json(
                    msg="TKE addon operation failed",
                    addon=_safe(addon),
                    reason=addon.get("Reason"),
                )
        if time.time() >= deadline:
            module.fail_json(
                msg="Timed out waiting for TKE addon state",
                addon=_safe(addon),
                expected="absent" if absent else "Succeeded",
            )
        time.sleep(module.params["waiter_delay"])


def build_install_request(models, params):
    request = models.InstallAddonRequest()
    request.ClusterId, request.AddonName = params["cluster_id"], params["name"]
    request.AddonVersion, request.RawValues = params["version"], _raw(params["values"])
    return request


def build_update_request(models, params, current):
    request = models.UpdateAddonRequest()
    request.ClusterId, request.AddonName = params["cluster_id"], params["name"]
    request.AddonVersion = params["version"] or current.get("AddonVersion")
    if params["values"] is not None:
        request.RawValues = _raw(params["values"])
    request.UpdateStrategy = params["update_strategy"]
    return request


def _version_tuple(value):
    try:
        return tuple(int(part) for part in str(value).lstrip("v").split("."))
    except ValueError:
        return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "cluster_id": {"type": "str", "required": True},
            "name": {"type": "str", "required": True},
            "version": {"type": "str"},
            "values": {"type": "raw", "no_log": True},
            "values_file": {"type": "path"},
            "values_format": {"type": "str", "choices": ["auto", "json", "yaml"], "default": "auto"},
            "update_strategy": {"type": "str", "choices": ["merge", "replace"], "default": "merge"},
            "api_dry_run": {"type": "bool", "default": False},
            "allow_downgrade": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
        mutually_exclusive=[("values", "values_file")],
    )
    p = module.params
    try:
        p["values"] = load_values(p)
    except (OSError, ValueError) as exc:
        module.fail_json(msg="Unable to load addon values", error=str(exc))
    module.require_sdk()
    models, tke_client = _load_tke()
    client = module.create_client(tke_client.TkeClient, "tke.tencentcloudapi.com")
    try:
        current = describe_addon(module, client, models, p["cluster_id"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, addon=None, msg="TKE addon already absent")
            diff = maybe_diff(module, _safe(current), None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), addon=_safe(current), msg="Would delete TKE addon")
            request = models.DeleteAddonRequest()
            request.ClusterId, request.AddonName = p["cluster_id"], p["name"]
            module.sdk_call(client.DeleteAddon, request)
            wait_for_addon(module, client, models, p["cluster_id"], p["name"], absent=True)
            module.exit_json(changed=True, **(diff or {}), addon=None, msg="TKE addon deleted")
        desired = {"AddonName": p["name"], "AddonVersion": p["version"]}
        if p["values"] is not None:
            desired["RawValues"] = _raw(p["values"])
        if current is None:
            if not p["version"]:
                module.fail_json(msg="version is required to install a TKE addon")
            diff = maybe_diff(module, None, _safe(desired))
            if module.check_mode and not p["api_dry_run"]:
                module.exit_json(changed=True, **(diff or {}), addon=None, msg="Would install TKE addon")
            request = build_install_request(models, p)
            if p["api_dry_run"]:
                request.DryRun = True
                module.sdk_call(client.InstallAddon, request)
                if module.check_mode:
                    module.exit_json(changed=True, **(diff or {}), addon=None, msg="TKE addon installation validated")
                request = build_install_request(models, p)
            module.sdk_call(client.InstallAddon, request)
            current = wait_for_addon(module, client, models, p["cluster_id"], p["name"])
            module.exit_json(changed=True, **(diff or {}), addon=_safe(current), msg="TKE addon installed")
        version_drift = p["version"] is not None and current.get("AddonVersion") != p["version"]
        values_drift = p["values"] is not None and _canonical_raw(current.get("RawValues")) != _values_json(p["values"])
        current_version = _version_tuple(current.get("AddonVersion"))
        desired_version = _version_tuple(p["version"])
        if version_drift and not p["allow_downgrade"] and current_version and desired_version and desired_version < current_version:
            module.fail_json(
                msg="Addon version downgrade is blocked; set allow_downgrade=true to continue",
                current_version=current.get("AddonVersion"),
                desired_version=p["version"],
            )
        if not version_drift and not values_drift:
            module.exit_json(changed=False, addon=_safe(current), msg="TKE addon is up to date")
        diff = maybe_diff(module, _safe(current), _safe(desired))
        if module.check_mode and not p["api_dry_run"]:
            module.exit_json(changed=True, **(diff or {}), addon=_safe(current), msg="Would update TKE addon")
        request = build_update_request(models, p, current)
        if p["api_dry_run"]:
            request.DryRun = True
            module.sdk_call(client.UpdateAddon, request)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), addon=_safe(current), msg="TKE addon update validated")
            request = build_update_request(models, p, current)
        module.sdk_call(client.UpdateAddon, request)
        current = wait_for_addon(module, client, models, p["cluster_id"], p["name"])
        module.exit_json(changed=True, **(diff or {}), addon=_safe(current), msg="TKE addon updated")
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
