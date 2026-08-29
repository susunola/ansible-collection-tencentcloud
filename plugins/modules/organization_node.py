#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: organization_node
short_description: Manage Tencent Cloud Organization nodes
version_added: "0.14.0"
description: Creates, renames and deletes organizational units in Tencent Cloud Organization.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  node_id: {description: Existing organization node ID., type: int}
  parent_node_id: {description: Parent organization node ID., type: int}
  name: {description: Organization node name., type: str}
  remark: {description: Organization node remark., type: str, default: ''}
  tags: {description: Tags assigned when creating the node., type: dict, default: {}}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.organization_node:
    parent_node_id: 1001
    name: Production
    remark: Production business units
    tags:
      environment: production
'''
RETURN = r'''
node: {description: Organization node metadata., type: dict, returned: always}
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_organization():
    from tencentcloud.organization.v20210331 import models, organization_client

    return models, organization_client


def build_tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        item = models.Tag()
        item.TagKey, item.TagValue = str(key), str(value)
        result.append(item)
    return result


def build_describe_request(models, offset=0):
    request = models.DescribeOrganizationNodesRequest()
    request.Offset, request.Limit = offset, 50
    return request


def build_create_request(models, params):
    request = models.AddOrganizationNodeRequest()
    request.ParentNodeId, request.Name = params["parent_node_id"], params["name"]
    request.Remark, request.Tags = params["remark"], build_tags(models, params["tags"])
    return request


def build_update_request(models, node_id, params):
    request = models.UpdateOrganizationNodeRequest()
    request.NodeId, request.Name, request.Remark = node_id, params["name"], params["remark"]
    return request


def build_delete_request(models, node_id):
    request = models.DeleteOrganizationNodesRequest()
    request.NodeId = [node_id]
    return request


def find_node(module, client, models, node_id=None, parent_node_id=None, name=None):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeOrganizationNodes, build_describe_request(models, offset))
        items = list(response.Items or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if (node_id and value.get("NodeId") == node_id) or (not node_id and value.get("ParentNodeId") == parent_node_id and value.get("Name") == name):
                matches.append(value)
        offset += len(items)
        if not items or offset >= int(response.Total or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple Organization nodes have the requested name under the parent", name=name, parent_node_id=parent_node_id)
    return matches[0] if matches else None


def _tags(values):
    return {x.get("TagKey"): x.get("TagValue") for x in (values or [])}


def _desired(params):
    return {
        "ParentNodeId": params["parent_node_id"],
        "Name": params["name"],
        "Remark": params["remark"],
        "Tags": {str(k): str(v) for k, v in params["tags"].items()},
    }


def _matches(current, desired):
    return all((_tags(current.get(key)) if key == "Tags" else current.get(key)) == value for key, value in desired.items())


def wait_for_node(module, client, models, node_id, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_node(module, client, models, node_id, None, None)
        if absent and current is None:
            return None
        if not absent and current and _matches(current, desired):
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for Organization node convergence", node=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "node_id": {"type": "int"},
            "parent_node_id": {"type": "int"},
            "name": {"type": "str"},
            "remark": {"type": "str", "default": ""},
            "tags": {"type": "dict", "default": {}},
        },
        required_one_of=[("node_id", "name")],
        required_if=[("state", "present", ("parent_node_id", "name"))],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, client_module = _load_organization()
    client = module.create_client(client_module.OrganizationClient, "organization.tencentcloudapi.com")
    try:
        current = find_node(module, client, models, p["node_id"], p["parent_node_id"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, node=None, msg="Organization node is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), node=current, msg="Would delete Organization node")
            module.sdk_call(client.DeleteOrganizationNodes, build_delete_request(models, current["NodeId"]))
            wait_for_node(module, client, models, current["NodeId"], absent=True)
            module.exit_json(changed=True, **(diff or {}), node=None, msg="Organization node deleted")
        desired = _desired(p)
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), node=None, msg="Would create Organization node")
            response = module.sdk_call(client.AddOrganizationNode, build_create_request(models, p))
            current = wait_for_node(module, client, models, response.NodeId, desired)
            module.exit_json(changed=True, **(diff or {}), node=current, msg="Organization node created")
        if current.get("ParentNodeId") != desired["ParentNodeId"]:
            module.fail_json(
                msg="Organization node parent cannot be changed; recreate the node",
                current_parent_node_id=current.get("ParentNodeId"),
                requested_parent_node_id=desired["ParentNodeId"],
            )
        if _tags(current.get("Tags")) != desired["Tags"]:
            module.fail_json(
                msg="Organization node tags cannot be changed by the Organization API; recreate the node",
                current_tags=_tags(current.get("Tags")),
                requested_tags=desired["Tags"],
            )
        if _matches(current, desired):
            module.exit_json(changed=False, node=current, msg="Organization node is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), node=current, msg="Would update Organization node")
        module.sdk_call(client.UpdateOrganizationNode, build_update_request(models, current["NodeId"], p))
        current = wait_for_node(module, client, models, current["NodeId"], desired)
        module.exit_json(changed=True, **(diff or {}), node=current, msg="Organization node updated")
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
