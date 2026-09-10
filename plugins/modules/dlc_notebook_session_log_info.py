#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_notebook_session_log_info
short_description: Gather Tencent Cloud DLC Notebook session logs
version_added: "0.14.0"
description:
  - Reads DLC Notebook session logs with offset pagination until the API returns a short page.
  - A configurable page cap prevents unbounded reads when the service returns repeated full pages.
options:
  session_id: {type: str, required: true, description: Exact Notebook session ID.}
  page_size: {type: int, default: 200, description: 'Log lines requested per page, from 1 to 1000.'}
  max_pages: {type: int, default: 100, description: 'Maximum number of pages fetched, from 1 to 1000.'}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_notebook_session_log_info:
    session_id: session-xxxxxxxx
    page_size: 200
"""
RETURN = r"""
logs: {description: Ordered Notebook session log lines., type: list, elements: str, returned: always}
truncated: {description: Whether max_pages stopped a sequence of full pages., type: bool, returned: always}
request_id: {description: Request ID from the final page., type: str, returned: always}
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def build_request(models, session_id, offset, limit):
    request = models.DescribeNotebookSessionLogRequest()
    request.SessionId, request.Offset, request.Limit = session_id, offset, limit
    return request


def read(module, client, models, p):
    logs, offset, request_id, truncated = [], 0, None, False
    for _ in range(p["max_pages"]):
        response = module.sdk_call(client.DescribeNotebookSessionLog, build_request(models, p["session_id"], offset, p["page_size"]))
        page = response.Logs or []
        logs.extend(page)
        request_id = response.RequestId
        offset += len(page)
        if len(page) < p["page_size"]:
            break
    else:
        truncated = True
    return logs, truncated, request_id


def run_module():
    spec = {"session_id": {"required": True}, "page_size": {"type": "int", "default": 200}, "max_pages": {"type": "int", "default": 100}}
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if not 1 <= p["page_size"] <= 1000:
        module.fail_json(msg="page_size must be between 1 and 1000")
    if not 1 <= p["max_pages"] <= 1000:
        module.fail_json(msg="max_pages must be between 1 and 1000")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        logs, truncated, request_id = read(module, client, models, p)
        module.exit_json(changed=False, logs=logs, truncated=truncated, request_id=request_id)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
