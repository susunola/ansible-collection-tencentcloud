#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: scf_version
short_description: Manage Tencent Cloud SCF function versions
version_added: "0.13.0"
description:
  - Publish and delete Tencent Cloud SCF (Serverless Cloud Function)
    versions through the C(scf.v20180416) API.
  - This module is idempotent. Publishing an already-existing version
    reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
  - A version is identified by O(function_name) plus O(version). The
    C(present) state publishes a snapshot of the current C(\$LATEST) code
    with V(PublishVersion) when the version does not exist; the C(absent)
    state deletes it with V(DeleteFunctionVersion).
options:
  state:
    description:
      - C(present) publishes the version when it does not exist.
      - C(absent) deletes the version with V(DeleteFunctionVersion).
    type: str
    choices: [present, absent]
    default: present
  function_name:
    description:
      - Name of the function the version belongs to, written to
        V(PublishVersionRequest.FunctionName).
    type: str
    required: true
  version:
    description:
      - Version number to publish or delete, written to
        V(DeleteFunctionVersionRequest.Qualifier).
      - C(\$LATEST) and C(default) cannot be deleted.
    type: str
    required: true
  namespace:
    description:
      - Namespace of the function, written to
        V(PublishVersionRequest.Namespace) and
        V(DeleteFunctionVersionRequest.Namespace).
      - Defaults to C(default) when not given.
    type: str
    default: default
  description:
    description:
      - Description attached to the version when publishing it, written to
        V(PublishVersionRequest.Description).
      - Only applied at publish time; existing versions keep their own
        description.
    type: str
  force_delete:
    description:
      - Force-delete flag, written to
        V(DeleteFunctionVersionRequest.ForceDelete).
      - C(true) directly deletes the container and force-closes functions
        that are still executing.
    type: bool
    default: false
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
  - Publishing a version snapshots the current C(\$LATEST) code; it does
    not wait for any pending deployment to finish.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Publish version 2 of the function
  susunola.tencentcloud.scf_version:
    region: ap-guangzhou
    state: present
    function_name: my-func
    version: 2
    description: Deployed by ansible

- name: Delete version 2
  susunola.tencentcloud.scf_version:
    region: ap-guangzhou
    state: absent
    function_name: my-func
    version: 2
'''

RETURN = r'''
version:
  description: The version as reported by V(ListVersionByFunction) after the
    operation.
  returned: success
  type: dict
  sample:
    Version: 2
    Description: Deployed by ansible
    AddTime: "2026-08-28 10:00:00"
    Status: Active
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_scf():
    from tencentcloud.scf.v20180416 import models, scf_client
    return models, scf_client


def build_list_request(models, params):
    request = models.ListVersionByFunctionRequest()
    request.FunctionName = params["function_name"]
    request.Namespace = params["namespace"]
    request.Limit = 100
    return request


def find_version(module, client, models, params):
    """Return the matching version dict or None."""
    request = build_list_request(models, params)
    response = module.sdk_call(client.ListVersionByFunction, request)
    for item in response.Versions or []:
        current = item._serialize(allow_none=True)
        if str(current.get("Version")) == str(params["version"]):
            return current
    return None


def build_publish_request(models, params):
    request = models.PublishVersionRequest()
    request.FunctionName = params["function_name"]
    request.Namespace = params["namespace"]
    if params["description"] is not None:
        request.Description = params["description"]
    return request


def _publish(module, client, models, params):
    request = build_publish_request(models, params)
    module.sdk_call(client.PublishVersion, request)


def _delete(module, client, models, params):
    request = models.DeleteFunctionVersionRequest()
    request.FunctionName = params["function_name"]
    request.Qualifier = params["version"]
    request.Namespace = params["namespace"]
    if params["force_delete"]:
        request.ForceDelete = True
    module.sdk_call(client.DeleteFunctionVersion, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "function_name": {"type": "str", "required": True},
            "version": {"type": "str", "required": True},
            "namespace": {"type": "str", "default": "default"},
            "description": {"type": "str"},
            "force_delete": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    version = module.params["version"]
    if version in ("$LATEST", "default"):
        module.fail_json(msg="version %s cannot be managed by this module" % version)

    models, scf_client = _load_scf()
    client = module.create_client(scf_client.ScfClient, "scf.tencentcloudapi.com")

    try:
        current = find_version(module, client, models, module.params)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="SCF version already absent")
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete SCF version")
        _delete(module, client, models, module.params)
        module.exit_json(changed=True, **(diff or {}), version=None, msg="SCF version deleted")

    # state == present
    if current is None:
        desired = {"Version": version, "Description": module.params["description"] or ""}
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would publish SCF version")
        _publish(module, client, models, module.params)
        current = find_version(module, client, models, module.params)
        module.exit_json(changed=True, **(diff or {}), version=current, msg="SCF version published")

    module.exit_json(changed=False, version=current, msg="SCF version already exists")


def main():
    run_module()


if __name__ == "__main__":
    main()
