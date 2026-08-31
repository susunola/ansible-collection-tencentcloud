#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: dlc_notebook_session_info
short_description: Gather Tencent Cloud DLC Notebook sessions
version_added: "0.14.0"
description:
  - Lists DLC Notebook sessions with complete pagination and optional engine, state, keyword and engine-generation filters.
options:
  data_engine_name: {type: str, description: Return sessions for this exact data-engine name.}
  states:
    type: list
    elements: str
    choices: [not_started, starting, idle, busy, shutting_down, error, dead, killed, success]
    description: Return sessions in any of these lifecycle states.
  keyword: {type: str, description: DLC notebook keyword filter over engine name, session ID or session name.}
  engine_generation: {type: str, choices: [supersql, native], description: Filter by engine generation.}
  sort_fields: {type: list, elements: str, description: API-supported session sort fields.}
  ascending: {type: bool, default: false, description: Sort in ascending order.}
  page_size: {type: int, default: 100, description: Number of sessions requested per page, from 1 to 100.}
  retries: {type: int, default: 5, description: Retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.dlc_notebook_session_info:
    data_engine_name: production-spark
    states: [idle, busy]

- susunola.tencentcloud.dlc_notebook_session_info:
    keyword: analyst
    engine_generation: supersql
'''
RETURN = r'''
sessions: {description: Matching DLC Notebook sessions., type: list, elements: dict, returned: always}
total_count: {description: Number of sessions reported by the API., type: int, returned: always}
request_id: {description: Request ID from the final page., type: str, returned: always}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client
    return models, dlc_client


def build_request(models, p, offset=0):
    request = models.DescribeNotebookSessionsRequest(); request.Offset, request.Limit, request.Asc = offset, p["page_size"], p["ascending"]
    if p.get("data_engine_name") is not None: request.DataEngineName = p["data_engine_name"]
    if p.get("states") is not None: request.State = p["states"]
    if p.get("sort_fields") is not None: request.SortFields = p["sort_fields"]
    filters = []
    for name, value in (("engine-generation", p.get("engine_generation")), ("notebook-keyword", p.get("keyword"))):
        if value is not None:
            item = models.Filter(); item.Name, item.Values = name, [value]; filters.append(item)
    if filters: request.Filters = filters
    return request


def read(module, client, models, p):
    offset, sessions, total, request_id = 0, [], 0, None
    while True:
        response = module.sdk_call(client.DescribeNotebookSessions, build_request(models, p, offset)); page = response.Sessions or []
        sessions.extend(x._serialize(allow_none=True) for x in page); total = int(response.TotalElements or 0); request_id = response.RequestId
        offset += len(page)
        if not page or offset >= total: break
    return sessions, total, request_id


def run_module():
    states = ["not_started", "starting", "idle", "busy", "shutting_down", "error", "dead", "killed", "success"]
    spec = {
        "data_engine_name": {}, "states": {"type": "list", "elements": "str", "choices": states}, "keyword": {},
        "engine_generation": {"choices": ["supersql", "native"]}, "sort_fields": {"type": "list", "elements": "str"},
        "ascending": {"type": "bool", "default": False}, "page_size": {"type": "int", "default": 100},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True); p = module.params
    if not 1 <= p["page_size"] <= 100: module.fail_json(msg="page_size must be between 1 and 100")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        sessions, total, request_id = read(module, client, models, p)
        module.exit_json(changed=False, sessions=sessions, total_count=total, request_id=request_id)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
