#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: tione_model_service_state
short_description: Manage Tencent Cloud TIONE online model service state
version_added: "0.14.0"
description:
  - Reconciles the running, stopped or absent state of an existing TIONE online model service version.
  - Uses the stable service-version ID; service creation and configuration drift are intentionally outside this module.
  - Failed and abnormal states are surfaced explicitly instead of repeatedly issuing lifecycle actions.
options:
  service_id: {type: str, required: true, description: Stable deployed service-version ID.}
  project_id: {type: str, description: Optional TI workspace ID.}
  state: {type: str, choices: [running, stopped, absent], default: running, description: Desired operational state.}
  allow_delete: {type: bool, default: false, description: Explicit destructive-operation guard.}
  wait: {type: bool, default: true, description: Wait for lifecycle convergence.}
  waiter_delay: {type: int, default: 10, description: Seconds between state checks.}
  waiter_timeout: {type: int, default: 1800, description: Overall convergence timeout.}
  retries: {type: int, default: 5, description: Retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tione_model_service_state:
    service_id: ms-xxxxxxxx
    state: running

- susunola.tencentcloud.tione_model_service_state:
    service_id: ms-xxxxxxxx
    state: absent
    allow_delete: true
'''
RETURN = r'''
service: {description: Effective service detail., type: dict, returned: always}
service_id: {description: Stable service-version ID., type: str, returned: always}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state

FAILED = {"create_failed", "timeout_exception", "abnormal"}
TRANSITIONAL = {"creating", "stopping", "pending", "waiting"}


def _load():
    from tencentcloud.tione.v20211111 import models, tione_client
    return models, tione_client


def detail_request(models, p):
    request = models.DescribeModelServiceRequest(); request.ServiceId = p["service_id"]
    if p.get("project_id") is not None: request.TiProjectId = p["project_id"]
    return request


def action_request(cls, p, action=None):
    request = cls(); request.ServiceId = p["service_id"]
    if p.get("project_id") is not None: request.TiProjectId = p["project_id"]
    if action is not None: request.ServiceAction = action
    return request


def get(module, client, models, p):
    try: response = module.sdk_call(client.DescribeModelService, detail_request(models, p))
    except Exception as exc:
        if is_not_found(exc): return None
        raise
    return response.Service._serialize(allow_none=True) if response.Service else None


def service_status(value): return str((value or {}).get("Status") or "").lower()


def wait_service(module, client, models, p, accepted):
    def poll():
        current = get(module, client, models, p)
        if current is None: return "absent"
        actual = service_status(current)
        if actual in FAILED: module.fail_json(msg="TIONE model service entered a failed state", service=current)
        return actual
    return wait_for_state(module, poll, accepted, timeout=p["waiter_timeout"], delay=p["waiter_delay"])


def run_module():
    spec = {
        "service_id": {"required": True}, "project_id": {},
        "state": {"choices": ["running", "stopped", "absent"], "default": "running"},
        "allow_delete": {"type": "bool", "default": False}, "wait": {"type": "bool", "default": True},
        "waiter_delay": {"type": "int", "default": 10}, "waiter_timeout": {"type": "int", "default": 1800},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True); p = module.params
    if p["waiter_delay"] < 1 or p["waiter_timeout"] < 1: module.fail_json(msg="waiter_delay and waiter_timeout must be positive")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TioneClient, "tione.tencentcloudapi.com")
    try:
        current = get(module, client, models, p)
        if p["state"] == "absent":
            if current is None: module.exit_json(changed=False, service=None, service_id=p["service_id"])
            if not p["allow_delete"]: module.fail_json(msg="allow_delete=true is required to delete a TIONE model service", service=current)
            diff_value = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteModelService, action_request(models.DeleteModelServiceRequest, p))
                if p["wait"]: wait_service(module, client, models, p, ["absent"])
            module.exit_json(changed=True, **(diff_value or {}), service=None, service_id=p["service_id"])
        if current is None: module.fail_json(msg="TIONE model service does not exist; create it before managing operational state", service_id=p["service_id"])
        actual = service_status(current)
        if actual in FAILED: module.fail_json(msg="TIONE model service is in a failed state", service=current)
        target_status = "normal" if p["state"] == "running" else "stopped"
        if actual == target_status: module.exit_json(changed=False, service=current, service_id=p["service_id"])
        if actual in TRANSITIONAL and not p["wait"]: module.fail_json(msg="TIONE model service is transitioning; enable wait before changing state", service=current)
        diff_value = maybe_diff(module, current, dict(current, Status="Normal" if p["state"] == "running" else "Stopped"))
        if not module.check_mode:
            if actual in TRANSITIONAL:
                wait_service(module, client, models, p, ["normal", "stopped"])
                current = get(module, client, models, p); actual = service_status(current)
            if actual != target_status:
                action = "RESUME" if p["state"] == "running" else "STOP"
                module.sdk_call(client.ModifyModelService, action_request(models.ModifyModelServiceRequest, p, action))
                if p["wait"]: wait_service(module, client, models, p, [target_status])
                current = get(module, client, models, p)
        module.exit_json(changed=True, **(diff_value or {}), service=current, service_id=p["service_id"])
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
