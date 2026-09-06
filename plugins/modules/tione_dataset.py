#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tione_dataset
short_description: Manage Tencent Cloud TIONE datasets
version_added: "0.14.0"
description:
  - Creates immutable TIONE dataset definitions and safely deletes an exact dataset ID.
  - Existing creation-field drift is reported because TIONE exposes no dataset update API.
  - Deletion deliberately requires C(dataset_id); dataset names aggregate versions and are not a safe destructive identity.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired dataset presence.}
  name: {type: str, description: Exact dataset name; required for creation.}
  dataset_id: {type: str, description: Stable dataset ID; optional for lookup and required for deletion.}
  project_id: {type: str, description: Optional TI workspace ID.}
  dataset_type: {type: str, choices: [TYPE_DATASET_IMAGE, TYPE_DATASET_LLM, TYPE_DATASET_TABLE, TYPE_DATASET_OTHER], description: Dataset type; required for creation.}
  storage_data_path: {type: dict, description: CosPathInfo-compatible source path.}
  storage_label_path: {type: dict, description: CosPathInfo-compatible label path.}
  dataset_tags: {type: list, elements: dict, description: Tag-compatible dataset tags.}
  annotation_status: {type: str, choices: [STATUS_NON_ANNOTATED, STATUS_ANNOTATED], description: Initial annotation status.}
  annotation_type: {type: str, choices: [ANNOTATION_TYPE_CLASSIFICATION, ANNOTATION_TYPE_DETECTION, ANNOTATION_TYPE_SEGMENTATION, ANNOTATION_TYPE_TRACKING, ANNOTATION_TYPE_OCR], description: Initial annotation type.}
  annotation_format: {type: str, choices: [ANNOTATION_FORMAT_TI, ANNOTATION_FORMAT_PASCAL, ANNOTATION_FORMAT_COCO, ANNOTATION_FORMAT_FILE], description: Initial annotation format.}
  schema_infos: {type: list, elements: dict, description: SchemaInfo-compatible table headers.}
  is_schema_existed: {type: bool, description: Whether source data contains a header.}
  content_type: {type: str, choices: [TYPE_TEXT_LINE, TYPE_TEXT_FILE], description: Text import granularity.}
  dataset_scene: {type: str, choices: [LLM, CV, STRUCTURE, OTHER], description: Dataset modeling category.}
  scene_tags: {type: list, elements: str, description: Dataset scene tags.}
  cfs_config: {type: dict, description: CFSConfig-compatible configuration for LLM datasets.}
  delete_label_files: {type: bool, default: false, description: Also delete COS label files during explicit deletion.}
  allow_delete: {type: bool, default: false, description: Explicit destructive-operation guard.}
  wait: {type: bool, default: true, description: Wait for creation visibility or deletion disappearance.}
  waiter_delay: {type: int, default: 5, description: Seconds between visibility checks.}
  waiter_timeout: {type: int, default: 300, description: Overall visibility timeout.}
  retries: {type: int, default: 5, description: Retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tione_dataset:
    name: customer-support-sft
    dataset_type: TYPE_DATASET_LLM
    dataset_scene: LLM
    storage_data_path:
      Bucket: ml-datasets-1250000000
      Region: ap-guangzhou
      Paths: [/support/sft/]

- susunola.tencentcloud.tione_dataset:
    state: absent
    dataset_id: ds-xxxxxxxx
    allow_delete: true
"""
RETURN = r"""
dataset: {description: Effective TIONE dataset group metadata., type: dict, returned: always}
dataset_id: {description: Stable dataset ID., type: str, returned: when available}
"""

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state

FIELDS = {
    "dataset_type": ("DatasetType", None),
    "storage_data_path": ("StorageDataPath", "CosPathInfo"),
    "storage_label_path": ("StorageLabelPath", "CosPathInfo"),
    "dataset_tags": ("DatasetTags", "Tag"),
    "annotation_status": ("AnnotationStatus", None),
    "annotation_type": ("AnnotationType", None),
    "annotation_format": ("AnnotationFormat", None),
    "schema_infos": ("SchemaInfos", "SchemaInfo"),
    "is_schema_existed": ("IsSchemaExisted", None),
    "content_type": ("ContentType", None),
    "dataset_scene": ("DatasetScene", None),
    "scene_tags": ("SceneTags", None),
    "cfs_config": ("CFSConfig", "CFSConfig"),
}


def _load():
    from tencentcloud.tione.v20211111 import models, tione_client

    return models, tione_client


def _model(cls, value):
    item = cls()
    item.from_json_string(json.dumps(value))
    return item


def normalize(value):
    result = dict(value or {})
    if result.get("DatasetTags") is not None:
        result["DatasetTags"] = sorted(result["DatasetTags"], key=lambda x: json.dumps(x, sort_keys=True))
    if result.get("SceneTags") is not None:
        result["SceneTags"] = sorted(result["SceneTags"])
    return result


def list_request(models, p, offset):
    request = models.DescribeDatasetsRequest()
    request.Offset, request.Limit = offset, 200
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    if p.get("dataset_id"):
        request.DatasetIds = [p["dataset_id"]]
    elif p.get("name"):
        item = models.Filter()
        item.Name, item.Values = "DatasetName", [p["name"]]
        request.Filters = [item]
    return request


def find(module, client, models, p):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeDatasets, list_request(models, p, offset))
        items = response.DatasetGroups or []
        for item in items:
            value = normalize(item._serialize(allow_none=True))
            if p.get("dataset_id") and value.get("DatasetId") == p["dataset_id"]:
                matches.append(value)
            elif not p.get("dataset_id") and value.get("DatasetName") == p.get("name"):
                matches.append(value)
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple TIONE dataset groups matched the requested identity", name=p.get("name"), dataset_id=p.get("dataset_id"))
    return matches[0] if matches else None


def desired(p, current=None):
    result = dict(current or {})
    result["DatasetName"] = p.get("name") or result.get("DatasetName")
    for source, (target, _) in FIELDS.items():
        if p.get(source) is not None:
            result[target] = p[source]
    return normalize(result)


def conflict(p, current):
    target, changes = desired(p, current), {}
    for source, (key, _) in FIELDS.items():
        if source == "schema_infos":
            continue
        if p.get(source) is not None and current.get(key) != target.get(key):
            changes[key] = (current.get(key), target.get(key))
    if p.get("name") is not None and current.get("DatasetName") != p["name"]:
        changes["DatasetName"] = (current.get("DatasetName"), p["name"])
    return changes


def create_request(models, p):
    request = models.CreateDatasetRequest()
    request.DatasetName = p["name"]
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    for source, (target, cls_name) in FIELDS.items():
        value = p.get(source)
        if value is None:
            continue
        if cls_name and isinstance(value, list):
            value = [_model(getattr(models, cls_name), item) for item in value]
        elif cls_name:
            value = _model(getattr(models, cls_name), value)
        setattr(request, target, value)
    return request


def delete_request(models, p):
    request = models.DeleteDatasetRequest()
    request.DatasetId, request.DeleteLabelEnable = p["dataset_id"], p["delete_label_files"]
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
        "dataset_id": {},
        "project_id": {},
        "dataset_type": {"choices": ["TYPE_DATASET_IMAGE", "TYPE_DATASET_LLM", "TYPE_DATASET_TABLE", "TYPE_DATASET_OTHER"]},
        "storage_data_path": {"type": "dict"},
        "storage_label_path": {"type": "dict"},
        "dataset_tags": {"type": "list", "elements": "dict"},
        "annotation_status": {"choices": ["STATUS_NON_ANNOTATED", "STATUS_ANNOTATED"]},
        "annotation_type": {
            "choices": [
                "ANNOTATION_TYPE_CLASSIFICATION",
                "ANNOTATION_TYPE_DETECTION",
                "ANNOTATION_TYPE_SEGMENTATION",
                "ANNOTATION_TYPE_TRACKING",
                "ANNOTATION_TYPE_OCR",
            ]
        },
        "annotation_format": {"choices": ["ANNOTATION_FORMAT_TI", "ANNOTATION_FORMAT_PASCAL", "ANNOTATION_FORMAT_COCO", "ANNOTATION_FORMAT_FILE"]},
        "schema_infos": {"type": "list", "elements": "dict"},
        "is_schema_existed": {"type": "bool"},
        "content_type": {"choices": ["TYPE_TEXT_LINE", "TYPE_TEXT_FILE"]},
        "dataset_scene": {"choices": ["LLM", "CV", "STRUCTURE", "OTHER"]},
        "scene_tags": {"type": "list", "elements": "str"},
        "cfs_config": {"type": "dict"},
        "delete_label_files": {"type": "bool", "default": False},
        "allow_delete": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 5},
        "waiter_timeout": {"type": "int", "default": 300},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if p["state"] == "present" and not p.get("name"):
        module.fail_json(msg="name is required when state=present")
    if p["state"] == "absent" and not p.get("dataset_id"):
        module.fail_json(msg="dataset_id is required for safe deletion")
    if p.get("cfs_config") is not None and p.get("dataset_scene") not in (None, "LLM"):
        module.fail_json(msg="cfs_config is only valid for the LLM dataset scene")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TioneClient, "tione.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, dataset=None, dataset_id=p["dataset_id"])
            if not p["allow_delete"]:
                module.fail_json(msg="allow_delete=true is required to delete a TIONE dataset", dataset=current)
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteDataset, delete_request(models, p))
                if p["wait"]:
                    wait_presence(module, client, models, p, False)
            module.exit_json(changed=True, **(diff_value or {}), dataset=None, dataset_id=p["dataset_id"])
        if current:
            changes = conflict(p, current)
            if changes:
                module.fail_json(
                    msg="TIONE datasets expose no update API and the existing dataset has immutable drift", dataset=current, immutable_drift=changes
                )
            module.exit_json(changed=False, dataset=current, dataset_id=current.get("DatasetId"))
        if p.get("dataset_id"):
            module.fail_json(msg="the requested TIONE dataset_id does not exist; omit dataset_id to create by name", dataset_id=p["dataset_id"])
        if not p.get("dataset_type"):
            module.fail_json(msg="dataset_type is required when creating a TIONE dataset")
        target, diff_value, dataset_id = desired(p), maybe_diff(module, None, desired(p)), None
        if not module.check_mode:
            response = module.sdk_call(client.CreateDataset, create_request(models, p))
            dataset_id = response.DatasetId
            lookup = dict(p, dataset_id=dataset_id)
            if p["wait"]:
                wait_presence(module, client, models, lookup, True)
            current = find(module, client, models, lookup)
        module.exit_json(
            changed=True, **(diff_value or {}), dataset=current if not module.check_mode else target, dataset_id=(current or {}).get("DatasetId") or dataset_id
        )
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
