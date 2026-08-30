#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: cvm_launch_template_version
short_description: Manage Tencent Cloud CVM launch-template versions
version_added: "0.14.0"
description:
  - Creates and deletes immutable CVM launch-template versions.
  - A version can be selected by number or by its exact description; configuration drift requires replacement with a new version.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  template_id: {type: str, required: true, description: Launch-template ID.}
  version: {type: int, description: Existing version number.}
  description: {type: str, description: Version description used as the declarative identity when version is omitted.}
  template_data: {type: dict, description: Complete SDK-compatible launch-template version data.}
  base_version: {type: int, description: Existing version inherited by the new version.}
  make_default: {type: bool, default: false, description: Select the resulting version as the template default.}
  force_replace: {type: bool, default: false, description: Delete and recreate when immutable version data differs.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cvm_launch_template_version:
    template_id: lt-xxxxxxxx
    description: web-v2
    template_data:
      Placement: {Zone: ap-guangzhou-3}
      ImageId: img-xxxxxxxx
      InstanceType: S5.LARGE8
    make_default: true
'''
RETURN = r'''launch_template_version: {description: Effective immutable version metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cvm.v20170312 import models, cvm_client
    return models, cvm_client
def describe_request(models, p, offset=0):
    request = models.DescribeLaunchTemplateVersionsRequest(); request.LaunchTemplateId, request.Offset, request.Limit = p["template_id"], offset, 100
    if p.get("version") is not None: request.LaunchTemplateVersions = [p["version"]]
    return request
def create_request(models, p):
    request = models.CreateLaunchTemplateVersionRequest(); request._deserialize(p["template_data"])
    request.LaunchTemplateId, request.LaunchTemplateVersionDescription = p["template_id"], p["description"]
    request.LaunchTemplateVersion = p.get("base_version"); return request
def default_request(models, p, version):
    request = models.ModifyLaunchTemplateDefaultVersionRequest(); request.LaunchTemplateId, request.DefaultVersion = p["template_id"], version; return request
def delete_request(models, p, version):
    request = models.DeleteLaunchTemplateVersionsRequest(); request.LaunchTemplateId, request.LaunchTemplateVersions = p["template_id"], [version]; return request


def _subset(current, target):
    if isinstance(target, dict): return isinstance(current, dict) and all(k in current and _subset(current[k], v) for k, v in target.items())
    if isinstance(target, list): return current == target
    return current == target
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeLaunchTemplateVersions, describe_request(models, p)); matches = []
    for item in response.LaunchTemplateVersionSet or []:
        value = item._serialize(allow_none=True)
        if (p.get("version") is not None and int(value.get("LaunchTemplateVersion") or 0) == p["version"]) or (p.get("version") is None and value.get("LaunchTemplateVersionDescription") == p.get("description")): matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple launch-template versions matched; specify version")
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "template_id": {"required": True}, "version": {"type": "int"}, "description": {}, "template_data": {"type": "dict"}, "base_version": {"type": "int"}, "make_default": {"type": "bool", "default": False}, "force_replace": {"type": "bool", "default": False}}, required_one_of=[("version", "description")], supports_check_mode=True)
    p = module.params
    if p["state"] == "present" and (not p.get("description") or not p.get("template_data")): module.fail_json(msg="description and template_data are required when state=present")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.CvmClient, "cvm.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, launch_template_version=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteLaunchTemplateVersions, delete_request(models, p, int(current["LaunchTemplateVersion"])))
            module.exit_json(changed=True, **(diff or {}), launch_template_version=current if module.check_mode else None)
        data_matches = bool(current and _subset(current.get("LaunchTemplateVersionData") or {}, p["template_data"]))
        default_matches = bool(current and (not p["make_default"] or current.get("IsDefaultVersion")))
        if data_matches and default_matches: module.exit_json(changed=False, launch_template_version=current)
        if current and not data_matches and not p["force_replace"]: module.fail_json(msg="launch-template versions are immutable; set force_replace=true to replace this version", version=current.get("LaunchTemplateVersion"))
        target = {"LaunchTemplateVersionDescription": p["description"], "LaunchTemplateVersionData": p["template_data"], "IsDefaultVersion": p["make_default"]}; diff = maybe_diff(module, current, target)
        if not module.check_mode:
            if current and not data_matches:
                old_version = int(current["LaunchTemplateVersion"]); preserve_default = bool(current.get("IsDefaultVersion")); p["version"] = None
                p["version"] = int(module.sdk_call(client.CreateLaunchTemplateVersion, create_request(models, p)).LaunchTemplateVersionNumber); current = find(module, client, models, p)
                if preserve_default or p["make_default"]:
                    module.sdk_call(client.ModifyLaunchTemplateDefaultVersion, default_request(models, p, p["version"])); current = find(module, client, models, p)
                module.sdk_call(client.DeleteLaunchTemplateVersions, delete_request(models, p, old_version))
            if not current:
                p["version"] = int(module.sdk_call(client.CreateLaunchTemplateVersion, create_request(models, p)).LaunchTemplateVersionNumber); current = find(module, client, models, p)
            if p["make_default"] and not current.get("IsDefaultVersion"):
                module.sdk_call(client.ModifyLaunchTemplateDefaultVersion, default_request(models, p, int(current["LaunchTemplateVersion"]))); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), launch_template_version=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
