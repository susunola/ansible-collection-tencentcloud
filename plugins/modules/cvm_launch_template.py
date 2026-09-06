#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cvm_launch_template
short_description: Manage Tencent Cloud CVM launch templates
version_added: "0.14.0"
description:
  - Creates and deletes CVM launch templates and selects their default version.
  - Initial template data creates version 1 and is creation-only; use C(cvm_launch_template_version) for later configuration revisions.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  template_id: {type: str, description: Existing launch-template ID.}
  name: {type: str, description: Launch-template name.}
  initial_data: {type: dict, description: SDK-compatible launch-template version fields used when creating the template.}
  version_description: {type: str, default: initial version, description: Description of version 1.}
  default_version: {type: int, description: Existing version number that should be the default.}
  force_replace: {type: bool, default: false, description: Replace the template when its immutable name differs.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cvm_launch_template:
    name: web-production
    initial_data:
      Placement: {Zone: ap-guangzhou-3}
      ImageId: img-xxxxxxxx
      InstanceType: S5.MEDIUM4
      SecurityGroupIds: [sg-xxxxxxxx]
"""
RETURN = r"""launch_template: {description: Effective launch-template metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cvm.v20170312 import models, cvm_client

    return models, cvm_client


def describe_request(models, p, offset=0):
    request = models.DescribeLaunchTemplatesRequest()
    request.Offset, request.Limit = offset, 100
    if p.get("template_id"):
        request.LaunchTemplateIds = [p["template_id"]]
    elif p.get("name"):
        item = models.Filter()
        item.Name, item.Values = "launch-template-name", [p["name"]]
        request.Filters = [item]
    return request


def create_request(models, p):
    request = models.CreateLaunchTemplateRequest()
    request._deserialize(p["initial_data"])
    request.LaunchTemplateName, request.LaunchTemplateVersionDescription = p["name"], p["version_description"]
    return request


def default_request(models, template_id, version):
    request = models.ModifyLaunchTemplateDefaultVersionRequest()
    request.LaunchTemplateId, request.DefaultVersion = template_id, version
    return request


def delete_request(models, template_id):
    request = models.DeleteLaunchTemplateRequest()
    request.LaunchTemplateId = template_id
    return request


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeLaunchTemplates, describe_request(models, p))
    matches = []
    for item in response.LaunchTemplateSet or []:
        value = item._serialize(allow_none=True)
        if (p.get("template_id") and value.get("LaunchTemplateId") == p["template_id"]) or (
            not p.get("template_id") and value.get("LaunchTemplateName") == p.get("name")
        ):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple CVM launch templates matched; specify template_id")
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "template_id": {},
            "name": {},
            "initial_data": {"type": "dict"},
            "version_description": {"default": "initial version"},
            "default_version": {"type": "int"},
            "force_replace": {"type": "bool", "default": False},
        },
        required_one_of=[("template_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p.get("name"):
        module.fail_json(msg="name is required when state=present")
    if p.get("default_version") is not None and p["default_version"] < 1:
        module.fail_json(msg="default_version must be positive")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CvmClient, "cvm.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, launch_template=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteLaunchTemplate, delete_request(models, current["LaunchTemplateId"]))
            module.exit_json(changed=True, **(diff or {}), launch_template=current if module.check_mode else None)
        replace = bool(current and current.get("LaunchTemplateName") != p["name"])
        if replace and not p["force_replace"]:
            module.fail_json(
                msg="launch-template name is immutable; set force_replace=true to recreate it",
                current_name=current.get("LaunchTemplateName"),
                desired_name=p["name"],
            )
        desired_default = p.get("default_version")
        if current and not replace and (desired_default is None or int(current.get("DefaultVersionNumber") or 0) == desired_default):
            module.exit_json(changed=False, launch_template=current)
        if (not current or replace) and not p.get("initial_data"):
            module.fail_json(msg="initial_data is required when creating or replacing a launch template")
        target = {"LaunchTemplateName": p["name"], "DefaultVersionNumber": desired_default or 1}
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            if replace:
                module.sdk_call(client.DeleteLaunchTemplate, delete_request(models, current["LaunchTemplateId"]))
                current = None
            if not current:
                p["template_id"] = module.sdk_call(client.CreateLaunchTemplate, create_request(models, p)).LaunchTemplateId
                current = find(module, client, models, p)
            if desired_default is not None and int(current.get("DefaultVersionNumber") or 0) != desired_default:
                module.sdk_call(client.ModifyLaunchTemplateDefaultVersion, default_request(models, current["LaunchTemplateId"], desired_default))
                current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), launch_template=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
