#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tione_model_service_auth_token
short_description: Manage Tencent Cloud TIONE model service authentication tokens
version_added: "0.14.0"
description:
  - Creates, discovers, updates, rotates and deletes service-group authentication tokens.
  - Stable C(token_id) is preferred; exact C(name) lookup rejects ambiguous matches.
  - Rotation is idempotently authorized with C(rotate_from_token_id). The token value is removed from results unless explicitly requested.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired token presence.}
  service_group_id: {type: str, required: true, description: Stable online service-group ID.}
  project_id: {type: str, description: Optional TI workspace ID used to read token inventory.}
  token_id: {type: str, description: Stable token ID for update or deletion.}
  name: {type: str, description: Exact token name; required for creation.}
  description: {type: str, description: Token description.}
  limits: {type: list, elements: dict, description: AuthTokenLimit-compatible rate limits.}
  rotate_from_token_id: {type: str, description: Rotate only while the current token ID equals this value.}
  show_token_value: {type: bool, default: false, description: Include the sensitive generated token value in the result.}
  allow_delete: {type: bool, default: false, description: Explicit destructive-operation guard.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tione_model_service_auth_token:
    service_group_id: ms-group-xxxxxxxx
    name: production-client
    limits:
      - {Strategy: PerMinute, Max: 1200}

- susunola.tencentcloud.tione_model_service_auth_token:
    service_group_id: ms-group-xxxxxxxx
    token_id: token-current-id
    rotate_from_token_id: token-current-id
    show_token_value: true
  no_log: true
"""
RETURN = r"""
auth_token: {description: 'Effective token metadata, with Value removed by default.', type: dict, returned: always}
token_id: {description: Stable token ID., type: str, returned: when available}
"""

import copy
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tione.v20211111 import models, tione_client

    return models, tione_client


def _model(cls, value):
    item = cls()
    item.from_json_string(json.dumps(value))
    return item


def group_request(models, p):
    request = models.DescribeModelServiceGroupRequest()
    request.ServiceGroupId = p["service_group_id"]
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    return request


def tokens(module, client, models, p):
    response = module.sdk_call(client.DescribeModelServiceGroup, group_request(models, p))
    group = response.ServiceGroup
    if not group:
        module.fail_json(msg="TIONE service group does not exist", service_group_id=p["service_group_id"])
    value = group._serialize(allow_none=True)
    return value.get("AuthTokens") or []


def find(module, values, p):
    if p.get("token_id"):
        return next((item for item in values if (item.get("Base") or {}).get("Id") == p["token_id"]), None)
    matches = [item for item in values if (item.get("Base") or {}).get("Name") == p.get("name")]
    if len(matches) > 1:
        module.fail_json(msg="Multiple TIONE auth tokens matched the exact name", name=p.get("name"))
    return matches[0] if matches else None


def normalized_limits(values):
    return sorted((dict(item) for item in (values or [])), key=lambda x: (str(x.get("Strategy") or ""), int(x.get("Max") or 0)))


def desired(p, current=None):
    value = copy.deepcopy(current or {"Base": {}})
    base = value.setdefault("Base", {})
    if p.get("name") is not None:
        base["Name"] = p["name"]
    if p.get("description") is not None:
        base["Description"] = p["description"]
    if p.get("limits") is not None:
        value["Limits"] = normalized_limits(p["limits"])
    return value


def sanitize(value, show=False):
    result = copy.deepcopy(value)
    if result and not show:
        (result.get("Base") or {}).pop("Value", None)
    return result


def create_request(models, p):
    request = models.CreateModelServiceAuthTokenRequest()
    request.ServiceGroupId = p["service_group_id"]
    request.Name = p["name"]
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    if p.get("description") is not None:
        request.Description = p["description"]
    return request


def modify_request(models, p, current, rotate):
    request = models.ModifyModelServiceAuthTokenRequest()
    request.ServiceGroupId = p["service_group_id"]
    request.NeedReset = rotate
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    request.AuthToken = _model(models.AuthToken, desired(p, current))
    return request


def delete_request(models, p, current):
    request = models.DeleteModelServiceAuthTokenRequest()
    request.ServiceGroupId = p["service_group_id"]
    if p.get("project_id") is not None:
        request.TiProjectId = p["project_id"]
    request.AuthTokenValue = (current.get("Base") or {}).get("Value")
    return request


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "service_group_id": {"required": True},
        "project_id": {},
        "token_id": {},
        "name": {},
        "description": {},
        "limits": {"type": "list", "elements": "dict"},
        "rotate_from_token_id": {"no_log": True},
        "show_token_value": {"type": "bool", "default": False},
        "allow_delete": {"type": "bool", "default": False},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if not (p.get("token_id") or p.get("name")):
        module.fail_json(msg="token_id or name is required")
    if p["state"] == "absent" and not p.get("token_id"):
        module.fail_json(msg="token_id is required for safe deletion")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TioneClient, "tione.tencentcloudapi.com")
    try:
        current = find(module, tokens(module, client, models, p), p)
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, auth_token=None, token_id=p["token_id"])
            if not p["allow_delete"]:
                module.fail_json(msg="allow_delete=true is required to delete a TIONE auth token", auth_token=sanitize(current))
            if not (current.get("Base") or {}).get("Value"):
                module.fail_json(msg="TIONE did not return the token value required by its delete API", token_id=p["token_id"])
            diff_value = maybe_diff(module, sanitize(current), None)
            if not module.check_mode:
                module.sdk_call(client.DeleteModelServiceAuthToken, delete_request(models, p, current))
            module.exit_json(changed=True, **(diff_value or {}), auth_token=None, token_id=p["token_id"])
        if current is None:
            if p.get("token_id"):
                module.fail_json(msg="requested token_id does not exist", token_id=p["token_id"])
            target = desired(p)
            diff_value = maybe_diff(module, None, sanitize(target))
            token_id = None
            if not module.check_mode:
                module.sdk_call(client.CreateModelServiceAuthToken, create_request(models, p))
                current = find(module, tokens(module, client, models, p), p)
                if current is None:
                    module.fail_json(msg="created TIONE auth token was not returned by service-group discovery", name=p["name"])
                token_id = (current.get("Base") or {}).get("Id")
                if p.get("limits") is not None:
                    p = dict(p, token_id=token_id)
                    module.sdk_call(client.ModifyModelServiceAuthToken, modify_request(models, p, current, False))
                    current = find(module, tokens(module, client, models, p), p)
            module.exit_json(
                changed=True, **(diff_value or {}), auth_token=sanitize(current if not module.check_mode else target, p["show_token_value"]), token_id=token_id
            )
        current_id = (current.get("Base") or {}).get("Id")
        rotate = p.get("rotate_from_token_id") == current_id
        target = desired(p, current)
        config_drift = sanitize(current) != sanitize(target)
        if not config_drift and not rotate:
            module.exit_json(changed=False, auth_token=sanitize(current, p["show_token_value"]), token_id=current_id)
        diff_value = maybe_diff(module, sanitize(current), sanitize(target))
        if not module.check_mode:
            module.sdk_call(client.ModifyModelServiceAuthToken, modify_request(models, p, current, rotate))
            lookup = dict(p, token_id=None, name=(target.get("Base") or {}).get("Name"))
            current = find(module, tokens(module, client, models, lookup), lookup)
            if current is None:
                module.fail_json(msg="updated TIONE auth token was not returned by service-group discovery")
            current_id = (current.get("Base") or {}).get("Id")
        module.exit_json(
            changed=True, **(diff_value or {}), auth_token=sanitize(current if not module.check_mode else target, p["show_token_value"]), token_id=current_id
        )
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
