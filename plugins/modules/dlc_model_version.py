#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_model_version
short_description: Publish immutable Tencent Cloud DLC model versions
version_added: "0.14.0"
description:
  - Ensures that an immutable version exists for a DLC inference model.
  - The DLC API exposes neither version update nor deletion; conflicting metadata for an existing version is reported instead of overwritten.
options:
  model_uid: {type: str, required: true, description: Parent inference-model UID.}
  version: {type: str, required: true, description: Exact immutable version label.}
  description: {type: str, description: Version description.}
  storage_uri: {type: str, description: Version storage URI.}
  use_custom_storage: {type: bool, description: Whether the version uses customer storage.}
  storage_type: {type: str, choices: [LOCAL, CFS, COS, CFSTurbo, GooseFS], description: Version upload source type.}
  goosefs_config: {type: dict, description: GooseFSConfig-compatible creation object.}
  wait: {type: bool, default: true, description: Wait until the version is visible.}
  waiter_delay: {type: int, default: 5, description: Seconds between polls.}
  waiter_timeout: {type: int, default: 300, description: Overall convergence timeout.}
  retries: {type: int, default: 5, description: Retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_model_version:
    model_uid: model-bge-managed
    version: v2
    description: Quantized production release
    storage_type: COS
    storage_uri: cos://model-bucket/bge/v2/
    use_custom_storage: true
"""
RETURN = r"""
model_version: {description: Effective immutable model version., type: dict, returned: always}
version_id: {description: DLC version ID., type: str, returned: when available}
"""

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def _model(cls, value):
    item = cls()
    item.from_json_string(json.dumps(value))
    return item


def list_request(models, p, page=1):
    request = models.ListModelVersionsRequest()
    request.ModelUid, request.Page, request.PageSize = p["model_uid"], page, 200
    return request


def find(module, client, models, p):
    page, matches = 1, []
    while True:
        response = module.sdk_call(client.ListModelVersions, list_request(models, p, page))
        items = response.Items or []
        matches.extend(x._serialize(allow_none=True) for x in items if x.Version == p["version"])
        if not items or page >= int(response.TotalPages or 1):
            break
        page += 1
    if len(matches) > 1:
        module.fail_json(msg="Multiple DLC model versions matched the exact label", model_uid=p["model_uid"], version=p["version"])
    return matches[0] if matches else None


def desired(p, current=None):
    result = dict(current or {})
    result["Version"] = p["version"]
    for source, target in (("description", "Description"), ("storage_uri", "StorageUri"), ("use_custom_storage", "UseCustomStorage")):
        if p.get(source) is not None:
            result[target] = p[source]
    return result


def conflict(p, current):
    target, changes = desired(p, current), {}
    for source, key in (("description", "Description"), ("storage_uri", "StorageUri"), ("use_custom_storage", "UseCustomStorage")):
        if p.get(source) is not None and current.get(key) != target.get(key):
            changes[key] = (current.get(key), target.get(key))
    return changes


def create_request(models, p):
    request = models.CreateModelVersionRequest()
    request.ModelUid, request.ModelVersion = p["model_uid"], p["version"]
    for source, target in (
        ("description", "Description"),
        ("storage_uri", "StorageUri"),
        ("use_custom_storage", "UseCustomStorage"),
        ("storage_type", "StorageType"),
    ):
        if p.get(source) is not None:
            setattr(request, target, p[source])
    if p.get("goosefs_config") is not None:
        request.GooseFSConfig = _model(models.GooseFSConfig, p["goosefs_config"])
    return request


def wait_version(module, client, models, p):
    def poll():
        return "ready" if find(module, client, models, p) else "absent"

    wait_for_state(module, poll, ["ready"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    spec = {
        "model_uid": {"required": True},
        "version": {"required": True},
        "description": {},
        "storage_uri": {},
        "use_custom_storage": {"type": "bool"},
        "storage_type": {"choices": ["LOCAL", "CFS", "COS", "CFSTurbo", "GooseFS"]},
        "goosefs_config": {"type": "dict"},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 5},
        "waiter_timeout": {"type": "int", "default": 300},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if p.get("storage_type") in ("CFS", "COS", "CFSTurbo") and not p.get("storage_uri"):
        module.fail_json(msg="storage_uri is required for CFS, COS and CFSTurbo versions")
    if p.get("storage_type") == "LOCAL" and p.get("goosefs_config") is not None:
        module.fail_json(msg="goosefs_config cannot be used with LOCAL storage")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if current:
            changes = conflict(p, current)
            if changes:
                module.fail_json(
                    msg="DLC model versions are immutable and the requested label already has conflicting metadata",
                    model_version=current,
                    immutable_drift=changes,
                )
            module.exit_json(changed=False, model_version=current, version_id=current.get("VersionId"))
        target, diff_value, version_id = desired(p), maybe_diff(module, None, desired(p)), None
        if not module.check_mode:
            response = module.sdk_call(client.CreateModelVersion, create_request(models, p))
            version_id = response.VersionId
            if p["wait"]:
                wait_version(module, client, models, p)
            current = find(module, client, models, p)
        module.exit_json(
            changed=True,
            **(diff_value or {}),
            model_version=current if not module.check_mode else target,
            version_id=(current or {}).get("VersionId") or version_id,
        )
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
