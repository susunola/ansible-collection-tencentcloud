#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tcr_namespace
short_description: Manage Tencent Cloud TCR namespaces
version_added: "0.13.0"
description:
  - Create, update and delete Tencent Cloud TCR (Tencent Container
    Registry) namespaces through the C(tcr.v20190924) API.
  - This module is idempotent. Running it twice leaves the namespace
    unchanged and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
  - A namespace is identified by O(registry_id) plus O(name). The access
    level (O(is_public)) and the vulnerability settings
    (O(is_auto_scan), O(is_prevent_vul), O(severity)) are enforced on
    existing namespaces with V(ModifyNamespace).
options:
  state:
    description:
      - C(present) creates the namespace when it does not exist and
        enforces the access and vulnerability settings on an existing
        namespace.
      - C(absent) deletes the namespace with V(DeleteNamespace).
    type: str
    choices: [present, absent]
    default: present
  registry_id:
    description:
      - ID of the parent TCR enterprise instance, e.g. C(tcr-xxxxxxxx).
    type: str
    required: true
  name:
    description:
      - Name of the namespace, written to
        V(CreateNamespaceRequest.NamespaceName).
      - 2-30 characters, lowercase letters, digits and the separators
        C(.), C(_) and C(-); must not start or end with a separator.
    type: str
    required: true
  is_public:
    description:
      - Whether the namespace is public, written to
        V(CreateNamespaceRequest.IsPublic) and
        V(ModifyNamespaceRequest.IsPublic).
      - C(true) makes the namespace public, C(false) keeps it private.
    type: bool
    default: false
  is_auto_scan:
    description:
      - Whether images are scanned automatically, written to
        V(ModifyNamespaceRequest.IsAutoScan).
      - C(true) scans automatically, C(false) scans manually.
    type: bool
  is_prevent_vul:
    description:
      - Whether vulnerable images are blocked, written to
        V(ModifyNamespaceRequest.IsPreventVUL).
      - C(true) blocks, C(false) does not.
    type: bool
  severity:
    description:
      - Vulnerability level that triggers the block, written to
        V(ModifyNamespaceRequest.Severity).
      - Only meaningful when O(is_prevent_vul=true).
    type: str
    choices: [low, medium, high]
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
  - Requires the C(tencentcloud-sdk-python-tcr) package on the controller.
  - A namespace cannot be deleted while it still contains repositories;
    delete or empty the repositories first.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a private namespace
  susunola.tencentcloud.tcr_namespace:
    region: ap-guangzhou
    state: present
    registry_id: tcr-xxxxxxxx
    name: team-a
    is_public: false

- name: Enable automatic scanning and vulnerability blocking
  susunola.tencentcloud.tcr_namespace:
    region: ap-guangzhou
    state: present
    registry_id: tcr-xxxxxxxx
    name: team-a
    is_auto_scan: true
    is_prevent_vul: true
    severity: high

- name: Delete the namespace
  susunola.tencentcloud.tcr_namespace:
    region: ap-guangzhou
    state: absent
    registry_id: tcr-xxxxxxxx
    name: team-a
'''

RETURN = r'''
namespace:
  description: The namespace as reported by V(DescribeNamespaces) after the
    operation.
  returned: success
  type: dict
  sample:
    Name: team-a
    Public: false
    NamespaceId: ns-xxxxxxxx
    AutoScan: true
    PreventVUL: true
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_tcr():
    from tencentcloud.tcr.v20190924 import models, tcr_client
    return models, tcr_client


def build_describe_request(models, registry_id, name):
    request = models.DescribeNamespacesRequest()
    request.RegistryId = registry_id
    if name:
        request.NamespaceName = name
    request.All = True
    return request


def find_namespace(module, client, models, registry_id, name):
    """Return the matching namespace dict or None."""
    request = build_describe_request(models, registry_id, name)
    response = module.sdk_call(client.DescribeNamespaces, request)
    for item in response.NamespaceList or []:
        current = item._serialize(allow_none=True)
        if current.get("Name") == name:
            return current
    return None


def build_create_request(models, params):
    request = models.CreateNamespaceRequest()
    request.RegistryId = params["registry_id"]
    request.NamespaceName = params["name"]
    request.IsPublic = params["is_public"]
    if params["is_auto_scan"] is not None:
        request.IsAutoScan = params["is_auto_scan"]
    if params["is_prevent_vul"] is not None:
        request.IsPreventVUL = params["is_prevent_vul"]
    if params["severity"] is not None:
        request.Severity = params["severity"]
    return request


def _create(module, client, models, params):
    request = build_create_request(models, params)
    module.sdk_call(client.CreateNamespace, request)


def _update(module, client, models, params):
    request = models.ModifyNamespaceRequest()
    request.RegistryId = params["registry_id"]
    request.NamespaceName = params["name"]
    request.IsPublic = params["is_public"]
    if params["is_auto_scan"] is not None:
        request.IsAutoScan = params["is_auto_scan"]
    if params["is_prevent_vul"] is not None:
        request.IsPreventVUL = params["is_prevent_vul"]
    if params["severity"] is not None:
        request.Severity = params["severity"]
    module.sdk_call(client.ModifyNamespace, request)


def _delete(module, client, models, registry_id, name):
    request = models.DeleteNamespaceRequest()
    request.RegistryId = registry_id
    request.NamespaceName = name
    module.sdk_call(client.DeleteNamespace, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "registry_id": {"type": "str", "required": True},
            "name": {"type": "str", "required": True},
            "is_public": {"type": "bool", "default": False},
            "is_auto_scan": {"type": "bool"},
            "is_prevent_vul": {"type": "bool"},
            "severity": {"type": "str", "choices": ["low", "medium", "high"]},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    registry_id = module.params["registry_id"]
    name = module.params["name"]

    models, tcr_client = _load_tcr()
    client = module.create_client(tcr_client.TcrClient, "tcr.tencentcloudapi.com")

    try:
        current = find_namespace(module, client, models, registry_id, name)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="TCR namespace already absent")
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete TCR namespace")
        _delete(module, client, models, registry_id, name)
        module.exit_json(changed=True, **(diff or {}), namespace=None, msg="TCR namespace deleted")

    # state == present
    if current is None:
        desired = {
            "Name": name,
            "Public": module.params["is_public"],
        }
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create TCR namespace")
        _create(module, client, models, module.params)
        current = find_namespace(module, client, models, registry_id, name)
        module.exit_json(changed=True, **(diff or {}), namespace=current, msg="TCR namespace created")

    desired = _desired_settings(module)
    drift = {
        key: value
        for key, value in desired.items()
        if current.get(key) != value
    }
    if drift:
        diff = maybe_diff(module, {key: current.get(key) for key in drift}, drift)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would update TCR namespace settings")
        _update(module, client, models, module.params)
        updated = find_namespace(module, client, models, registry_id, name)
        module.exit_json(changed=True, **(diff or {}), namespace=updated, msg="TCR namespace settings updated")

    module.exit_json(changed=False, namespace=current, msg="TCR namespace is up to date")


def _desired_settings(module):
    """Return the settings enforced on an existing namespace."""
    desired = {"Public": module.params["is_public"]}
    if module.params["is_auto_scan"] is not None:
        desired["AutoScan"] = module.params["is_auto_scan"]
    if module.params["is_prevent_vul"] is not None:
        desired["PreventVUL"] = module.params["is_prevent_vul"]
    if module.params["severity"] is not None:
        desired["Severity"] = module.params["severity"]
    return desired


def main():
    run_module()


if __name__ == "__main__":
    main()
