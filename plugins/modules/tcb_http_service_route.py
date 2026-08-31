#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tcb_http_service_route
short_description: Manage Tencent CloudBase HTTP service domain routes
version_added: "0.14.0"
description: Creates, updates and deletes an HTTP service domain and its route configuration.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  env_id: {type: str, required: true, description: CloudBase environment ID.}
  domain: {type: str, required: true, description: Custom domain used as the resource identity.}
  domain_config: {type: dict, description: SDK HTTPServiceDomainParam payload including routes and certificate settings.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tcb_http_service_route:
    env_id: env-xxxxxxxx
    domain: api.example.com
    domain_config:
      Domain: api.example.com
      Protocol: https
      Routes:
        - {Path: /api, UpstreamResourceType: cloudrun, UpstreamResourceName: backend}
"""
RETURN = r"""route: {description: Effective domain and route metadata., type: dict, returned: always}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tcb.v20180608 import models, tcb_client

    return models, tcb_client


def _model(models, value):
    x = models.HTTPServiceDomainParam()
    x.from_json_string(json.dumps(value))
    return x


def describe_request(models, env_id, offset=0):
    r = models.DescribeHTTPServiceRouteRequest()
    r.EnvId = env_id
    r.Offset, r.Limit = offset, 100
    return r


def create_request(models, p, target):
    r = models.CreateHTTPServiceRouteRequest()
    r.EnvId = p["env_id"]
    r.Domain = _model(models, target)
    return r


def update_request(models, p, target):
    r = models.ModifyHTTPServiceRouteRequest()
    r.EnvId = p["env_id"]
    r.Domain = _model(models, target)
    return r


def delete_request(models, p):
    r = models.DeleteHTTPServiceRouteRequest()
    r.EnvId, r.Domain, r.Paths = p["env_id"], p["domain"], None
    return r


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        response = module.sdk_call(client.DescribeHTTPServiceRoute, describe_request(models, p["env_id"], offset))
        page = response.Domains or []
        for item in page:
            value = item._serialize(allow_none=True)
            if value.get("Domain") == p["domain"]:
                matches.append(value)
        offset += len(page)
        if not page or offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple CloudBase HTTP service domains matched", domain=p["domain"])
    return matches[0] if matches else None


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and contains(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(contains(a, e) for a, e in zip(actual, expected))
    return actual == expected


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "env_id": {"required": True},
            "domain": {"required": True},
            "domain_config": {"type": "dict"},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TcbClient, "tcb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, route=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteHTTPServiceRoute, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), route=None)
        if not p.get("domain_config"):
            module.fail_json(msg="domain_config is required when state is present")
        target = dict(p["domain_config"])
        if target.get("Domain") not in (None, p["domain"]):
            module.fail_json(msg="domain_config.Domain must match domain")
        target["Domain"] = p["domain"]
        if current and contains(current, target):
            module.exit_json(changed=False, route=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(
                client.ModifyHTTPServiceRoute if current else client.CreateHTTPServiceRoute,
                update_request(models, p, target) if current else create_request(models, p, target),
            )
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), route=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
