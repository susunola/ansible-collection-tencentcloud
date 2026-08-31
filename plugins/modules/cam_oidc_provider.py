#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cam_oidc_provider
short_description: Manage Tencent Cloud CAM OIDC identity providers
version_added: "0.14.0"
description: Creates, updates and deletes a CAM OpenID Connect identity provider.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  name: {type: str, required: true, description: OIDC provider name.}
  identity_url: {type: str, description: OIDC issuer URL.}
  client_ids: {type: list, elements: str, description: Exact allowed client ID set.}
  identity_key: {type: str, description: Base64-encoded public signing key.}
  description: {type: str, default: '', description: Provider description.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cam_oidc_provider:
    name: ci-workloads
    identity_url: https://token.actions.githubusercontent.com
    client_ids: [sts.tencentcloudapi.com]
    identity_key: "{{ lookup('file', 'oidc-public.pem') | b64encode }}"
"""
RETURN = r"""oidc_provider: {description: CAM OIDC provider metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cam.v20190116 import cam_client, models

    return models, cam_client


def describe_request(models, name):
    request = models.DescribeOIDCConfigRequest()
    request.Name = name
    return request


def create_request(models, p):
    request = models.CreateOIDCConfigRequest()
    request.IdentityUrl, request.ClientId, request.Name = p["identity_url"], sorted(set(p["client_ids"])), p["name"]
    request.IdentityKey, request.Description = p["identity_key"], p["description"]
    return request


def update_request(models, p):
    request = models.UpdateOIDCConfigRequest()
    request.IdentityUrl, request.ClientId, request.Name = p["identity_url"], sorted(set(p["client_ids"])), p["name"]
    request.IdentityKey, request.Description = p["identity_key"], p["description"]
    return request


def delete_request(models, name):
    request = models.DeleteOIDCConfigRequest()
    request.Name = name
    return request


def find(module, client, models, name):
    try:
        response = module.sdk_call(client.DescribeOIDCConfig, describe_request(models, name))
        value = response._serialize(allow_none=True)
        return value if value.get("Name") == name and int(value.get("Status") or 0) != 0 else None
    except Exception as exc:
        if is_not_found(exc):
            return None
        raise


def comparable(value):
    return {
        "Name": value.get("Name"),
        "IdentityUrl": value.get("IdentityUrl"),
        "ClientId": sorted(set(value.get("ClientId") or [])),
        "IdentityKey": value.get("IdentityKey"),
        "Description": value.get("Description") or "",
    }


def desired(p):
    return {
        "Name": p["name"],
        "IdentityUrl": p["identity_url"],
        "ClientId": sorted(set(p["client_ids"])),
        "IdentityKey": p["identity_key"],
        "Description": p["description"],
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "name": {"required": True},
            "identity_url": {},
            "client_ids": {"type": "list", "elements": "str"},
            "identity_key": {"no_log": False},
            "description": {"default": ""},
        },
        required_if=[("state", "present", ["identity_url", "client_ids", "identity_key"])],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CamClient, "cam.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["name"])
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, oidc_provider=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteOIDCConfig, delete_request(models, p["name"]))
            module.exit_json(changed=True, **(diff or {}), oidc_provider=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, oidc_provider=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(
                client.UpdateOIDCConfig if current else client.CreateOIDCConfig, update_request(models, p) if current else create_request(models, p)
            )
            current = find(module, client, models, p["name"])
        module.exit_json(changed=True, **(diff or {}), oidc_provider=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
