#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tsf_namespace
short_description: Manage a Tencent Cloud TSF namespace
version_added: "0.15.0"
description: Creates, updates and deletes a TSF namespace with immutable placement protection.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  namespace_id:
    description:
      - Existing namespace ID. When omitted, exact name and cluster are used.
    type: str
  name:
    description:
      - Namespace name.
    type: str
    required: true
  cluster_id:
    description:
      - Cluster ID; required when creating a cluster namespace.
    type: str
  description:
    description:
      - Namespace description.
    type: str
  resource_type:
    description:
      - Namespace resource type, immutable after creation.
    type: str
    choices: [DEF, GW]
  namespace_type:
    description:
      - Namespace type, immutable after creation.
    type: str
    choices: [DEF, GLOBAL]
    default: DEF
  high_availability:
    description:
      - Whether high availability is enabled.
    type: bool
  create_k8s_namespace:
    description:
      - Create the corresponding Kubernetes namespace.
    type: bool
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
attributes:
  check_mode:
    description:
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  diff_mode:
    description:
      - Returns the difference between the observed and the requested state
        when the task runs with C(--diff).
    support: full
  idempotent:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
seealso:
  - module: susunola.tencentcloud.tsf_namespace_info
    description: Gather information about Tencent Cloud TSF namespaces.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- name: Manage a production namespace
  susunola.tencentcloud.tsf_namespace:
    name: production
    cluster_id: cluster-xxxxxxxx
    resource_type: DEF
    high_availability: true

- name: Delete the namespace
  susunola.tencentcloud.tsf_namespace:
    state: absent
    name: production
"""
RETURN = r"""namespace:
  description:
    - Effective namespace metadata.
  returned: always
  type: dict"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, fail_from_sdk_error


def _load():
    from tencentcloud.tsf.v20180326 import models, tsf_client

    return models, tsf_client


def _serialize(value):
    return value._serialize(allow_none=True) if value is not None else None


def find(module, client, models, params):
    request = models.DescribeSimpleNamespacesRequest()
    request.NamespaceId = params.get("namespace_id")
    request.NamespaceName = None if params.get("namespace_id") else params["name"]
    request.ClusterId = params.get("cluster_id")
    request.Offset, request.Limit = 0, 100
    result = module.sdk_call(client.DescribeSimpleNamespaces, request).Result
    items = [_serialize(item) for item in ((result.Content if result else None) or [])]
    if params.get("namespace_id"):
        matches = [item for item in items if item["NamespaceId"] == params["namespace_id"]]
    else:
        matches = [
            item
            for item in items
            if item["NamespaceName"] == params["name"] and (not params.get("cluster_id") or item.get("ClusterId") == params["cluster_id"])
        ]
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSF namespaces matched", name=params["name"], cluster_id=params.get("cluster_id"))
    return matches[0] if matches else None


def desired(params):
    target = {"NamespaceName": params["name"]}
    mapping = {
        "cluster_id": "ClusterId",
        "description": "NamespaceDesc",
        "resource_type": "NamespaceResourceType",
        "namespace_type": "NamespaceType",
        "create_k8s_namespace": "CreateK8sNamespaceFlag",
    }
    for source, key in mapping.items():
        if params.get(source) is not None:
            target[key] = params[source]
    if params.get("high_availability") is not None:
        target["IsHaEnable"] = "1" if params["high_availability"] else "0"
    return target


def comparable(current, target):
    return {key: current.get(key) for key in target if key != "CreateK8sNamespaceFlag"}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "namespace_id": {},
            "name": {"required": True},
            "cluster_id": {},
            "description": {},
            "resource_type": {"choices": ["DEF", "GW"]},
            "namespace_type": {"choices": ["DEF", "GLOBAL"], "default": "DEF"},
            "high_availability": {"type": "bool"},
            "create_k8s_namespace": {"type": "bool"},
        },
        supports_check_mode=True,
    )
    params = module.params
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.TsfClient, "tsf.tencentcloudapi.com")
    try:
        current = find(module, client, models, params)
        if params["state"] == "absent":
            if not current:
                module.exit_json(changed=False, namespace=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.DeleteNamespaceRequest()
                request.NamespaceId, request.ClusterId = current["NamespaceId"], current.get("ClusterId")
                response = module.sdk_call(client.DeleteNamespace, request)
                if response.Result is False:
                    module.fail_json(msg="Tencent Cloud rejected the TSF namespace deletion", request_id=response.RequestId)
            module.exit_json(changed=True, **(diff or {}), namespace=None)
        target = desired(params)
        if not current and params["namespace_type"] != "GLOBAL" and not params.get("cluster_id"):
            module.fail_json(msg="cluster_id is required when creating a non-global TSF namespace")
        if current:
            require_immutable_unchanged(module, current, target, ["ClusterId", "NamespaceResourceType", "NamespaceType"], "TSF namespace")
        compare_target = {key: value for key, value in target.items() if key != "CreateK8sNamespaceFlag"}
        if current and comparable(current, target) == compare_target:
            module.exit_json(changed=False, namespace=current)
        diff = maybe_diff(module, comparable(current, target) if current else None, compare_target)
        if not module.check_mode:
            if current:
                request = models.ModifyNamespaceRequest()
                request.NamespaceId = current["NamespaceId"]
                for key in ("NamespaceName", "NamespaceDesc", "IsHaEnable"):
                    if key in target:
                        setattr(request, key, target[key])
                response = module.sdk_call(client.ModifyNamespace, request)
                if response.Result is False:
                    module.fail_json(msg="Tencent Cloud rejected the TSF namespace update", request_id=response.RequestId)
                params["namespace_id"] = current["NamespaceId"]
            else:
                request = models.CreateNamespaceRequest()
                for key, value in target.items():
                    setattr(request, key, value)
                response = module.sdk_call(client.CreateNamespace, request)
                params["namespace_id"] = response.Result
            current = find(module, client, models, params)
        module.exit_json(changed=True, **(diff or {}), namespace=current if not module.check_mode else target)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
