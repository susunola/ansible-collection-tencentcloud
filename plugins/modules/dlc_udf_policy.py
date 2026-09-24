#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_udf_policy
short_description: Reconcile Tencent Cloud DLC UDF access policies
version_added: "0.14.0"
description:
  - Reconciles the complete user and work-group access policy for an exact DLC UDF identity.
  - Access, user and group ordering is normalized and clearing the entire policy requires explicit authorization.
options:
  name:
    description:
      - Exact UDF name.
    type: str
    required: true
  database_name:
    description:
      - Database name or global-function for a global UDF.
    type: str
    required: true
  catalog_name:
    description:
      - Data catalog name.
    type: str
    required: true
  policy_infos:
    type: list
    elements: dict
    required: true
    description: Complete desired UDF policy set.
    suboptions:
      accesses:
        description:
          - Access types such as select, alter or drop.
        type: list
        required: true
        elements: str
      users:
        description:
          - Exact user identity set.
        type: list
        default: []
        elements: str
      groups:
        description:
          - Exact work-group identity set.
        type: list
        default: []
        elements: str
  allow_empty:
    description:
      - Explicitly authorize clearing every UDF policy entry.
    type: bool
    default: false
  wait:
    description:
      - Wait for readable policy convergence.
    type: bool
    default: true
  waiter_delay:
    description:
      - Seconds between polls.
    type: int
    default: 3
  waiter_timeout:
    description:
      - Overall convergence timeout.
    type: int
    default: 180

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
  idempotency:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_udf_policy:
    catalog_name: DataLakeCatalog
    database_name: analytics
    name: normalize_email
    policy_infos:
      - accesses: [select]
        users: ['100000000001']
        groups: ['2001']

- susunola.tencentcloud.dlc_udf_policy:
    catalog_name: DataLakeCatalog
    database_name: analytics
    name: normalize_email
    policy_infos: []
    allow_empty: true
"""
RETURN = r"""
udf_policy: {description: Effective normalized UDF policy set., type: list, elements: dict, returned: always}
"""

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def normalize(values):
    by_access = {}
    for value in values or []:
        users = set(value.get("Users", value.get("users", [])))
        groups = set(value.get("Groups", value.get("groups", [])))
        for access in set(value.get("Accesses", value.get("accesses", []))):
            entry = by_access.setdefault(access, {"users": set(), "groups": set()})
            entry["users"].update(users)
            entry["groups"].update(groups)
    return [{"Accesses": [access], "Users": sorted(value["users"]), "Groups": sorted(value["groups"])} for access, value in sorted(by_access.items())]


def describe_request(models, p):
    request = models.DescribeUDFPolicyRequest()
    request.Name, request.DatabaseName, request.CatalogName = p["name"], p["database_name"], p["catalog_name"]
    return request


def read(module, client, models, p):
    response = module.sdk_call(client.DescribeUDFPolicy, describe_request(models, p))
    return normalize(x._serialize(allow_none=True) for x in (response.UDFPolicyInfos or []))


def update_request(models, p):
    request = models.UpdateUDFPolicyRequest()
    request.Name, request.DatabaseName, request.CatalogName = p["name"], p["database_name"], p["catalog_name"]
    request.UDFPolicyInfos = []
    for value in normalize(p["policy_infos"]):
        item = models.UDFPolicyInfo()
        item.from_json_string(json.dumps(value))
        request.UDFPolicyInfos.append(item)
    return request


def wait_policy(module, client, models, p, target):
    def poll():
        return "ready" if read(module, client, models, p) == target else "pending"

    wait_for_state(module, poll, ["ready"], timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    info = {
        "accesses": {"type": "list", "elements": "str", "required": True},
        "users": {"type": "list", "elements": "str", "default": []},
        "groups": {"type": "list", "elements": "str", "default": []},
    }
    spec = {
        "name": {"required": True},
        "database_name": {"required": True},
        "catalog_name": {"required": True},
        "policy_infos": {"type": "list", "elements": "dict", "required": True, "options": info},
        "allow_empty": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 3},
        "waiter_timeout": {"type": "int", "default": 180},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    target = normalize(p["policy_infos"])
    if not target and not p["allow_empty"]:
        module.fail_json(msg="set allow_empty=true to authorize clearing all DLC UDF policy entries")
    for index, item in enumerate(target):
        if not item["Accesses"]:
            module.fail_json(msg="each UDF policy entry requires at least one access", index=index)
        if not item["Users"] and not item["Groups"]:
            module.fail_json(msg="each UDF policy entry requires users or groups", index=index)
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        current = read(module, client, models, p)
        if current == target:
            module.exit_json(changed=False, udf_policy=current)
        diff_value = maybe_diff(module, current, target)
        if not module.check_mode:
            response = module.sdk_call(client.UpdateUDFPolicy, update_request(models, p))
            if p["wait"]:
                wait_policy(module, client, models, p, target)
            current = normalize(x._serialize(allow_none=True) for x in response.UDFPolicyInfos) if response.UDFPolicyInfos is not None else target
            if p["wait"]:
                current = read(module, client, models, p)
        module.exit_json(changed=True, **(diff_value or {}), udf_policy=current if not module.check_mode else target)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
