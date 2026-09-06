#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tem_application
short_description: Manage Tencent Cloud TEM applications
version_added: "0.14.0"
description: Creates, updates and deletes TEM application definitions.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  application_id: {type: str, description: Existing application ID.}
  name: {type: str, description: Application name and immutable identity.}
  description: {type: str, description: Application description.}
  use_default_image_service: {type: int, choices: [0, 1], description: Use the default image service.}
  repo_type: {type: int, choices: [0, 1], description: Image repository type.}
  instance_id: {type: str, description: Enterprise registry instance ID.}
  repo_server: {type: str, description: Image repository server.}
  repo_name: {type: str, description: Image repository name.}
  source_channel: {type: int, default: 0, description: TEM source channel.}
  subnet_ids: {type: list, elements: str, description: Application subnet IDs.}
  coding_language: {type: str, description: Application programming language.}
  deploy_mode: {type: str, description: Deployment mode.}
  enable_tracing: {type: int, choices: [0, 1], description: APM tracing switch.}
  default_repo_parameters: {type: dict, description: SDK UseDefaultRepoParameters payload.}
  tags: {type: dict, description: Creation-time tags.}
  environment_id: {type: str, description: Environment used when deleting a deployed application.}
  delete_if_no_running_version: {type: bool, default: true, description: Delete the application when it has no running version.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tem_application:
    name: order-api
    description: Order service
    use_default_image_service: 1
    coding_language: JAVA
    deploy_mode: IMAGE
"""
RETURN = r"""application: {description: Effective TEM application metadata., type: dict, returned: always}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.tem.v20210701 import models, tem_client

    return models, tem_client


def _model(cls, value):
    if value is None:
        return None
    x = cls()
    x.from_json_string(json.dumps(value))
    return x


def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        x = models.Tag()
        x.TagKey, x.TagValue = str(key), str(value)
        result.append(x)
    return result


def describe_request(models, p, offset=0):
    r = models.DescribeApplicationsRequest()
    r.ApplicationId = p.get("application_id")
    r.Keyword = None if p.get("application_id") else p.get("name")
    r.Offset, r.Limit = offset, 100
    r.SourceChannel = p["source_channel"]
    return r


def create_request(models, p):
    r = models.CreateApplicationRequest()
    r.ApplicationName, r.Description = p["name"], p.get("description")
    r.UseDefaultImageService, r.RepoType = p.get("use_default_image_service"), p.get("repo_type")
    r.InstanceId, r.RepoServer, r.RepoName = p.get("instance_id"), p.get("repo_server"), p.get("repo_name")
    r.SourceChannel = p["source_channel"]
    r.SubnetList = p.get("subnet_ids")
    r.CodingLanguage, r.DeployMode, r.EnableTracing = p.get("coding_language"), p.get("deploy_mode"), p.get("enable_tracing")
    r.UseDefaultImageServiceParameters = _model(models.UseDefaultRepoParameters, p.get("default_repo_parameters"))
    r.Tags = _tags(models, p.get("tags"))
    return r


def update_request(models, p, application_id, description):
    r = models.ModifyApplicationInfoRequest()
    r.ApplicationId, r.Description, r.SourceChannel = application_id, description, p["source_channel"]
    r.EnableTracing = p.get("enable_tracing")
    return r


def delete_request(models, p, application_id):
    r = models.DeleteApplicationRequest()
    r.ApplicationId, r.EnvironmentId, r.SourceChannel = application_id, p.get("environment_id"), p["source_channel"]
    r.DeleteApplicationIfNoRunningVersion = p["delete_if_no_running_version"]
    return r


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        result = module.sdk_call(client.DescribeApplications, describe_request(models, p, offset)).Result
        page = (result.Records if result else None) or []
        for item in page:
            value = item._serialize(allow_none=True)
            if (p.get("application_id") and value.get("ApplicationId") == p["application_id"]) or (
                not p.get("application_id") and value.get("ApplicationName") == p.get("name")
            ):
                matches.append(value)
        offset += len(page)
        if not page or offset >= int((result.Total if result else 0) or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple TEM applications matched; specify application_id")
    return matches[0] if matches else None


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "application_id": {},
        "name": {},
        "description": {},
        "use_default_image_service": {"type": "int", "choices": [0, 1]},
        "repo_type": {"type": "int", "choices": [0, 1]},
        "instance_id": {},
        "repo_server": {},
        "repo_name": {},
        "source_channel": {"type": "int", "default": 0},
        "subnet_ids": {"type": "list", "elements": "str"},
        "coding_language": {},
        "deploy_mode": {},
        "enable_tracing": {"type": "int", "choices": [0, 1]},
        "default_repo_parameters": {"type": "dict"},
        "tags": {"type": "dict"},
        "environment_id": {},
        "delete_if_no_running_version": {"type": "bool", "default": True},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("application_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TemClient, "tem.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, application=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteApplication, delete_request(models, p, current["ApplicationId"]))
            module.exit_json(changed=True, **(diff or {}), application=None)
        if not current:
            if not p.get("name"):
                module.fail_json(msg="name is required to create a TEM application")
            target = {"ApplicationName": p["name"], "Description": p.get("description"), "EnableTracing": p.get("enable_tracing")}
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                p["application_id"] = module.sdk_call(client.CreateApplication, create_request(models, p)).Result
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), application=current if not module.check_mode else target)
        before = {"ApplicationName": current.get("ApplicationName"), "Description": current.get("Description"), "EnableTracing": current.get("EnableTracing")}
        target = {
            "ApplicationName": p.get("name") or before["ApplicationName"],
            "Description": p.get("description") if p.get("description") is not None else before["Description"],
            "EnableTracing": p.get("enable_tracing") if p.get("enable_tracing") is not None else before["EnableTracing"],
        }
        if before == target:
            module.exit_json(changed=False, application=current)
        require_immutable_unchanged(module, before, target, ("ApplicationName",), "TEM application")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyApplicationInfo, update_request(models, p, current["ApplicationId"], target["Description"]))
            p["application_id"] = current["ApplicationId"]
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), application=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
