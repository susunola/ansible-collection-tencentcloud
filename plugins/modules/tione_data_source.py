#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tione_data_source
short_description: Manage Tencent Cloud TIONE data sources
version_added: "0.14.0"
description:
  - Creates immutable TIONE storage data sources and deletes them by stable ID.
  - Existing creation-field drift is reported because TIONE exposes no data-source update API.
  - Name lookup rejects ambiguity; destructive operations require both a stable ID and an explicit guard.
options:
  state:
    description:
      - Desired data-source presence.
    type: str
    choices: [present, absent]
    default: present
  name:
    description:
      - Exact data-source name; required for creation.
    type: str
  data_source_id:
    description:
      - Stable data-source ID; optional for lookup and required for deletion.
    type: str
  project_id:
    description:
      - Optional TI workspace ID.
    type: str
  source_type:
    description:
      - Storage data-source type; required for creation.
    type: str
  permission:
    description:
      - Data-source access permission; required for creation.
    type: str
    choices: [RW, RO]
  storage_id:
    description:
      - Storage instance ID; required for creation.
    type: str
  mount_config:
    description:
      - MountConfigureInfo-compatible mount configuration.
    type: dict
  tags:
    description:
      - Tag-compatible resource tags.
    type: list
    elements: dict
  allow_delete:
    description:
      - Explicit destructive-operation guard.
    type: bool
    default: false
  wait:
    description:
      - Wait for creation visibility or deletion disappearance.
    type: bool
    default: true
  waiter_delay:
    description:
      - Seconds between visibility checks.
    type: int
    default: 5
  waiter_timeout:
    description:
      - Overall visibility timeout.
    type: int
    default: 300

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
attributes:
  check_mode:
    description:
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  diff_mode:
    description:
      - Returns the difference between the observed and the requested state
        when the task runs with C(--diff).
    support: full
  idempotent:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
seealso:
  - module: susunola.tencentcloud.tione_data_source_info
    description: Gather Tencent Cloud TIONE data sources.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tione_data_source:
    name: shared-training-cfs
    source_type: CFS
    permission: RW
    storage_id: cfs-xxxxxxxx
    mount_config:
      WorkDir: /training
    tags:
      - {TagKey: environment, TagValue: production}

- susunola.tencentcloud.tione_data_source:
    state: absent
    data_source_id: datasource-xxxxxxxx
    allow_delete: true
"""
RETURN = r"""
data_source:
  description:
    - Effective TIONE data-source metadata.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    Id: datasource-8b0a1c2d
    Name: shared-training-cfs
    Type: CFS
    Permission: RW
    StorageId: cfs-123
    MountConfigure:
      WorkDir: /training
      MountPath: /data
    Tags:
      - TagKey: environment
        TagValue: production
data_source_id:
  description:
    - Stable data-source ID.
  returned: when available
  type: str
  sample: datasource-8b0a1c2d
