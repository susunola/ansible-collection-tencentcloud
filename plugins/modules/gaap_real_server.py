#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: gaap_real_server
short_description: Manage Tencent Cloud GAAP real servers
version_added: "0.14.0"
description: Registers, renames and explicitly removes reusable GAAP origin identities.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  real_server_id:
    description:
      - Existing real-server ID.
    type: str
  address:
    description:
      - Exact origin IP address or domain.
    type: str
  name:
    description:
      - Origin display name.
    type: str
  project_id:
    description:
      - Tencent Cloud project ID.
    type: int
    default: 0
  allow_shared_delete:
    description:
      - Authorize global removal, which can affect every listener using this origin.
    type: bool
    default: false
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
  - module: susunola.tencentcloud.gaap_real_server_info
    description: Gather information about Tencent Cloud GAAP real servers.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.gaap_real_server:
    address: 10.0.1.10
    name: orders-primary

- name: Delete the real server
  susunola.tencentcloud.gaap_real_server:
    state: absent
    address: 10.0.1.10
    allow_shared_delete: true
"""
RETURN = r"""real_server:
  description:
    - Effective GAAP real server.
  returned: always
  type: dict"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.gaap.v20180529 import models, gaap_client

    return models, gaap_client


def find(module, client, models, real_server_id=None, address=None, project_id=-1):
    offset, matches = 0, []
    while True:
        request = models.DescribeRealServersRequest()
        request.ProjectId, request.Offset, request.Limit = project_id, offset, 50
        request.SearchValue = address
        response = module.sdk_call(client.DescribeRealServers, request)
        page = response.RealServerSet or []
        for item in page:
            value = item._serialize(allow_none=True)
            if (real_server_id and value.get("RealServerId") == real_server_id) or (not real_server_id and value.get("RealServerIP") == address):
                matches.append(value)
        offset += len(page)
        if real_server_id or not page or offset >= int(response.TotalCount or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple GAAP real servers have the requested address; specify real_server_id")
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "real_server_id": {},
            "address": {},
            "name": {},
            "project_id": {"type": "int", "default": 0},
            "allow_shared_delete": {"type": "bool", "default": False},
        },
        required_one_of=[("real_server_id", "address")],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.GaapClient, "gaap.tencentcloudapi.com")
    try:
        current = find(module, client, models, p.get("real_server_id"), p.get("address"), p["project_id"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, real_server=None)
            if not p["allow_shared_delete"]:
                module.fail_json(msg="allow_shared_delete=true is required because GAAP real-server removal affects all bindings", real_server=current)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.RemoveRealServersRequest()
                request.RealServerIds = [current["RealServerId"]]
                module.sdk_call(client.RemoveRealServers, request)
            module.exit_json(changed=True, **(diff or {}), real_server=current if module.check_mode else None)
        if current is None:
            if not p.get("address") or not p.get("name"):
                module.fail_json(msg="address and name are required to register a GAAP real server")
            wanted = {"RealServerIP": p["address"], "RealServerName": p["name"], "ProjectId": p["project_id"]}
            diff = maybe_diff(module, None, wanted)
            if not module.check_mode:
                request = models.AddRealServersRequest()
                request.ProjectId, request.RealServerIP, request.RealServerName = p["project_id"], [p["address"]], p["name"]
                response = module.sdk_call(client.AddRealServers, request)
                p["real_server_id"] = response.RealServerSet[0].RealServerId
                current = find(module, client, models, p["real_server_id"], None, p["project_id"])
            module.exit_json(changed=True, **(diff or {}), real_server=current if not module.check_mode else wanted)
        if not p.get("name") or current.get("RealServerName") == p["name"]:
            module.exit_json(changed=False, real_server=current)
        before, wanted = {"RealServerName": current.get("RealServerName")}, {"RealServerName": p["name"]}
        diff = maybe_diff(module, before, wanted)
        if not module.check_mode:
            request = models.ModifyRealServerNameRequest()
            request.RealServerId, request.RealServerName = current["RealServerId"], p["name"]
            module.sdk_call(client.ModifyRealServerName, request)
            current = find(module, client, models, current["RealServerId"], None, p["project_id"])
        module.exit_json(changed=True, **(diff or {}), real_server=current if not module.check_mode else wanted)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
