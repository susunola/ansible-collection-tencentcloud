#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_config_file_release
short_description: Manage a Tencent Cloud TSE configuration file release
version_added: "0.14.0"
description: Publishes exact configuration content, rolls an existing release back to a desired version, or deletes the release.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: TSE engine instance ID.}
  namespace: {type: str, required: true, description: Configuration namespace.}
  group: {type: str, required: true, description: Configuration group.}
  name: {type: str, required: true, description: Configuration file name.}
  release_name: {type: str, required: true, description: Stable release name.}
  release_id: {type: str, description: Existing release ID.}
  content: {type: str, description: Exact released content.}
  format: {type: str, description: Configuration format.}
  comment: {type: str, description: Configuration comment stored in the release.}
  release_description: {type: str, description: Release description.}
  supported_client: {type: int, description: Supported client type.}
  persistent: {type: dict, description: SDK ConfigFilePersistent payload.}
  beta_labels: {type: list, elements: dict, description: SDK gray-release label entries.}
  release_type: {type: str, description: Release type such as gray.}
  rollback_version: {type: str, description: Historical version that must become active; mutually exclusive with content publication fields.}
  strict_enable: {type: bool, default: true, description: Ask Tencent Cloud to reject conflicting release versions.}
  waiter_delay: {type: int, default: 2, description: Reconciliation polling interval.}
  waiter_timeout: {type: int, default: 60, description: Reconciliation timeout.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_config_file_release:
    instance_id: ins-xxxxxxxx
    namespace: production
    group: application
    name: orders.yaml
    release_name: production
    format: YAML
    content: "server:\n  port: 8080\n"

- susunola.tencentcloud.tse_config_file_release:
    instance_id: ins-xxxxxxxx
    namespace: production
    group: application
    name: orders.yaml
    release_name: production
    rollback_version: '12'
"""
RETURN = r"""release: {description: Effective configuration release metadata and content., type: dict, returned: always}"""
import json
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def detail_request(models, p):
    r = models.DescribeConfigFileReleaseRequest()
    r.InstanceId, r.Namespace, r.Group, r.Name, r.ReleaseName, r.Id = (
        p["instance_id"],
        p["namespace"],
        p["group"],
        p["name"],
        p["release_name"],
        p.get("release_id"),
    )
    return r


def release_model(models, value):
    r = models.ConfigFileRelease()
    r.from_json_string(json.dumps(value))
    return r


def publish_request(models, p, target):
    r = models.PublishConfigFilesRequest()
    r.InstanceId, r.ConfigFileReleases, r.StrictEnable = p["instance_id"], release_model(models, target), p["strict_enable"]
    return r


def rollback_request(models, p, current):
    target = {key: current.get(key) for key in ("Id", "Name", "Namespace", "Group", "FileName")}
    target["Version"] = p["rollback_version"]
    r = models.RollbackConfigFileReleasesRequest()
    r.InstanceId, r.RollbackConfigFileReleases = p["instance_id"], [release_model(models, target)]
    return r


def delete_request(models, p, current):
    value = {
        "Namespace": current.get("Namespace") or p["namespace"],
        "Group": current.get("Group") or p["group"],
        "FileName": current.get("FileName") or p["name"],
        "ReleaseVersion": current.get("Version"),
        "Id": current.get("Id"),
    }
    item = models.ConfigFileReleaseDeletion()
    item.from_json_string(json.dumps(value))
    r = models.DeleteConfigFileReleasesRequest()
    r.InstanceId, r.ConfigFileReleases = p["instance_id"], [item]
    return r


def find(module, client, models, p):
    try:
        value = module.sdk_call(client.DescribeConfigFileRelease, detail_request(models, p)).ConfigFileRelease
        return value._serialize(allow_none=True) if value else None
    except Exception as exc:
        code = str(exc.get_code() if hasattr(exc, "get_code") else "").lower()
        if "notfound" in code or "notexist" in code:
            return None
        raise


def desired(p, current=None):
    value = {"Name": p["release_name"], "Namespace": p["namespace"], "Group": p["group"], "FileName": p["name"]}
    mapping = (
        ("content", "Content"),
        ("format", "Format"),
        ("comment", "Comment"),
        ("release_description", "ReleaseDescription"),
        ("supported_client", "ConfigFileSupportedClient"),
        ("persistent", "ConfigFilePersistent"),
        ("beta_labels", "BetaLabels"),
        ("release_type", "ReleaseType"),
    )
    for source, target in mapping:
        selected = p.get(source) if p.get(source) is not None else (current or {}).get(target)
        if selected is not None:
            value[target] = selected
    return value


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and contains(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return actual == expected
    return actual == expected or (actual is not None and expected is not None and str(actual) == str(expected))


def wait(module, client, models, p, target=None, absent=False):
    deadline = time.time() + p["waiter_timeout"]
    while True:
        value = find(module, client, models, p)
        if absent and value is None:
            return None
        if not absent and value is not None and contains(value, target or {}):
            return value
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for TSE configuration release convergence", release=value)
        time.sleep(p["waiter_delay"])


def require_success(module, response, operation):
    if getattr(response, "Result", None) is not True:
        module.fail_json(msg="TSE configuration release operation returned an unsuccessful result", operation=operation)


def run_module():
    publication = ("content", "format", "comment", "release_description", "supported_client", "persistent", "beta_labels", "release_type")
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "instance_id": {"required": True},
        "namespace": {"required": True},
        "group": {"required": True},
        "name": {"required": True},
        "release_name": {"required": True},
        "release_id": {},
        "content": {},
        "format": {},
        "comment": {},
        "release_description": {},
        "supported_client": {"type": "int"},
        "persistent": {"type": "dict"},
        "beta_labels": {"type": "list", "elements": "dict"},
        "release_type": {},
        "rollback_version": {},
        "strict_enable": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 2},
        "waiter_timeout": {"type": "int", "default": 60},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    conflicts = [field for field in publication if p.get("rollback_version") is not None and p.get(field) is not None]
    if p["state"] == "present" and conflicts:
        module.fail_json(msg="rollback_version is mutually exclusive with publication fields", conflicts=conflicts)
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, release=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                require_success(module, module.sdk_call(client.DeleteConfigFileReleases, delete_request(models, p, current)), "DeleteConfigFileReleases")
                wait(module, client, models, p, absent=True)
            module.exit_json(changed=True, **(diff or {}), release=None)
        if p.get("rollback_version") is not None:
            if not current:
                module.fail_json(msg="An existing TSE configuration release is required for rollback")
            if str(current.get("Version")) == str(p["rollback_version"]):
                module.exit_json(changed=False, release=current)
            target = {"Version": p["rollback_version"]}
            diff = maybe_diff(module, {"Version": current.get("Version")}, target)
            if not module.check_mode:
                require_success(module, module.sdk_call(client.RollbackConfigFileReleases, rollback_request(models, p, current)), "RollbackConfigFileReleases")
                current = wait(module, client, models, p, target)
            module.exit_json(changed=True, **(diff or {}), release=current if not module.check_mode else dict(current, **target))
        target = desired(p, current)
        if not current:
            missing = [key for key in ("content", "format") if p.get(key) is None]
            if missing:
                module.fail_json(msg="content and format are required for a new TSE configuration release", missing=missing)
        if current and contains(current, target):
            module.exit_json(changed=False, release=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            response = module.sdk_call(client.PublishConfigFiles, publish_request(models, p, target))
            require_success(module, response, "PublishConfigFiles")
            p["release_id"] = response.ConfigFileReleaseId or p.get("release_id")
            current = wait(module, client, models, p, target)
        module.exit_json(changed=True, **(diff or {}), release=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
