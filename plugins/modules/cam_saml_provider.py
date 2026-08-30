#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: cam_saml_provider
short_description: Manage Tencent Cloud CAM SAML identity providers
version_added: "0.14.0"
description: Creates, updates and deletes a CAM SAML identity provider with canonical metadata comparison.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  name: {type: str, required: true, description: SAML provider name.}
  description: {type: str, default: '', description: Provider description.}
  metadata_document: {type: str, description: Base64-encoded SAML metadata document.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cam_saml_provider:
    name: corporate-idp
    description: Corporate identity provider
    metadata_document: "{{ lookup('file', 'metadata.xml') | b64encode }}"
'''
RETURN = r'''saml_provider: {description: CAM SAML provider metadata., type: dict, returned: always}'''
import base64
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cam.v20190116 import cam_client, models
    return models, cam_client


def get_request(models, name): request = models.GetSAMLProviderRequest(); request.Name = name; return request
def create_request(models, p):
    request = models.CreateSAMLProviderRequest(); request.Name, request.Description, request.SAMLMetadataDocument = p["name"], p["description"], p["metadata_document"]; return request
def update_request(models, p):
    request = models.UpdateSAMLProviderRequest(); request.Name, request.Description, request.SAMLMetadataDocument = p["name"], p["description"], p["metadata_document"]; return request
def delete_request(models, name): request = models.DeleteSAMLProviderRequest(); request.Name = name; return request


def canonical_metadata(value):
    if value is None: return None
    try: return base64.b64decode(value, validate=True).decode("utf-8").strip()
    except Exception: return str(value).strip()


def find(module, client, models, name):
    try:
        response = module.sdk_call(client.GetSAMLProvider, get_request(models, name)); return response._serialize(allow_none=True)
    except Exception as exc:
        if is_not_found(exc): return None
        raise


def comparable(value): return {"Name": value.get("Name"), "Description": value.get("Description") or "", "SAMLMetadata": canonical_metadata(value.get("SAMLMetadata"))}
def desired(p): return {"Name": p["name"], "Description": p["description"], "SAMLMetadata": canonical_metadata(p["metadata_document"])}


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "name": {"required": True}, "description": {"default": ""}, "metadata_document": {}}, required_if=[("state", "present", ["metadata_document"])], supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.CamClient, "cam.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["name"])
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, saml_provider=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteSAMLProvider, delete_request(models, p["name"]))
            module.exit_json(changed=True, **(diff or {}), saml_provider=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target: module.exit_json(changed=False, saml_provider=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            module.sdk_call(client.UpdateSAMLProvider if current else client.CreateSAMLProvider, update_request(models, p) if current else create_request(models, p)); current = find(module, client, models, p["name"])
        module.exit_json(changed=True, **(diff or {}), saml_provider=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
