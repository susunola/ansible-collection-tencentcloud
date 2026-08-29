#!/usr/bin/python
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: dbbrain_sql_filter
short_description: Manage Tencent Cloud DBbrain SQL filters
version_added: "0.14.0"
description: Manages active SQL concurrency filters through DBbrain.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  instance_id: {description: Database instance ID., type: str, required: true}
  sql_type: {description: SQL statement type to match., type: str, choices: [SELECT, UPDATE, DELETE, INSERT, REPLACE], required: true}
  filter_key: {description: Comma-separated SQL keywords matched with logical AND., type: str, required: true}
  max_concurrency: {description: Maximum concurrent matching statements; zero rejects all., type: int, required: true}
  duration: {description: Filter lifetime in seconds; -1 means indefinitely., type: int, default: -1}
  session_token: {description: Short-lived token returned by VerifyUserAccount., type: str, required: true}
  product: {description: Database product family., type: str, choices: [mysql, cynosdb], default: mysql}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r"""
- susunola.tencentcloud.dbbrain_sql_filter:
    instance_id: cdb-xxxxxxxx
    sql_type: SELECT
    filter_key: select,user
    max_concurrency: 10
    session_token: "{{ dbbrain_session_token }}"
"""
RETURN = r"""sql_filter: {description: SQL filter metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_dbbrain():
    from tencentcloud.dbbrain.v20210527 import dbbrain_client, models

    return models, dbbrain_client


def build_describe_request(models, p):
    r = models.DescribeSqlFiltersRequest()
    r.InstanceId = p["instance_id"]
    r.Statuses = ["RUNNING"]
    r.Offset = 0
    r.Limit = 100
    r.Product = p["product"]
    return r


def build_create_request(models, p):
    r = models.CreateSqlFilterRequest()
    r.InstanceId = p["instance_id"]
    r.SqlType = p["sql_type"]
    r.FilterKey = p["filter_key"]
    r.MaxConcurrency = p["max_concurrency"]
    r.Duration = p["duration"]
    r.SessionToken = p["session_token"]
    r.Product = p["product"]
    return r


def build_delete_request(models, p, ids):
    r = models.DeleteSqlFiltersRequest()
    r.InstanceId = p["instance_id"]
    r.FilterIds = ids
    r.SessionToken = p["session_token"]
    r.Product = p["product"]
    return r


def _desired(p):
    return {"SqlType": p["sql_type"], "OriginKeys": p["filter_key"], "MaxConcurrency": p["max_concurrency"]}


def _find(items, p):
    return next(
        (x._serialize(allow_none=True) for x in items if x.SqlType == p["sql_type"] and x.OriginKeys == p["filter_key"] and x.Status == "RUNNING"), None
    )


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "instance_id": {"type": "str", "required": True},
            "sql_type": {"type": "str", "choices": ["SELECT", "UPDATE", "DELETE", "INSERT", "REPLACE"], "required": True},
            "filter_key": {"type": "str", "required": True, "no_log": False},
            "max_concurrency": {"type": "int", "required": True},
            "duration": {"type": "int", "default": -1},
            "session_token": {"type": "str", "required": True, "no_log": True},
            "product": {"type": "str", "choices": ["mysql", "cynosdb"], "default": "mysql"},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load_dbbrain()
    client = module.create_client(cm.DbbrainClient, "dbbrain.tencentcloudapi.com")
    try:
        current = _find(module.sdk_call(client.DescribeSqlFilters, build_describe_request(models, p)).Items or [], p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, sql_filter=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteSqlFilters, build_delete_request(models, p, [current["Id"]]))
            module.exit_json(changed=True, **(diff or {}), sql_filter=current if module.check_mode else None)
        desired = _desired(p)
        if current and all(current.get(k) == v for k, v in desired.items()):
            module.exit_json(changed=False, sql_filter=current)
        diff = maybe_diff(module, current, desired)
        if not module.check_mode:
            if current:
                module.sdk_call(client.DeleteSqlFilters, build_delete_request(models, p, [current["Id"]]))
            response = module.sdk_call(client.CreateSqlFilter, build_create_request(models, p))
            desired["Id"] = response.FilterId
        module.exit_json(changed=True, **(diff or {}), sql_filter=current if module.check_mode else desired)
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
