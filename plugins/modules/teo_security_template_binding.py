#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: teo_security_template_binding
short_description: Manage Tencent Cloud EdgeOne security template bindings
version_added: "0.14.0"
description: Reconciles the exact set of acceleration domains bound to an EdgeOne web security template.
options:
  zone_id: {type: str, required: true, description: EdgeOne zone ID.}
  template_id: {type: str, required: true, description: Web security template ID.}
  domains: {type: list, elements: str, required: true, description: Exact set of acceleration domains bound to the template.}
  overwrite: {type: bool, default: true, description: Replace another template currently bound to a requested domain.}
  unbind_policy: {type: str, choices: [keep-policy, use-default], default: keep-policy, description: Policy retained by domains removed from the template.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""

EXAMPLES = r"""
- name: Bind production domains to a security template
  susunola.tencentcloud.teo_security_template_binding:
    region: ap-guangzhou
    zone_id: zone-xxxxxxxx
    template_id: temp-xxxxxxxx
    domains:
      - app.example.com
      - api.example.com
"""

RETURN = r"""bindings: {description: Current template binding records and deployment states., type: list, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.teo.v20220901 import models, teo_client

    return models, teo_client


def describe_request(models, p):
    request = models.DescribeSecurityTemplateBindingsRequest()
    request.ZoneId, request.TemplateId = p["zone_id"], [p["template_id"]]
    return request


def bind_request(models, p, domains):
    request = models.BindSecurityTemplateToEntityRequest()
    request.ZoneId, request.TemplateId = p["zone_id"], p["template_id"]
    request.Entities, request.Operate, request.OverWrite = domains, "bind", p["overwrite"]
    return request


def unbind_request(models, p, domain):
    request = models.BindSecurityTemplateToEntityRequest()
    request.ZoneId, request.TemplateId = p["zone_id"], p["template_id"]
    request.Entities, request.Operate = [domain], "unbind-" + p["unbind_policy"]
    return request


def get_bindings(module, client, models, p):
    response = module.sdk_call(client.DescribeSecurityTemplateBindings, describe_request(models, p))
    result = []
    for binding in response.SecurityTemplate or []:
        if binding.TemplateId != p["template_id"]:
            continue
        for scope in binding.TemplateScope or []:
            if scope.ZoneId != p["zone_id"]:
                continue
            result.extend(item._serialize(allow_none=True) for item in scope.EntityStatus or [])
    return result


def active_domains(bindings):
    return sorted(set(item.get("Entity") for item in bindings if item.get("Entity") and item.get("Status") in ("online", "process", "pending")))


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "zone_id": {"required": True},
            "template_id": {"required": True},
            "domains": {"type": "list", "elements": "str", "required": True},
            "overwrite": {"type": "bool", "default": True},
            "unbind_policy": {"choices": ["keep-policy", "use-default"], "default": "keep-policy"},
        },
        supports_check_mode=True,
    )
    p = module.params
    if len(p["domains"]) != len(set(p["domains"])):
        module.fail_json(msg="domains must not contain duplicates")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TeoClient, "teo.tencentcloudapi.com")
    try:
        bindings = get_bindings(module, client, models, p)
        before = active_domains(bindings)
        target = sorted(p["domains"])
        if before == target:
            module.exit_json(changed=False, bindings=bindings)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            missing, extra = sorted(set(target) - set(before)), sorted(set(before) - set(target))
            if missing:
                module.sdk_call(client.BindSecurityTemplateToEntity, bind_request(models, p, missing))
            for domain in extra:
                module.sdk_call(client.BindSecurityTemplateToEntity, unbind_request(models, p, domain))
            bindings = get_bindings(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), bindings=bindings)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
