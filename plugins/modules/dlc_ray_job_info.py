#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_ray_job_info
short_description: Gather Tencent Cloud DLC Ray job diagnostics
version_added: "0.14.0"
description:
  - Reads one Ray job by strong ID and optionally gathers its status history, events, Pods and submitted YAML.
  - Page-number and context-token diagnostics are bounded to prevent unbounded reads.
options:
  ray_job_id: {type: str, required: true, description: Exact Ray job ID.}
  include_history: {type: bool, default: false, description: Include paginated job status history.}
  include_events: {type: bool, default: false, description: Include context-paginated Ray job events.}
  include_pods: {type: bool, default: false, description: Include paginated Ray job Pods.}
  include_yaml: {type: bool, default: false, description: Include the submitted RayJob YAML.}
  start_time: {type: int, description: Optional diagnostic start timestamp in milliseconds.}
  end_time: {type: int, description: Optional diagnostic end timestamp in milliseconds.}
  event_type: {type: str, description: Optional ASCII event type such as Normal or Warning.}
  page_size: {type: int, default: 100, description: History, event and Pod page size, from 1 to 200.}
  max_pages: {type: int, default: 100, description: Maximum pages per diagnostic stream, from 1 to 1000.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_ray_job_info:
    ray_job_id: rayjob-xxxxxxxx
    include_history: true
    include_events: true
    include_pods: true
    include_yaml: true
"""
RETURN = r"""
ray_job: {description: Ray job detail., type: dict, returned: always}
history: {description: Ordered job status history., type: list, elements: dict, returned: always}
events: {description: Ordered Ray job events., type: list, elements: dict, returned: always}
pods: {description: Matching Ray job Pods., type: list, elements: dict, returned: always}
yaml: {description: Submitted RayJob YAML., type: str, returned: when include_yaml}
truncated: {description: Diagnostic stream truncation flags., type: dict, returned: always}
request_id: {description: Request ID from the Ray job detail call., type: str, returned: always}
"""

import re
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def id_request(cls, job_id):
    request = cls()
    request.Id = job_id
    return request


def history_request(models, p, page):
    request = id_request(models.GetRayJobHistoryRequest, p["ray_job_id"])
    request.Page, request.PageSize = page, p["page_size"]
    return request


def pods_request(models, p, page):
    request = id_request(models.GetRayJobPodsRequest, p["ray_job_id"])
    request.Page, request.PageSize = page, p["page_size"]
    if p.get("start_time") is not None:
        request.StartTime = p["start_time"]
    if p.get("end_time") is not None:
        request.EndTime = p["end_time"]
    return request


def event_request(models, p, context=None):
    request = id_request(models.GetRayJobEventRequest, p["ray_job_id"])
    request.PageSize = p["page_size"]
    if context:
        request.Context = context
    if p.get("start_time") is not None:
        request.StartTime = p["start_time"]
    if p.get("end_time") is not None:
        request.EndTime = p["end_time"]
    if p.get("event_type") is not None:
        request.EventType = p["event_type"]
    return request


def page_number_read(module, function, request_fn, item_field, p):
    values, truncated = [], False
    for page in range(1, p["max_pages"] + 1):
        response = module.sdk_call(function, request_fn(page))
        items = getattr(response, item_field) or []
        values.extend(x._serialize(allow_none=True) for x in items)
        if page >= int(response.TotalPages or 0) or not items:
            break
    else:
        truncated = True
    return values, truncated


def event_read(module, client, models, p):
    values, context, seen, truncated = [], None, set(), False
    for _ in range(p["max_pages"]):
        response = module.sdk_call(client.GetRayJobEvent, event_request(models, p, context))
        values.extend(x._serialize(allow_none=True) for x in (response.Events or []))
        if response.ListOver:
            break
        context = response.Context
        if not context:
            break
        if context in seen:
            module.fail_json(msg="DLC Ray job event pagination repeated a context token", ray_job_id=p["ray_job_id"], context=context)
        seen.add(context)
    else:
        truncated = True
    return values, truncated


def run_module():
    spec = {
        "ray_job_id": {"required": True},
        "include_history": {"type": "bool", "default": False},
        "include_events": {"type": "bool", "default": False},
        "include_pods": {"type": "bool", "default": False},
        "include_yaml": {"type": "bool", "default": False},
        "start_time": {"type": "int"},
        "end_time": {"type": "int"},
        "event_type": {},
        "page_size": {"type": "int", "default": 100},
        "max_pages": {"type": "int", "default": 100},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if not 1 <= p["page_size"] <= 200:
        module.fail_json(msg="page_size must be between 1 and 200")
    if not 1 <= p["max_pages"] <= 1000:
        module.fail_json(msg="max_pages must be between 1 and 1000")
    if p.get("start_time") is not None and p.get("end_time") is not None and p["start_time"] > p["end_time"]:
        module.fail_json(msg="start_time must not exceed end_time")
    if p.get("event_type") is not None and not re.match(r"^[A-Za-z]+$", p["event_type"]):
        module.fail_json(msg="event_type must contain ASCII letters only")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.GetRayJob, id_request(models.GetRayJobRequest, p["ray_job_id"]))
        detail = response._serialize(allow_none=True)
        request_id = detail.pop("RequestId", None)
        history, events, pods, yaml = [], [], [], None
        truncated = {"history": False, "events": False, "pods": False}
        if p["include_history"]:
            history, truncated["history"] = page_number_read(module, client.GetRayJobHistory, lambda page: history_request(models, p, page), "Items", p)
        if p["include_events"]:
            events, truncated["events"] = event_read(module, client, models, p)
        if p["include_pods"]:
            pods, truncated["pods"] = page_number_read(module, client.GetRayJobPods, lambda page: pods_request(models, p, page), "Items", p)
        if p["include_yaml"]:
            yaml = module.sdk_call(client.GetRayJobYaml, id_request(models.GetRayJobYamlRequest, p["ray_job_id"])).Yaml
        module.exit_json(changed=False, ray_job=detail, history=history, events=events, pods=pods, yaml=yaml, truncated=truncated, request_id=request_id)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