"""

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.tione.v20211111 import models, tione_client

    return models, tione_client


def _model(cls, value):
    item = cls()
    item.from_json_string(json.dumps(value))
    return item


def normalize(value):
    result = dict(value or {})
    if result.get("Tags") is not None:
        result["Tags"] = sorted(result["Tags"], key=lambda x: json.dumps(x, sort_keys=True))
    return result


def get_request(models, p):
    request = models.DescribeDataSourceRequest()
    request.Id = p["data_source_id"]
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    return request


def list_request(models, p, offset):
    request = models.DescribeDataSourcesRequest()
    request.Offset, request.Limit = offset, 200
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    item = models.Filter()
    item.Name, item.Values = "Name", [p["name"]]
    request.Filters = [item]
    return request


def find(module, client, models, p):
    if p.get("data_source_id"):
        try:
            response = module.sdk_call(client.DescribeDataSource, get_request(models, p))
        except Exception as exc:
            if is_not_found(exc):
                return None
            raise
        return normalize(response.DataSourceInfo._serialize(allow_none=True)) if response.DataSourceInfo else None
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeDataSources, list_request(models, p, offset))
        items = response.DataSourceInfos or []
        matches.extend(normalize(item._serialize(allow_none=True)) for item in items if item.Name == p["name"])
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple TIONE data sources matched the exact name", name=p["name"])
    return matches[0] if matches else None


def desired(p, current=None):
    result = dict(current or {})
    result["Name"] = p.get("name") or result.get("Name")
    for source, target in (
        ("source_type", "Type"),
        ("permission", "Permission"),
        ("storage_id", "StorageId"),
        ("mount_config", "MountConfigure"),
        ("tags", "Tags"),
    ):
        if p.get(source) is not None:
            result[target] = p[source]
    return normalize(result)


def conflict(p, current):
    target, changes = desired(p, current), {}
    for source, key in (
        ("name", "Name"),
        ("source_type", "Type"),
        ("permission", "Permission"),
        ("storage_id", "StorageId"),
        ("mount_config", "MountConfigure"),
        ("tags", "Tags"),
    ):
        if p.get(source) is not None and current.get(key) != target.get(key):
            changes[key] = (current.get(key), target.get(key))
    return changes


def create_request(models, p):
    request = models.CreateDataSourceRequest()
    request.Name, request.Type, request.Permission, request.StorageId = p["name"], p["source_type"], p["permission"], p["storage_id"]
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    if p.get("mount_config") is not None:
        request.MountConfigure = _model(models.MountConfigureInfo, p["mount_config"])
    if p.get("tags") is not None:
        request.Tags = [_model(models.Tag, item) for item in p["tags"]]
    return request


def delete_request(models, p):
    request = models.DeleteDataSourceRequest()
    request.Id = p["data_source_id"]
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    return request


def wait_presence(module, client, models, p, present):
    def poll():
        return "present" if find(module, client, models, p) else "absent"

    wait_for_state(module, poll, ["present" if present else "absent"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "name": {},
        "data_source_id": {},
        "project_id": {},
        "source_type": {},
        "permission": {"choices": ["RW", "RO"]},
        "storage_id": {},
        "mount_config": {"type": "dict"},
        "tags": {"type": "list", "elements": "dict"},
        "allow_delete": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 5},
        "waiter_timeout": {"type": "int", "default": 300},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if p["state"] == "present" and not (p.get("name") or p.get("data_source_id")):
        module.fail_json(msg="name or data_source_id is required when state=present")
    if p["state"] == "absent" and not p.get("data_source_id"):
        module.fail_json(msg="data_source_id is required for safe deletion")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TioneClient, "tione.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, data_source=None, data_source_id=p["data_source_id"])
            if not p["allow_delete"]:
                module.fail_json(msg="allow_delete=true is required to delete a TIONE data source", data_source=current)
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteDataSource, delete_request(models, p))
                if p["wait"]:
                    wait_presence(module, client, models, p, False)
            module.exit_json(changed=True, **(diff_value or {}), data_source=None, data_source_id=p["data_source_id"])
        if current:
            changes = conflict(p, current)
            if changes:
                module.fail_json(
                    msg="TIONE data sources expose no update API and the existing data source has immutable drift", data_source=current, immutable_drift=changes
                )
            module.exit_json(changed=False, data_source=current, data_source_id=current.get("Id"))
        if p.get("data_source_id"):
            module.fail_json(msg="the requested TIONE data_source_id does not exist; omit it to create by name", data_source_id=p["data_source_id"])
        missing = [key for key in ("name", "source_type", "permission", "storage_id") if not p.get(key)]
        if missing:
            module.fail_json(msg="creation parameters are required for a TIONE data source", missing=missing)
        target, diff_value, data_source_id = desired(p), maybe_diff(module, None, desired(p)), None
        if not module.check_mode:
            response = module.sdk_call(client.CreateDataSource, create_request(models, p))
            data_source_id = response.Id
            lookup = dict(p, data_source_id=data_source_id)
            if p["wait"]:
                wait_presence(module, client, models, lookup, True)
            current = find(module, client, models, lookup)
        module.exit_json(
            changed=True,
            **(diff_value or {}),
            data_source=current if not module.check_mode else target,
            data_source_id=(current or {}).get("Id") or data_source_id,
        )
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
