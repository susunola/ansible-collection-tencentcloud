#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: postgresql_parameter_template
short_description: Manage Tencent Cloud PostgreSQL parameter templates
version_added: "0.14.0"
description: Creates, updates and deletes reusable TencentDB for PostgreSQL parameter templates.
options:
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  template_id: {type: str, description: Existing parameter template ID.}
  name: {type: str, description: Template name.}
  description: {type: str, default: '', description: Template description.}
  database_major_version: {type: str, description: PostgreSQL major version required at creation.}
  database_engine: {type: str, default: postgresql, description: Database engine required at creation.}
  parameters: {type: dict, default: {}, description: Parameter name and expected value mapping to enforce.}
  reset_parameters: {type: list, elements: str, default: [], description: Parameter names to reset to template defaults.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.postgresql_parameter_template:
    name: production-pg15
    database_major_version: '15'
    parameters: {max_connections: '1000'}
"""
RETURN = r"""parameter_template: {description: PostgreSQL parameter template metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.postgres.v20170312 import models, postgres_client

    return models, postgres_client


def find(module, client, models, template_id, name):
    offset, matches = 0, []
    while True:
        request = models.DescribeParameterTemplatesRequest()
        request.Offset, request.Limit = offset, 100
        response = module.sdk_call(client.DescribeParameterTemplates, request)
        items = list(response.ParameterTemplateSet or [])
        matches.extend(x for x in items if (template_id and x.TemplateId == template_id) or (not template_id and x.TemplateName == name))
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple PostgreSQL parameter templates have the requested name", name=name)
    if not matches:
        return None
    request = models.DescribeParameterTemplateAttributesRequest()
    request.TemplateId = matches[0].TemplateId
    return module.sdk_call(client.DescribeParameterTemplateAttributes, request)._serialize(allow_none=True)


def normalize(value, parameter_names=()):
    names = set(parameter_names)
    return {
        "TemplateName": value.get("TemplateName"),
        "TemplateDescription": value.get("TemplateDescription") or "",
        "DBMajorVersion": value.get("DBMajorVersion"),
        "DBEngine": value.get("DBEngine"),
        "Parameters": {x.get("Name"): x.get("CurrentValue") for x in value.get("ParamInfoSet") or [] if x.get("Name") in names},
    }


def entries(models, values):
    result = []
    for name, value in sorted(values.items()):
        item = models.ParamEntry()
        item.Name, item.ExpectedValue = str(name), str(value)
        result.append(item)
    return result


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "template_id": {},
            "name": {},
            "description": {"default": ""},
            "database_major_version": {},
            "database_engine": {"default": "postgresql"},
            "parameters": {"type": "dict", "default": {}},
            "reset_parameters": {"type": "list", "elements": "str", "default": []},
        },
        required_one_of=[("template_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p["name"]:
        module.fail_json(msg="name is required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.PostgresClient, "postgres.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["template_id"], p["name"])
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, parameter_template=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.DeleteParameterTemplateRequest()
                request.TemplateId = current["TemplateId"]
                module.sdk_call(client.DeleteParameterTemplate, request)
            module.exit_json(changed=True, **(diff or {}), parameter_template=current if module.check_mode else None)
        target = {
            "TemplateName": p["name"],
            "TemplateDescription": p["description"],
            "DBMajorVersion": p["database_major_version"] or (current or {}).get("DBMajorVersion"),
            "DBEngine": p["database_engine"],
            "Parameters": {str(k): str(v) for k, v in p["parameters"].items()},
        }
        before = normalize(current, p["parameters"]) if current else None
        if before == target and not p["reset_parameters"]:
            module.exit_json(changed=False, parameter_template=current)
        if current:
            require_immutable_unchanged(module, before, target, ("DBMajorVersion", "DBEngine"), "PostgreSQL parameter template")
        elif not p["database_major_version"]:
            module.fail_json(msg="database_major_version is required when creating a PostgreSQL parameter template")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if not current:
                request = models.CreateParameterTemplateRequest()
                request.TemplateName, request.TemplateDescription = p["name"], p["description"]
                request.DBMajorVersion, request.DBEngine = p["database_major_version"], p["database_engine"]
                p["template_id"] = module.sdk_call(client.CreateParameterTemplate, request).TemplateId
                current = find(module, client, models, p["template_id"], None)
            request = models.ModifyParameterTemplateRequest()
            request.TemplateId = current["TemplateId"]
            request.TemplateName, request.TemplateDescription = p["name"], p["description"]
            request.ModifyParamEntrySet = entries(models, p["parameters"])
            request.DeleteParamSet = p["reset_parameters"]
            module.sdk_call(client.ModifyParameterTemplate, request)
            current = find(module, client, models, current["TemplateId"], None)
        module.exit_json(changed=True, **(diff or {}), parameter_template=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
