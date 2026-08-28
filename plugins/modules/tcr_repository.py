#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tcr_repository
short_description: Manage a Tencent Cloud TCR repository
version_added: "0.13.0"
description:
  - Creates, updates and deletes repositories in an Enterprise Edition TCR registry.
  - A repository is identified by C(registry_id), C(namespace) and C(name).
options:
  state:
    description: Desired repository lifecycle state.
    choices: [present, absent]
    default: present
    type: str
  registry_id:
    description: ID of the parent TCR Enterprise Edition registry.
    required: true
    type: str
  namespace:
    description: Name of the parent TCR namespace.
    required: true
    type: str
  name:
    description: Repository name.
    required: true
    type: str
  brief_description:
    description: Short repository summary.
    type: str
    default: ''
  description:
    description: Full repository description.
    type: str
    default: ''
  force_delete:
    description: Delete the repository even when it contains images.
    type: bool
    default: false
  retries: {description: Number of retries for transient SDK failures., type: int, default: 5}
  waiter_delay: {description: Seconds between state-polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent value appended to SDK requests., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

import json

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff

EXAMPLES = r'''
- name: Manage an application repository
  susunola.tencentcloud.tcr_repository:
    registry_id: tcr-abc123
    namespace: production
    name: api
    brief_description: Production API images

- name: Remove it and all images
  susunola.tencentcloud.tcr_repository:
    state: absent
    registry_id: tcr-abc123
    namespace: production
    name: api
    force_delete: true
'''

RETURN = r'''
repository:
  description: Repository returned by Tencent Cloud, or null after deletion.
  type: dict
  returned: always
'''


def _load_tcr():
    from tencentcloud.tcr.v20190924 import models, tcr_client

    return models, tcr_client


def _as_dict(value):
    if value is None:
        return None
    return json.loads(value.to_json_string())


def find_repository(module, client, models, registry_id, namespace, name):
    request = models.DescribeRepositoriesRequest()
    request.RegistryId = registry_id
    request.NamespaceName = namespace
    request.RepositoryName = name
    request.Limit = 100
    response = module.sdk_call(client.DescribeRepositories, request)
    for repository in getattr(response, "RepositoryList", None) or []:
        item = _as_dict(repository)
        if item.get("Name") == name or item.get("RepositoryName") == name:
            return item
    return None


def build_create_request(models, params):
    request = models.CreateRepositoryRequest()
    request.RegistryId = params["registry_id"]
    request.NamespaceName = params["namespace"]
    request.RepositoryName = params["name"]
    request.BriefDescription = params["brief_description"]
    request.Description = params["description"]
    return request


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "registry_id": {"type": "str", "required": True},
            "namespace": {"type": "str", "required": True},
            "name": {"type": "str", "required": True},
            "brief_description": {"type": "str", "default": ""},
            "description": {"type": "str", "default": ""},
            "force_delete": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    module.require_sdk()
    models, tcr_client = _load_tcr()
    client = module.create_client(tcr_client.TcrClient, "tcr.tencentcloudapi.com")
    p = module.params
    try:
        current = find_repository(module, client, models, p["registry_id"], p["namespace"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, repository=None, msg="TCR repository already absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), repository=current, msg="Would delete TCR repository")
            request = models.DeleteRepositoryRequest()
            request.RegistryId, request.NamespaceName = p["registry_id"], p["namespace"]
            request.RepositoryName, request.ForceDelete = p["name"], p["force_delete"]
            module.sdk_call(client.DeleteRepository, request)
            module.exit_json(changed=True, **(diff or {}), repository=None, msg="TCR repository deleted")

        desired = {"Name": p["name"], "BriefDescription": p["brief_description"], "Description": p["description"]}
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), repository=None, msg="Would create TCR repository")
            module.sdk_call(client.CreateRepository, build_create_request(models, p))
            current = find_repository(module, client, models, p["registry_id"], p["namespace"], p["name"])
            module.exit_json(changed=True, **(diff or {}), repository=current, msg="TCR repository created")

        drift = any((current.get(k) or "") != v for k, v in (("BriefDescription", p["brief_description"]), ("Description", p["description"])))
        if not drift:
            module.exit_json(changed=False, repository=current, msg="TCR repository is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), repository=current, msg="Would update TCR repository")
        request = models.ModifyRepositoryRequest()
        request.RegistryId, request.NamespaceName, request.RepositoryName = p["registry_id"], p["namespace"], p["name"]
        request.BriefDescription, request.Description = p["brief_description"], p["description"]
        module.sdk_call(client.ModifyRepository, request)
        current = find_repository(module, client, models, p["registry_id"], p["namespace"], p["name"])
        module.exit_json(changed=True, **(diff or {}), repository=current, msg="TCR repository updated")
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )


def main():
    run_module()


if __name__ == "__main__":
    main()
