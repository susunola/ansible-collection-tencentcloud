#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tse_config_file_deployment
short_description: Atomically deploy a Tencent Cloud TSE configuration file and release
version_added: "0.14.0"
description: Reconciles a configuration file and named release through one atomic API operation; teardown removes the release before the file.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired deployment state.}
  instance_id: {type: str, required: true, description: TSE engine instance ID.}
  namespace: {type: str, required: true, description: Configuration namespace.}
  group: {type: str, required: true, description: Configuration group.}
  name: {type: str, required: true, description: Configuration file name.}
  release_name: {type: str, required: true, description: Stable release name.}
  content: {type: str, description: Exact configuration content.}
  format: {type: str, description: Configuration format.}
  comment: {type: str, description: Configuration and release comment.}
  create_by: {type: str, description: Creator metadata.}
  modify_by: {type: str, description: Modifier metadata.}
  tags: {type: list, elements: dict, description: SDK ConfigFileTag payloads.}
  strict_enable: {type: bool, default: true, description: Reject conflicting release versions.}
  waiter_delay: {type: int, default: 2, description: Reconciliation polling interval.}
  waiter_timeout: {type: int, default: 60, description: Reconciliation timeout.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tse_config_file_deployment:
    instance_id: ins-xxxxxxxx
    namespace: production
    group: application
    name: orders.yaml
    release_name: production
    format: YAML
    content: "server:\n  port: 8080\n"
'''
RETURN = r'''
deployment: {description: Effective configuration file and release metadata., type: dict, returned: always}
'''

import json
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client
    return models, tse_client


def release_detail_request(models, params):
    value = models.DescribeConfigFileReleaseRequest()
    value.InstanceId, value.Namespace, value.Group = params["instance_id"], params["namespace"], params["group"]
    value.Name, value.ReleaseName = params["name"], params["release_name"]
    return value


def file_detail_request(models, params):
    value = models.DescribeConfigFileRequest()
    value.InstanceId, value.Namespace, value.Group, value.Name = params["instance_id"], params["namespace"], params["group"], params["name"]
    return value


def desired(params):
    value = {"ReleaseName": params["release_name"], "Namespace": params["namespace"],
             "Group": params["group"], "FileName": params["name"]}
    for source, target in (("content", "Content"), ("format", "Format"), ("comment", "Comment"),
                           ("create_by", "CreateBy"), ("modify_by", "ModifyBy"), ("tags", "Tags")):
        if params.get(source) is not None:
            value[target] = params[source]
    return value


def expected(target):
    release = {key: value for key, value in target.items() if key != "Tags"}
    release["Name"] = release.pop("ReleaseName")
    config_file = {key: value for key, value in target.items() if key != "ReleaseName"}
    config_file["Name"] = config_file.pop("FileName")
    return release, config_file


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and contains(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return actual == expected
    return actual == expected


def find_release(module, client, models, params):
    try:
        response = module.sdk_call(client.DescribeConfigFileRelease, release_detail_request(models, params))
        value = response.ConfigFileRelease
        return value._serialize(allow_none=True) if value else None
    except Exception as exc:
        code = str(exc.get_code() if hasattr(exc, "get_code") else "").lower()
        if "notfound" in code or "notexist" in code:
            return None
        raise


def find_file(module, client, models, params):
    try:
        response = module.sdk_call(client.DescribeConfigFile, file_detail_request(models, params))
        value = response.ConfigFile
        return value._serialize(allow_none=True) if value else None
    except Exception as exc:
        code = str(exc.get_code() if hasattr(exc, "get_code") else "").lower()
        if "notfound" in code or "notexist" in code:
            return None
        raise


def deploy_request(models, params, target):
    info = models.ConfigFilePublishInfo()
    info.from_json_string(json.dumps(target))
    value = models.CreateOrUpdateConfigFileAndReleaseRequest()
    value.InstanceId, value.ConfigFilePublishInfo, value.StrictEnable = params["instance_id"], info, params["strict_enable"]
    return value


def delete_release_request(models, params, current):
    item = models.ConfigFileReleaseDeletion()
    item.from_json_string(json.dumps({"Namespace": params["namespace"], "Group": params["group"],
                                     "FileName": params["name"], "ReleaseVersion": current.get("Version"),
                                     "Id": current.get("Id")}))
    value = models.DeleteConfigFileReleasesRequest()
    value.InstanceId, value.ConfigFileReleases = params["instance_id"], [item]
    return value


def delete_file_request(models, params, current):
    value = models.DeleteConfigFilesRequest()
    value.InstanceId, value.Namespace, value.Group = params["instance_id"], params["namespace"], params["group"]
    value.Name, value.Id = params["name"], current.get("Id")
    return value


def wait(module, client, models, params, release_target=None, file_target=None, absent=False):
    deadline = time.time() + params["waiter_timeout"]
    while True:
        release, config_file = find_release(module, client, models, params), find_file(module, client, models, params)
        if absent and release is None and config_file is None:
            return None
        if (not absent and release is not None and config_file is not None
                and contains(release, release_target or {}) and contains(config_file, file_target or {})):
            return {"release": release, "config_file": config_file}
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for TSE configuration deployment convergence",
                             release=release, config_file=config_file)
        time.sleep(params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={
        "state": {"choices": ["present", "absent"], "default": "present"},
        "instance_id": {"required": True}, "namespace": {"required": True}, "group": {"required": True},
        "name": {"required": True}, "release_name": {"required": True}, "content": {}, "format": {},
        "comment": {}, "create_by": {}, "modify_by": {}, "tags": {"type": "list", "elements": "dict"},
        "strict_enable": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 2}, "waiter_timeout": {"type": "int", "default": 60},
    }, supports_check_mode=True)
    params = module.params
    if params["state"] == "present" and any(params.get(key) is None for key in ("content", "format")):
        module.fail_json(msg="content and format are required for a TSE configuration deployment")
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.TseClient, "tse.tencentcloudapi.com")
    try:
        current_release, current_file = find_release(module, client, models, params), find_file(module, client, models, params)
        before = {"release": current_release, "config_file": current_file} if current_release or current_file else None
        if params["state"] == "absent":
            if before is None:
                module.exit_json(changed=False, deployment=None)
            diff = maybe_diff(module, before, None)
            if not module.check_mode:
                if current_release:
                    module.sdk_call(client.DeleteConfigFileReleases, delete_release_request(models, params, current_release))
                if current_file:
                    module.sdk_call(client.DeleteConfigFiles, delete_file_request(models, params, current_file))
                wait(module, client, models, params, absent=True)
            module.exit_json(changed=True, **(diff or {}), deployment=None)
        target = desired(params)
        release_target, file_target = expected(target)
        if (current_release and current_file and contains(current_release, release_target)
                and contains(current_file, file_target)):
            module.exit_json(changed=False, deployment=before)
        after = {"release": release_target, "config_file": file_target}
        diff = maybe_diff(module, before, after)
        if not module.check_mode:
            response = module.sdk_call(client.CreateOrUpdateConfigFileAndRelease, deploy_request(models, params, target))
            if response.Result is not True:
                module.fail_json(msg="TSE atomic configuration deployment returned an unsuccessful result")
            deployment = wait(module, client, models, params, release_target, file_target)
            deployment.update({"config_file_id": response.ConfigFileId, "release_id": response.ConfigFileReleaseId})
        else:
            deployment = after
        module.exit_json(changed=True, **(diff or {}), deployment=deployment)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
