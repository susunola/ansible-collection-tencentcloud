#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tsf_application
short_description: Manage a Tencent Cloud TSF application
version_added: "0.15.0"
description: Creates, updates and deletes a TSF application with idempotent lifecycle semantics.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  application_id:
    description:
      - Existing application ID. When omitted, the exact name is used.
    type: str
  name:
    description:
      - Application name.
    type: str
    required: true
  application_type:
    description:
      - Application runtime target; required when creating.
    type: str
    choices: [V, C, S]
  microservice_type:
    description:
      - Microservice type; required when creating.
    type: str
    choices: [N, M, G, NATIVE, RAW]
  description:
    description:
      - Application description.
    type: str
  remark_name:
    description:
      - Application display remark.
    type: str
  runtime_type:
    description:
      - Application runtime type, immutable after creation.
    type: str
  program_language:
    description:
      - Programming language, immutable after creation.
    type: str
    choices: [Java, C/C++, Python, Go, Other]
  framework_type:
    description:
      - Development framework.
    type: str
    choices: [SpringCloud, Dubbo, Go-GRPC, Other]
  apm_instance_id:
    description:
      - APM business system ID, immutable after creation.
    type: str
  ignore_create_image_repository:
    description:
      - Do not create an image repository with the application.
    type: bool
  create_same_name_image_repository:
    description:
      - Create and bind a same-name image repository.
    type: bool
  sync_delete_image_repository:
    description:
      - Delete the associated image repository when removing the application.
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
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- name: Manage a container application
  susunola.tencentcloud.tsf_application:
    name: orders
    application_type: C
    microservice_type: N
    description: Order service
    framework_type: SpringCloud
"""
RETURN = r"""application: {description: Effective application metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, fail_from_sdk_error


def _load():
    from tencentcloud.tsf.v20180326 import models, tsf_client

    return models, tsf_client


def _serialize(value):
    return value._serialize(allow_none=True) if value is not None else None


def find(module, client, models, params):
    if params.get("application_id"):
        request = models.DescribeApplicationRequest()
        request.ApplicationId = params["application_id"]
        return _serialize(module.sdk_call(client.DescribeApplication, request).Result)
    request = models.DescribeApplicationsRequest()
    request.SearchWord, request.Offset, request.Limit = params["name"], 0, 100
    result = module.sdk_call(client.DescribeApplications, request).Result
    matches = [_serialize(item) for item in ((result.Content if result else None) or []) if item.ApplicationName == params["name"]]
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSF applications matched the exact name", name=params["name"])
    return matches[0] if matches else None


def desired(params):
    mapping = {
        "name": "ApplicationName",
        "application_type": "ApplicationType",
        "microservice_type": "MicroserviceType",
        "description": "ApplicationDesc",
        "remark_name": "ApplicationRemarkName",
        "runtime_type": "ApplicationRuntimeType",
        "program_language": "ProgramLanguage",
        "framework_type": "FrameworkType",
        "apm_instance_id": "ApmInstanceId",
        "ignore_create_image_repository": "IgnoreCreateImageRepository",
        "create_same_name_image_repository": "CreateSameNameImageRepository",
    }
    return {target: params[source] for source, target in mapping.items() if params.get(source) is not None}


def comparable(current, target):
    return {key: current.get(key) for key in target}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "application_id": {},
            "name": {"required": True},
            "application_type": {"choices": ["V", "C", "S"]},
            "microservice_type": {"choices": ["N", "M", "G", "NATIVE", "RAW"]},
            "description": {},
            "remark_name": {},
            "runtime_type": {},
            "program_language": {"choices": ["Java", "C/C++", "Python", "Go", "Other"]},
            "framework_type": {"choices": ["SpringCloud", "Dubbo", "Go-GRPC", "Other"]},
            "apm_instance_id": {},
            "ignore_create_image_repository": {"type": "bool"},
            "create_same_name_image_repository": {"type": "bool"},
            "sync_delete_image_repository": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    params = module.params
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.TsfClient, "tsf.tencentcloudapi.com")
    try:
        current = find(module, client, models, params)
        if params["state"] == "absent":
            if not current:
                module.exit_json(changed=False, application=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.DeleteApplicationRequest()
                request.ApplicationId = current["ApplicationId"]
                request.SyncDeleteImageRepository = params["sync_delete_image_repository"]
                module.sdk_call(client.DeleteApplication, request)
            module.exit_json(changed=True, **(diff or {}), application=None)
        target = desired(params)
        if not current and (not params.get("application_type") or not params.get("microservice_type")):
            module.fail_json(msg="application_type and microservice_type are required when creating a TSF application")
        if current:
            require_immutable_unchanged(
                module,
                current,
                target,
                [
                    "ApplicationType",
                    "ApplicationRuntimeType",
                    "ProgramLanguage",
                    "ApmInstanceId",
                    "IgnoreCreateImageRepository",
                    "CreateSameNameImageRepository",
                ],
                "TSF application",
            )
        if current and comparable(current, target) == target:
            module.exit_json(changed=False, application=current)
        diff = maybe_diff(module, comparable(current, target) if current else None, target)
        if not module.check_mode:
            if current:
                request = models.ModifyApplicationRequest()
                request.ApplicationId = current["ApplicationId"]
                for key in ("ApplicationName", "ApplicationDesc", "ApplicationRemarkName", "MicroserviceType", "FrameworkType"):
                    if key in target:
                        setattr(request, key, target[key])
                response = module.sdk_call(client.ModifyApplication, request)
                if response.Result is False:
                    module.fail_json(msg="Tencent Cloud rejected the TSF application update", request_id=response.RequestId)
                params["application_id"] = current["ApplicationId"]
            else:
                request = models.CreateApplicationRequest()
                for key, value in target.items():
                    if hasattr(request, key):
                        setattr(request, key, value)
                response = module.sdk_call(client.CreateApplication, request)
                params["application_id"] = response.Result
            current = find(module, client, models, params)
        module.exit_json(changed=True, **(diff or {}), application=current if not module.check_mode else target)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
