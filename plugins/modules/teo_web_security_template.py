#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: teo_web_security_template
short_description: Manage Tencent Cloud EdgeOne web security templates
version_added: "0.14.0"
description: Creates, renames and deletes EdgeOne web security templates while preserving policy rules managed by dedicated rule resources.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired template state.}
  zone_id: {type: str, required: true, description: EdgeOne zone ID.}
  template_id: {type: str, description: Existing web security template ID.}
  name: {type: str, description: "Template name, also used for lookup."}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""

EXAMPLES = r"""
- name: Create a production web security template
  susunola.tencentcloud.teo_web_security_template:
    region: ap-guangzhou
    zone_id: zone-xxxxxxxx
    name: production_security
"""

RETURN = r"""security_template: {description: EdgeOne web security template and binding summary., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.teo.v20220901 import models, teo_client

    return models, teo_client


def describe_request(models, p):
    request = models.DescribeWebSecurityTemplatesRequest()
    request.ZoneIds = [p["zone_id"]]
    return request


def create_request(models, p):
    request = models.CreateWebSecurityTemplateRequest()
    request.ZoneId, request.TemplateName = p["zone_id"], p["name"]
    return request


def update_request(models, p, template_id):
    request = models.ModifyWebSecurityTemplateRequest()
    request.ZoneId, request.TemplateId, request.TemplateName = p["zone_id"], template_id, p["name"]
    return request


def delete_request(models, p, template_id):
    request = models.DeleteWebSecurityTemplateRequest()
    request.ZoneId, request.TemplateId = p["zone_id"], template_id
    return request


def find_template(module, client, models, p):
    response = module.sdk_call(client.DescribeWebSecurityTemplates, describe_request(models, p))
    matches = []
    for value in response.SecurityPolicyTemplates or []:
        item = value._serialize(allow_none=True)
        if p.get("template_id") and item.get("TemplateId") == p["template_id"]:
            matches.append(item)
        elif not p.get("template_id") and p.get("name") and item.get("TemplateName") == p["name"]:
            matches.append(item)
    if len(matches) > 1:
        module.fail_json(msg="Multiple EdgeOne web security templates matched; specify template_id")
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(
        argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "zone_id": {"required": True}, "template_id": {}, "name": {}},
        required_one_of=[("template_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p.get("name"):
        module.fail_json(msg="name is required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TeoClient, "teo.tencentcloudapi.com")
    try:
        current = find_template(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, security_template=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteWebSecurityTemplate, delete_request(models, p, current["TemplateId"]))
            module.exit_json(changed=True, **(diff or {}), security_template=current if module.check_mode else None)
        before = {"TemplateName": current.get("TemplateName")} if current else None
        target = {"TemplateName": p["name"]}
        if before == target:
            module.exit_json(changed=False, security_template=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if not current:
                p["template_id"] = module.sdk_call(client.CreateWebSecurityTemplate, create_request(models, p)).TemplateId
            else:
                module.sdk_call(client.ModifyWebSecurityTemplate, update_request(models, p, current["TemplateId"]))
            current = find_template(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), security_template=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
