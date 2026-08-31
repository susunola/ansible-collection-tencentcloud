#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: tdmysql_database_object_info
short_description: Gather Tencent Cloud TDSQL MySQL databases and objects
version_added: "0.14.0"
description:
  - Lists databases, or tables, views, procedures and functions within one database.
  - Both modes use bounded offset pagination.
options:
  instance_id: {type: str, required: true, description: Stable TDSQL MySQL instance ID.}
  database: {type: str, description: Database whose objects are requested; omit to list databases.}
  database_regexp: {type: str, description: Database-name expression in database-list mode.}
  table_regexp: {type: str, description: Table-name expression in object-list mode.}
  page_size: {type: int, default: 100, description: Items requested per page, from 1 to 100.}
  max_pages: {type: int, default: 1000, description: Maximum pages fetched, from 1 to 1000.}
  retries: {type: int, default: 5, description: Retries for transient API failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tdmysql_database_object_info:
    instance_id: tdsql3-xxxxxxxx
- susunola.tencentcloud.tdmysql_database_object_info:
    instance_id: tdsql3-xxxxxxxx
    database: application
'''
RETURN = r'''
databases: {description: Database metadata., type: list, elements: dict, returned: in database-list mode}
objects: {description: Tables, views, procedures and functions., type: dict, returned: in object-list mode}
total_count: {description: Matching database count reported by the API., type: int, returned: in database-list mode}
truncated: {description: Whether max_pages stopped pagination., type: bool, returned: always}
request_id: {description: Request ID from the final page., type: str, returned: always}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def database_request(models, p, offset):
    request = models.DescribeDatabasesRequest(); request.InstanceId, request.Offset, request.Limit = p["instance_id"], offset, p["page_size"]
    if p.get("database_regexp") is not None: request.DatabaseRegexp = p["database_regexp"]
    return request


def object_request(models, p, offset):
    request = models.DescribeDatabaseObjectsRequest(); request.InstanceId, request.DbName = p["instance_id"], p["database"]
    request.Offset, request.Limit = offset, p["page_size"]
    if p.get("table_regexp") is not None: request.TableRegexp = p["table_regexp"]
    return request


def read_databases(module, client, models, p):
    values, total, request_id, offset, truncated = [], 0, None, 0, False
    for _ in range(p["max_pages"]):
        response = module.sdk_call(client.DescribeDatabases, database_request(models, p, offset)); items = response.Databases or []
        values.extend(item._serialize(allow_none=True) for item in items); total, request_id = int(response.TotalCount or 0), response.RequestId; offset += len(items)
        if not items or offset >= total: break
    else: truncated = True
    return values, total, truncated, request_id


def read_objects(module, client, models, p):
    values = {"Tables": [], "Views": [], "Procs": [], "Funcs": []}; offset, request_id, truncated = 0, None, False
    for _ in range(p["max_pages"]):
        response = module.sdk_call(client.DescribeDatabaseObjects, object_request(models, p, offset)); page_count = 0
        for key in values:
            items = getattr(response, key, None) or []; page_count = max(page_count, len(items)); values[key].extend(item._serialize(allow_none=True) for item in items)
        request_id = response.RequestId; offset += page_count
        if page_count < p["page_size"]: break
    else: truncated = True
    return values, truncated, request_id


def _load():
    from tencentcloud.tdmysql.v20211122 import models, tdmysql_client
    return models, tdmysql_client


def run_module():
    spec = {"instance_id": {"required": True}, "database": {}, "database_regexp": {}, "table_regexp": {}, "page_size": {"type": "int", "default": 100}, "max_pages": {"type": "int", "default": 1000}}
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True); p = module.params
    if not 1 <= p["page_size"] <= 100 or not 1 <= p["max_pages"] <= 1000: module.fail_json(msg="page_size and max_pages are outside supported bounds")
    if p.get("database") and p.get("database_regexp"): module.fail_json(msg="database_regexp is only valid in database-list mode")
    if not p.get("database") and p.get("table_regexp"): module.fail_json(msg="table_regexp requires database")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TdmysqlClient, "tdmysql.tencentcloudapi.com")
    try:
        if p.get("database"):
            values, truncated, request_id = read_objects(module, client, models, p); module.exit_json(changed=False, objects=values, truncated=truncated, request_id=request_id)
        values, total, truncated, request_id = read_databases(module, client, models, p); module.exit_json(changed=False, databases=values, total_count=total, truncated=truncated, request_id=request_id)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
