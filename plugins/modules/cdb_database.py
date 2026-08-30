#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: cdb_database
short_description: Manage databases in TencentDB for MySQL
version_added: "0.14.0"
description: Creates and deletes a database and protects its immutable character set from silent drift.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: CDB instance ID.}
  name: {type: str, required: true, description: Database name.}
  character_set: {type: str, choices: [utf8, gbk, latin1, utf8mb4], default: utf8mb4, description: Database character set.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cdb_database:
    instance_id: cdb-xxxxxxxx
    name: orders
    character_set: utf8mb4
'''
RETURN = r'''database: {description: CDB database metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.cdb.v20170320 import cdb_client, models
    return models, cdb_client


def describe_request(models, instance_id, offset=0):
    request = models.DescribeDatabasesRequest(); request.InstanceId, request.Offset, request.Limit = instance_id, offset, 5000; return request


def create_request(models, p):
    request = models.CreateDatabaseRequest(); request.InstanceId, request.DBName, request.CharacterSetName = p["instance_id"], p["name"], p["character_set"]; return request


def delete_request(models, p):
    request = models.DeleteDatabaseRequest(); request.InstanceId, request.DBName = p["instance_id"], p["name"]; return request


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeDatabases, describe_request(models, p["instance_id"], offset)); items = list(response.DatabaseList or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if value.get("DatabaseName") == p["name"]: return value
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0): return None


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True}, "name": {"required": True}, "character_set": {"choices": ["utf8", "gbk", "latin1", "utf8mb4"], "default": "utf8mb4"}}, supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.CdbClient, "cdb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, database=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteDatabase, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), database=current if module.check_mode else None)
        target = {"DatabaseName": p["name"], "CharacterSet": p["character_set"]}
        before = {key: current.get(key) for key in target} if current else None
        if before == target: module.exit_json(changed=False, database=current)
        diff = maybe_diff(module, before, target)
        if current: require_immutable_unchanged(module, before, target, ("CharacterSet",), "CDB database")
        if not module.check_mode: module.sdk_call(client.CreateDatabase, create_request(models, p)); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), database=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
