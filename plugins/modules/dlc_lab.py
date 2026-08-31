#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: dlc_lab
short_description: Manage Tencent Cloud DLC data laboratories
version_added: "0.14.0"
description:
  - Creates, updates and deletes DLC data laboratory workspaces.
  - Resource configuration, catalog mounts and advanced cluster options are immutable after creation.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired lifecycle state.}
  name: {type: str, required: true, description: Exact laboratory name and immutable identity.}
  resource_partition_id: {type: str, description: Resource partition ID.}
  queue: {type: str, description: Queue name.}
  lab_image: {type: str, description: Required development-tool image.}
  image: {type: str, description: Optional explicit Ray cluster image.}
  description: {type: str, description: Laboratory description.}
  image_pull_policy: {type: str, choices: [Always, IfNotPresent, Never], description: Ray image pull policy.}
  lab_image_pull_policy: {type: str, choices: [Always, IfNotPresent, Never], description: Lab sidecar image pull policy.}
  image_pull_type: {type: str, choices: [BuiltIn, Custom, CustomCcr], description: Ray image source type.}
  lab_image_pull_type: {type: str, choices: [BuiltIn, Custom, CustomCcr], description: Lab image source type.}
  resource_config_id: {type: str, description: Managed resource-configuration ID.}
  group_id: {type: str, description: Compute group ID.}
  priority: {type: int, description: Scheduling priority from 1 to 9.}
  enable_token: {type: bool, description: Enable access-token authentication.}
  example_id: {type: str, description: Example template ID.}
  code_archive_url: {type: str, description: Example or project code archive URL.}
  tags:
    type: list
    elements: dict
    description: Exact Tencent Cloud tag set.
    options:
      key: {type: str, required: true, description: Tag key.}
      value: {type: str, required: true, description: Tag value.}
  persistent_work_dir: {type: dict, description: Persistent workspace directory contract passed to DLC.}
  resource_config: {type: str, description: Creation-time resource configuration JSON.}
  catalog: {type: str, description: Creation-time volume and mount configuration JSON.}
  advanced_options: {type: str, description: Creation-time flattened Ray cluster options JSON.}
  allow_delete: {type: bool, default: false, description: Explicitly authorize laboratory deletion.}
  wait: {type: bool, default: true, description: Wait for lifecycle and field convergence.}
  waiter_delay: {type: int, default: 10, description: Seconds between polls.}
  waiter_timeout: {type: int, default: 1800, description: Overall convergence timeout.}
  retries: {type: int, default: 5, description: Retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.dlc_lab:
    name: analytics-notebook
    resource_partition_id: rp-xxxxxxxx
    queue: default
    lab_image: ccr.ccs.tencentyun.com/dlc/jupyter:latest
    image_pull_type: BuiltIn
    lab_image_pull_type: BuiltIn
    priority: 5
    enable_token: true
    tags:
      - {key: environment, value: production}

- susunola.tencentcloud.dlc_lab:
    name: analytics-notebook
    state: absent
    allow_delete: true
'''
RETURN = r'''
lab:
  description: Effective DLC laboratory metadata.
  type: dict
  returned: always
lab_id:
  description: DLC laboratory ID.
  type: str
  returned: when present
'''

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state

MUTABLE = {
    "resource_partition_id": "ResourcePartitionId", "queue": "Queue", "lab_image": "LabImage", "image": "Image",
    "description": "Description", "image_pull_policy": "ImagePullPolicy", "lab_image_pull_policy": "LabImagePullPolicy",
    "image_pull_type": "ImagePullType", "lab_image_pull_type": "LabImagePullType", "resource_config_id": "ResourceConfigId",
    "group_id": "GroupId", "priority": "Priority", "enable_token": "EnableToken", "example_id": "ExampleId",
    "code_archive_url": "CodeArchiveUrl", "tags": "Tags", "persistent_work_dir": "PersistentWorkDir",
}
IMMUTABLE = {"resource_config": "ResourceConfig", "catalog": "Catalog", "advanced_options": "AdvancedOptions"}


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client
    return models, dlc_client


def list_request(models, page=1):
    request = models.ListLabsRequest(); request.Page, request.PageSize = page, 200; return request


def find(module, client, models, name):
    page, matches = 1, []
    while True:
        response = module.sdk_call(client.ListLabs, list_request(models, page))
        items = response.Items or []
        matches.extend(x._serialize(allow_none=True) for x in items if x.Name == name and (x.Type in (None, "WORKSPACE")))
        if page >= int(response.TotalPages or 1) or not items:
            break
        page += 1
    if len(matches) > 1:
        module.fail_json(msg="Multiple DLC laboratories matched the exact name", name=name)
    return normalize(matches[0]) if matches else None


def _canonical(value):
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    try:
        return json.dumps(json.loads(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError):
        return value


def _tags(value):
    result = []
    for item in value or []:
        key = item.get("TagKey", item.get("key")); val = item.get("TagValue", item.get("value"))
        result.append({"TagKey": key, "TagValue": val})
    return sorted(result, key=lambda x: (x["TagKey"], x["TagValue"]))


def normalize(value):
    result = dict(value or {})
    result["Tags"] = _tags(result.get("Tags"))
    for key in ("ResourceConfig", "Catalog", "AdvancedOptions"):
        if key in result:
            result[key] = _canonical(result[key])
    return result


def request_payload(p, update=False):
    payload = {"Name": p["name"]}
    for source, target in MUTABLE.items():
        if p.get(source) is not None:
            payload[target] = _tags(p[source]) if source == "tags" else p[source]
    if not update:
        for source, target in IMMUTABLE.items():
            if p.get(source) is not None:
                payload[target] = _canonical(p[source])
    return payload


def make_request(models, p, update=False):
    request = models.UpdateLabRequest() if update else models.CreateLabRequest()
    request.from_json_string(json.dumps(request_payload(p, update))); return request


def delete_request(models, lab_id):
    request = models.DeleteLabRequest(); request.Id = lab_id; return request


def desired(p, current=None):
    result = dict(current or {}); result["Name"] = p["name"]
    for source, target in {**MUTABLE, **IMMUTABLE}.items():
        if p.get(source) is not None:
            value = p[source]
            if source == "tags": value = _tags(value)
            if source in IMMUTABLE: value = _canonical(value)
            result[target] = value
    return result


def drift(p, current, fields):
    target, changes = desired(p, current), {}
    for source, key in fields.items():
        if p.get(source) is not None and current.get(key) != target.get(key):
            changes[key] = (current.get(key), target.get(key))
    return changes


def wait_lab(module, client, models, p, absent=False, expected=None):
    def poll():
        current = find(module, client, models, p["name"])
        if absent:
            return "absent" if current is None else "pending"
        if current is None:
            return "absent"
        status = str(current.get("Status") or "").upper()
        if "FAIL" in status or "ERROR" in status:
            module.fail_json(msg="DLC laboratory entered a failed state", lab=current)
        if expected and any(current.get(k) != v for k, v in expected.items()):
            return "pending"
        return "ready"
    wait_for_state(module, poll, ["absent" if absent else "ready"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    tag_options = {"key": {"required": True}, "value": {"required": True}}
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"}, "name": {"required": True},
        "resource_partition_id": {}, "queue": {}, "lab_image": {}, "image": {}, "description": {},
        "image_pull_policy": {"choices": ["Always", "IfNotPresent", "Never"]},
        "lab_image_pull_policy": {"choices": ["Always", "IfNotPresent", "Never"]},
        "image_pull_type": {"choices": ["BuiltIn", "Custom", "CustomCcr"]},
        "lab_image_pull_type": {"choices": ["BuiltIn", "Custom", "CustomCcr"]},
        "resource_config_id": {}, "group_id": {}, "priority": {"type": "int"}, "enable_token": {"type": "bool"},
        "example_id": {}, "code_archive_url": {}, "tags": {"type": "list", "elements": "dict", "options": tag_options},
        "persistent_work_dir": {"type": "dict"}, "resource_config": {}, "catalog": {}, "advanced_options": {},
        "allow_delete": {"type": "bool", "default": False}, "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 10}, "waiter_timeout": {"type": "int", "default": 1800},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True); p = module.params
    if p.get("priority") is not None and not 1 <= p["priority"] <= 9:
        module.fail_json(msg="priority must be between 1 and 9")
    for key in IMMUTABLE:
        if p.get(key) is not None:
            try: json.loads(p[key])
            except (TypeError, ValueError): module.fail_json(msg="%s must be valid JSON" % key)
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["name"])
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, lab=None, lab_id=None)
            if not p["allow_delete"]: module.fail_json(msg="set allow_delete=true to authorize deleting the DLC laboratory", lab=current)
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteLab, delete_request(models, current["Id"]))
                if p["wait"]: wait_lab(module, client, models, p, absent=True)
            module.exit_json(changed=True, **(diff_value or {}), lab=None, lab_id=None)
        if not current:
            required = ("resource_partition_id", "queue", "lab_image")
            missing = [key for key in required if not p.get(key)]
            if missing: module.fail_json(msg="creation parameters are required for a DLC laboratory", missing=missing)
            after, diff_value = desired(p), maybe_diff(module, None, desired(p))
            if not module.check_mode:
                response = module.sdk_call(client.CreateLab, make_request(models, p)); lab_id = response.Id
                if p["wait"]: wait_lab(module, client, models, p, expected={k: v for k, v in after.items() if k != "Name"})
                current = find(module, client, models, p["name"])
            else: lab_id = None
            module.exit_json(changed=True, **(diff_value or {}), lab=current if not module.check_mode else after, lab_id=(current or {}).get("Id") or lab_id)
        immutable_drift = drift(p, current, IMMUTABLE)
        if immutable_drift: module.fail_json(msg="DLC laboratory resource configuration, catalog and advanced options are immutable", immutable_drift=immutable_drift)
        changes = drift(p, current, MUTABLE)
        if not changes: module.exit_json(changed=False, lab=current, lab_id=current.get("Id"))
        after, diff_value = desired(p, current), maybe_diff(module, current, desired(p, current))
        if not module.check_mode:
            module.sdk_call(client.UpdateLab, make_request(models, p, update=True))
            if p["wait"]: wait_lab(module, client, models, p, expected={k: v[1] for k, v in changes.items()})
            current = find(module, client, models, p["name"])
        module.exit_json(changed=True, **(diff_value or {}), lab=current if not module.check_mode else after, lab_id=current.get("Id"))
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
