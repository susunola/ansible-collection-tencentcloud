#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tione_notebook
short_description: Manage Tencent Cloud TIONE notebooks
version_added: "0.14.0"
description:
  - Reconciles TIONE notebook configuration and operational state across creation, update, start, stop and deletion.
  - Mutable configuration drift is applied while stopped and the requested running state is restored afterwards.
  - Immutable network, billing and storage-source drift is reported explicitly instead of silently replacing persistent workspaces.
options:
  state: {type: str, choices: [running, stopped, absent], default: running, description: Desired notebook state.}
  name: {type: str, description: Exact notebook name; required for creation.}
  notebook_id: {type: str, description: Stable notebook ID; optional for lookup and required for deletion.}
  project_id: {type: str, description: Optional TI workspace ID used during discovery.}
  charge_type: {type: str, choices: [PREPAID, POSTPAID_BY_HOUR], description: Immutable billing mode; required for creation.}
  resource_conf: {type: dict, description: ResourceConf-compatible compute configuration.}
  log_enable: {type: bool, description: Enable log reporting.}
  root_access: {type: bool, description: Enable root access.}
  auto_stopping: {type: bool, description: Enable automatic stopping.}
  direct_internet_access: {type: bool, description: Enable direct internet access.}
  resource_group_id: {type: str, description: Prepaid resource-group ID.}
  vpc_id: {type: str, description: Immutable VPC ID.}
  subnet_id: {type: str, description: Immutable subnet ID.}
  volume_source_type: {type: str, choices: [FREE, CLOUD_PREMIUM, CLOUD_SSD, CFS, CFS_TURBO, GooseFSx], description: Immutable storage source type.}
  volume_size_gb: {type: int, description: Mutable storage volume size in GB.}
  volume_source_cfs: {type: dict, description: Immutable CFSConfig-compatible storage configuration.}
  volume_source_goosefs: {type: dict, description: Immutable GooseFS-compatible storage configuration.}
  log_config: {type: dict, description: LogConfig-compatible log destination.}
  lifecycle_script_id: {type: str, description: Lifecycle script ID.}
  default_code_repo_id: {type: str, description: Default code repository ID.}
  additional_code_repo_ids: {type: list, elements: str, description: 'Additional code repository IDs, at most three.'}
  automatic_stop_time: {type: int, description: Automatic stop interval in hours.}
  tags: {type: list, elements: dict, description: Tag-compatible notebook tags.}
  data_configs: {type: list, elements: dict, description: DataConfig-compatible storage mounts.}
  image_info: {type: dict, description: ImageInfo-compatible image selection.}
  image_type: {type: str, choices: [SYSTEM, TCR, CCR], description: Notebook image type.}
  ssh_config: {type: dict, description: SSHConfig-compatible SSH configuration.}
  description: {type: str, description: Notebook description.}
  allow_delete: {type: bool, default: false, description: Explicit destructive-operation guard.}
  wait: {type: bool, default: true, description: Wait for state convergence.}
  waiter_delay: {type: int, default: 10, description: Seconds between state checks.}
  waiter_timeout: {type: int, default: 1800, description: Overall convergence timeout.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tione_notebook:
    name: llm-finetuning
    state: running
    charge_type: POSTPAID_BY_HOUR
    resource_conf: {Cpu: 8, Memory: 32}
    volume_source_type: CLOUD_PREMIUM
    volume_size_gb: 100
    auto_stopping: true
    automatic_stop_time: 4
    direct_internet_access: false

- susunola.tencentcloud.tione_notebook:
    state: absent
    notebook_id: nb-xxxxxxxx
    allow_delete: true
"""
RETURN = r"""
notebook: {description: Effective TIONE notebook detail., type: dict, returned: always}
notebook_id: {description: Stable notebook ID., type: str, returned: when available}
"""

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state

FIELDS = {
    "name": ("Name", None),
    "charge_type": ("ChargeType", None),
    "resource_conf": ("ResourceConf", "ResourceConf"),
    "log_enable": ("LogEnable", None),
    "root_access": ("RootAccess", None),
    "auto_stopping": ("AutoStopping", None),
    "direct_internet_access": ("DirectInternetAccess", None),
    "resource_group_id": ("ResourceGroupId", None),
    "vpc_id": ("VpcId", None),
    "subnet_id": ("SubnetId", None),
    "volume_source_type": ("VolumeSourceType", None),
    "volume_size_gb": ("VolumeSizeInGB", None),
    "volume_source_cfs": ("VolumeSourceCFS", "CFSConfig"),
    "volume_source_goosefs": ("VolumeSourceGooseFS", "GooseFS"),
    "log_config": ("LogConfig", "LogConfig"),
    "lifecycle_script_id": ("LifecycleScriptId", None),
    "default_code_repo_id": ("DefaultCodeRepoId", None),
    "additional_code_repo_ids": ("AdditionalCodeRepoIds", None),
    "automatic_stop_time": ("AutomaticStopTime", None),
    "tags": ("Tags", "Tag"),
    "data_configs": ("DataConfigs", "DataConfig"),
    "image_info": ("ImageInfo", "ImageInfo"),
    "image_type": ("ImageType", None),
    "ssh_config": ("SSHConfig", "SSHConfig"),
    "description": ("Description", None),
}
IMMUTABLE = {"ChargeType", "VpcId", "SubnetId", "VolumeSourceType", "VolumeSourceCFS", "VolumeSourceGooseFS"}


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


def detail_request(models, notebook_id, project_id=None):
    request = models.DescribeNotebookRequest()
    request.Id = notebook_id
    if project_id is not None:
        request.TiProjectId = project_id
    return request


def list_request(models, p, offset):
    request = models.DescribeNotebooksRequest()
    request.Offset, request.Limit = offset, 200
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    item = models.Filter()
    item.Name, item.Values = "Name", [p["name"]]
    request.Filters = [item]
    return request


def get(module, client, models, notebook_id, project_id=None):
    try:
        response = module.sdk_call(client.DescribeNotebook, detail_request(models, notebook_id, project_id))
    except Exception as exc:
        if is_not_found(exc):
            return None
        raise
    return normalize(response.NotebookDetail._serialize(allow_none=True)) if response.NotebookDetail else None


def find(module, client, models, p):
    if p.get("notebook_id"):
        return get(module, client, models, p["notebook_id"], p.get("project_id"))
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeNotebooks, list_request(models, p, offset))
        items = response.NotebookSet or []
        matches.extend(item.Id for item in items if item.Name == p["name"])
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple TIONE notebooks matched the exact name", name=p["name"])
    return get(module, client, models, matches[0], p.get("project_id")) if matches else None


def desired(p, current=None):
    result = dict(current or {})
    for source, (target, _) in FIELDS.items():
        if p.get(source) is not None:
            result[target] = p[source]
    return normalize(result)


def drift(p, current):
    target, mutable, immutable = desired(p, current), {}, {}
    for source, (key, _) in FIELDS.items():
        if p.get(source) is not None and current.get(key) != target.get(key):
            (immutable if key in IMMUTABLE else mutable)[key] = (current.get(key), target.get(key))
    return mutable, immutable


def assign(models, request, key, value, cls_name):
    if cls_name and isinstance(value, list):
        value = [_model(getattr(models, cls_name), item) for item in value]
    elif cls_name and value is not None:
        value = _model(getattr(models, cls_name), value)
    setattr(request, key, value)


def create_request(models, p):
    request = models.CreateNotebookRequest()
    for source, (key, cls_name) in FIELDS.items():
        if p.get(source) is not None:
            assign(models, request, key, p[source], cls_name)
    return request


def modify_request(models, notebook_id, p):
    request = models.ModifyNotebookRequest()
    request.Id = notebook_id
    for source, (key, cls_name) in FIELDS.items():
        if key == "VolumeSourceGooseFS":
            continue
        if p.get(source) is not None:
            assign(models, request, key, p[source], cls_name)
    return request


def id_request(cls, notebook_id):
    request = cls()
    request.Id = notebook_id
    return request


def status(value):
    return str((value or {}).get("Status") or "").lower()


def wait_status(module, client, models, p, expected):
    def poll():
        current = get(module, client, models, p["notebook_id"], p.get("project_id"))
        if current is None:
            return "absent"
        actual = status(current)
        if actual in ("failed", "submitfailed"):
            module.fail_json(msg="TIONE notebook entered a failed state", notebook=current)
        return actual

    wait_for_state(module, poll, [expected], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def converge_stopped(module, client, models, p, current):
    actual = status(current)
    if actual == "stopped":
        return current
    if actual in ("failed", "submitfailed"):
        module.fail_json(msg="TIONE notebook is in a failed state", notebook=current)
    if actual in ("starting", "stopping"):
        if not p["wait"]:
            module.fail_json(msg="TIONE notebook is transitioning; enable wait before configuration or deletion", notebook=current)
        wait_status(module, client, models, p, "running" if actual == "starting" else "stopped")
        current = get(module, client, models, p["notebook_id"], p.get("project_id"))
        actual = status(current)
    if actual == "running":
        module.sdk_call(client.StopNotebook, id_request(models.StopNotebookRequest, p["notebook_id"]))
        if p["wait"]:
            wait_status(module, client, models, p, "stopped")
        current = get(module, client, models, p["notebook_id"], p.get("project_id"))
    elif actual != "stopped":
        module.fail_json(msg="TIONE notebook returned an unsupported operational state", status=current.get("Status"), notebook=current)
    return current


def run_module():
    spec = {"state": {"choices": ["running", "stopped", "absent"], "default": "running"}, "notebook_id": {}, "project_id": {}}
    for source in FIELDS:
        spec[source] = {}
    spec.update(
        {
            "charge_type": {"choices": ["PREPAID", "POSTPAID_BY_HOUR"]},
            "resource_conf": {"type": "dict"},
            "log_enable": {"type": "bool"},
            "root_access": {"type": "bool"},
            "auto_stopping": {"type": "bool"},
            "direct_internet_access": {"type": "bool"},
            "volume_source_type": {"choices": ["FREE", "CLOUD_PREMIUM", "CLOUD_SSD", "CFS", "CFS_TURBO", "GooseFSx"]},
            "volume_size_gb": {"type": "int"},
            "volume_source_cfs": {"type": "dict"},
            "volume_source_goosefs": {"type": "dict"},
            "log_config": {"type": "dict"},
            "additional_code_repo_ids": {"type": "list", "elements": "str"},
            "automatic_stop_time": {"type": "int"},
            "tags": {"type": "list", "elements": "dict"},
            "data_configs": {"type": "list", "elements": "dict"},
            "image_info": {"type": "dict"},
            "image_type": {"choices": ["SYSTEM", "TCR", "CCR"]},
            "ssh_config": {"type": "dict"},
            "allow_delete": {"type": "bool", "default": False},
            "wait": {"type": "bool", "default": True},
            "waiter_delay": {"type": "int", "default": 10},
            "waiter_timeout": {"type": "int", "default": 1800},
        }
    )
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if p.get("additional_code_repo_ids") is not None and len(p["additional_code_repo_ids"]) > 3:
        module.fail_json(msg="additional_code_repo_ids accepts at most three repositories")
    if p["state"] == "absent" and not p.get("notebook_id"):
        module.fail_json(msg="notebook_id is required for safe deletion")
    if p["state"] != "absent" and not (p.get("name") or p.get("notebook_id")):
        module.fail_json(msg="name or notebook_id is required")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TioneClient, "tione.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, notebook=None, notebook_id=p["notebook_id"])
            if not p["allow_delete"]:
                module.fail_json(msg="allow_delete=true is required to delete a TIONE notebook", notebook=current)
            if status(current) != "stopped" and not p["wait"]:
                module.fail_json(msg="wait=true is required to stop a TIONE notebook before deletion", notebook=current)
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                current = converge_stopped(module, client, models, p, current)
                module.sdk_call(client.DeleteNotebook, id_request(models.DeleteNotebookRequest, p["notebook_id"]))
                if p["wait"]:
                    wait_status(module, client, models, p, "absent")
            module.exit_json(changed=True, **(diff_value or {}), notebook=None, notebook_id=p["notebook_id"])
        if not current:
            if p.get("notebook_id"):
                module.fail_json(msg="the requested TIONE notebook_id does not exist; omit it to create by name", notebook_id=p["notebook_id"])
            missing = [key for key in ("name", "charge_type", "resource_conf") if p.get(key) is None]
            if missing:
                module.fail_json(msg="creation parameters are required for a TIONE notebook", missing=missing)
            target = desired(p)
            target["Status"] = p["state"].capitalize()
            diff_value = maybe_diff(module, None, target)
            notebook_id = None
            if not module.check_mode:
                response = module.sdk_call(client.CreateNotebook, create_request(models, p))
                notebook_id = response.Id
                p = dict(p, notebook_id=notebook_id)
                if p["wait"]:
                    wait_status(module, client, models, p, "running")
                current = get(module, client, models, notebook_id, p.get("project_id"))
                if p["state"] == "stopped":
                    current = converge_stopped(module, client, models, p, current)
            module.exit_json(
                changed=True, **(diff_value or {}), notebook=current if not module.check_mode else target, notebook_id=(current or {}).get("Id") or notebook_id
            )
        p = dict(p, notebook_id=current["Id"])
        mutable, immutable = drift(p, current)
        if immutable:
            module.fail_json(msg="TIONE notebook immutable configuration drift requires explicit replacement", notebook=current, immutable_drift=immutable)
        actual = status(current)
        needs_state = actual != p["state"]
        if not mutable and not needs_state:
            module.exit_json(changed=False, notebook=current, notebook_id=current["Id"])
        target = desired(p, current)
        target["Status"] = p["state"].capitalize()
        diff_value = maybe_diff(module, current, target)
        if not module.check_mode:
            if mutable:
                if status(current) != "stopped" and not p["wait"]:
                    module.fail_json(msg="wait=true is required to stop a TIONE notebook before modifying it", notebook=current)
                current = converge_stopped(module, client, models, p, current)
                module.sdk_call(client.ModifyNotebook, modify_request(models, current["Id"], p))
            if p["state"] == "running":
                current = get(module, client, models, p["notebook_id"], p.get("project_id"))
                if status(current) != "running":
                    module.sdk_call(client.StartNotebook, id_request(models.StartNotebookRequest, p["notebook_id"]))
                    if p["wait"]:
                        wait_status(module, client, models, p, "running")
            else:
                current = converge_stopped(module, client, models, p, current)
            current = get(module, client, models, p["notebook_id"], p.get("project_id"))
        module.exit_json(changed=True, **(diff_value or {}), notebook=current if not module.check_mode else target, notebook_id=current["Id"])
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
