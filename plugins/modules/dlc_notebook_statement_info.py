#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_notebook_statement_info
short_description: Gather a Tencent Cloud DLC Notebook statement and SQL results
version_added: "0.14.0"
description:
  - Reads one DLC Notebook statement through its strong session and statement identities.
  - Optionally retrieves every SQL-result page while preserving page boundaries and result metadata.
options:
  session_id: {type: str, required: true, description: Exact Notebook session ID.}
  statement_id: {type: str, required: true, description: Exact Notebook statement ID.}
  task_id: {type: str, description: Exact backing task ID; inferred from the statement when available.}
  include_sql_result: {type: bool, default: false, description: Retrieve all SQL-result pages for the backing task.}
  batch_id: {type: str, description: Optional batch ID used when reading SQL results.}
  max_results: {type: int, default: 1000, description: 'Maximum rows requested per result page, from 1 to 1000.'}
  data_field_cut_length: {type: int, description: Optional maximum returned field-value length.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_notebook_statement_info:
    session_id: session-xxxxxxxx
    statement_id: statement-xxxxxxxx

- susunola.tencentcloud.dlc_notebook_statement_info:
    session_id: session-xxxxxxxx
    statement_id: statement-xxxxxxxx
    include_sql_result: true
    max_results: 500
"""
RETURN = r"""
statement: {description: Notebook statement metadata., type: dict, returned: always}
result_pages: {description: Ordered SQL-result pages with schema and statistics., type: list, elements: dict, returned: when include_sql_result}
request_id: {description: Request ID from the statement lookup., type: str, returned: always}
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def statement_request(models, session_id, statement_id, task_id=None):
    request = models.DescribeNotebookSessionStatementRequest()
    request.SessionId, request.StatementId = session_id, statement_id
    if task_id is not None:
        request.TaskId = task_id
    return request


def result_request(models, task_id, p, token=None):
    request = models.DescribeNotebookSessionStatementSqlResultRequest()
    request.TaskId, request.MaxResults = task_id, p["max_results"]
    if token:
        request.NextToken = token
    if p.get("batch_id") is not None:
        request.BatchId = p["batch_id"]
    if p.get("data_field_cut_length") is not None:
        request.DataFieldCutLen = p["data_field_cut_length"]
    return request


def result_page(response):
    return {
        "TaskId": response.TaskId,
        "ResultSet": response.ResultSet,
        "ResultSchema": [x._serialize(allow_none=True) for x in (response.ResultSchema or [])],
        "NextToken": response.NextToken,
        "OutputPath": response.OutputPath,
        "UseTime": response.UseTime,
        "AffectRows": response.AffectRows,
        "DataAmount": response.DataAmount,
        "UiUrl": response.UiUrl,
        "RequestId": response.RequestId,
    }


def read_results(module, client, models, task_id, p):
    pages, token, seen = [], None, set()
    while True:
        response = module.sdk_call(client.DescribeNotebookSessionStatementSqlResult, result_request(models, task_id, p, token))
        page = result_page(response)
        pages.append(page)
        token = response.NextToken
        if not token:
            break
        if token in seen:
            module.fail_json(msg="DLC Notebook SQL-result pagination repeated a continuation token", task_id=task_id, next_token=token)
        seen.add(token)
    return pages


def run_module():
    spec = {
        "session_id": {"required": True},
        "statement_id": {"required": True},
        "task_id": {},
        "include_sql_result": {"type": "bool", "default": False},
        "batch_id": {},
        "max_results": {"type": "int", "default": 1000},
        "data_field_cut_length": {"type": "int"},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if not 1 <= p["max_results"] <= 1000:
        module.fail_json(msg="max_results must be between 1 and 1000")
    if p.get("data_field_cut_length") is not None and p["data_field_cut_length"] < 1:
        module.fail_json(msg="data_field_cut_length must be positive")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeNotebookSessionStatement, statement_request(models, p["session_id"], p["statement_id"], p.get("task_id")))
        statement = response.NotebookSessionStatement._serialize(allow_none=True) if response.NotebookSessionStatement is not None else None
        pages = []
        if p["include_sql_result"]:
            task_id = p.get("task_id") or (statement or {}).get("TaskId")
            if not task_id:
                module.fail_json(msg="task_id is required to retrieve SQL results and was not returned by the statement", statement=statement)
            pages = read_results(module, client, models, task_id, p)
        module.exit_json(changed=False, statement=statement, result_pages=pages, request_id=response.RequestId)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
