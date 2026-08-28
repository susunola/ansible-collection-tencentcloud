#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: scf_alias
short_description: Manage Tencent Cloud SCF function aliases
version_added: "0.13.0"
description:
  - Create, update and delete Tencent Cloud SCF (Serverless Cloud
    Function) aliases through the C(scf.v20180416) API.
  - This module is idempotent. Running it twice leaves the alias unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
  - An alias is identified by O(function_name) plus O(name). The target
    version (O(function_version)) and O(description) are enforced on an
    existing alias with V(UpdateAlias).
options:
  state:
    description:
      - C(present) creates the alias when it does not exist and enforces
        the target version and description on an existing alias.
      - C(absent) deletes the alias with V(DeleteAlias).
    type: str
    choices: [present, absent]
    default: present
  function_name:
    description:
      - Name of the function the alias belongs to, written to
        V(CreateAliasRequest.FunctionName).
    type: str
    required: true
  name:
    description:
      - Name of the alias, unique within the function, written to
        V(CreateAliasRequest.Name).
      - 1-64 characters; letters, digits, C(_) and C(-); must start with a
        letter.
    type: str
    required: true
  function_version:
    description:
      - Main version the alias points to, written to
        V(CreateAliasRequest.FunctionVersion) and
        V(UpdateAliasRequest.FunctionVersion).
      - Required when creating the alias.
    type: str
  namespace:
    description:
      - Namespace of the function, written to
        V(CreateAliasRequest.Namespace).
      - Defaults to C(default) when not given.
    type: str
    default: default
  description:
    description:
      - Description of the alias, written to
        V(CreateAliasRequest.Description) and
        V(UpdateAliasRequest.Description).
    type: str
  retries:
    description: Number of retries for transient SDK failures.
    type: int
    default: 5
  waiter_delay:
    description: Seconds to wait between state-polling attempts.
    type: int
    default: 5
  waiter_timeout:
    description: Overall timeout in seconds for state polling.
    type: int
    default: 120
  user_agent:
    description:
      - Value appended to the SDK User-Agent header so API usage can be
        attributed to this collection.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-scf) package on the controller.
  - Weighted routing to an additional version is not exposed in this
    version of the module; use the console or the SDK directly for
    V(UpdateAliasRequest.RoutingConfig).
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Point an alias at version 2
  susunola.tencentcloud.scf_alias:
    region: ap-guangzhou
    state: present
    function_name: my-func
    name: prod
    function_version: 2
    description: Production traffic

- name: Move the alias to version 3
  susunola.tencentcloud.scf_alias:
    region: ap-guangzhou
    state: present
    function_name: my-func
    name: prod
    function_version: 3

- name: Delete the alias
  susunola.tencentcloud.scf_alias:
    region: ap-guangzhou
    state: absent
    function_name: my-func
    name: prod
'''

RETURN = r'''
alias:
  description: The alias as reported by V(GetAlias) after the operation.
  returned: success
  type: dict
  sample:
    Name: prod
    FunctionVersion: 2
    Description: Production traffic
    AddTime: "2026-08-28 10:00:00"
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_scf():
    from tencentcloud.scf.v20180416 import models, scf_client
    return models, scf_client


def build_get_request(models, params):
    request = models.GetAliasRequest()
    request.FunctionName = params["function_name"]
    request.Name = params["name"]
    request.Namespace = params["namespace"]
    return request


def find_alias(module, client, models, params):
    """Return the matching alias dict or None."""
    request = build_get_request(models, params)
    response = module.sdk_call(client.GetAlias, request)
    return response._serialize(allow_none=True)


def build_create_request(models, params):
    request = models.CreateAliasRequest()
    request.FunctionName = params["function_name"]
    request.Name = params["name"]
    request.FunctionVersion = params["function_version"]
    request.Namespace = params["namespace"]
    if params["description"] is not None:
        request.Description = params["description"]
    return request


def _create(module, client, models, params):
    request = build_create_request(models, params)
    module.sdk_call(client.CreateAlias, request)


def _update(module, client, models, params):
    request = models.UpdateAliasRequest()
    request.FunctionName = params["function_name"]
    request.Name = params["name"]
    request.FunctionVersion = params["function_version"]
    request.Namespace = params["namespace"]
    if params["description"] is not None:
        request.Description = params["description"]
    module.sdk_call(client.UpdateAlias, request)


def _delete(module, client, models, params):
    request = models.DeleteAliasRequest()
    request.FunctionName = params["function_name"]
    request.Name = params["name"]
    request.Namespace = params["namespace"]
    module.sdk_call(client.DeleteAlias, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "function_name": {"type": "str", "required": True},
            "name": {"type": "str", "required": True},
            "function_version": {"type": "str"},
            "namespace": {"type": "str", "default": "default"},
            "description": {"type": "str"},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    if not module.params["function_version"]:
        module.fail_json(msg="function_version is required to identify the alias target")

    models, scf_client = _load_scf()
    client = module.create_client(scf_client.ScfClient, "scf.tencentcloudapi.com")

    try:
        current = find_alias(module, client, models, module.params)
    except Exception as exc:
        if _is_not_found(exc):
            current = None
        else:
            module.fail_json(
                msg="Tencent Cloud API request failed",
                error=str(exc),
                error_code=getattr(exc, "get_code", lambda: None)(),
                request_id=getattr(exc, "get_request_id", lambda: None)(),
            )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="SCF alias already absent")
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete SCF alias")
        _delete(module, client, models, module.params)
        module.exit_json(changed=True, **(diff or {}), alias=None, msg="SCF alias deleted")

    # state == present
    if current is None:
        desired = {
            "Name": module.params["name"],
            "FunctionVersion": module.params["function_version"],
            "Description": module.params["description"] or "",
        }
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create SCF alias")
        _create(module, client, models, module.params)
        current = find_alias(module, client, models, module.params)
        module.exit_json(changed=True, **(diff or {}), alias=current, msg="SCF alias created")

    drift = {}
    if current.get("FunctionVersion") != module.params["function_version"]:
        drift["FunctionVersion"] = module.params["function_version"]
    if current.get("Description") != (module.params["description"] or ""):
        drift["Description"] = module.params["description"] or ""
    if drift:
        diff = maybe_diff(
            module,
            {key: current.get(key) for key in drift},
            drift,
        )
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would update SCF alias")
        _update(module, client, models, module.params)
        updated = find_alias(module, client, models, module.params)
        module.exit_json(changed=True, **(diff or {}), alias=updated, msg="SCF alias updated")

    module.exit_json(changed=False, alias=current, msg="SCF alias is up to date")


def _is_not_found(exc):
    """Return True when the SDK reports the alias does not exist."""
    from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
    return is_not_found(exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
