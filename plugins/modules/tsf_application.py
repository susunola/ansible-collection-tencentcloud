#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: tsf_application
short_description: Manage a Tencent Cloud TSF application
version_added: "0.15.0"
description: Creates, updates and deletes a TSF application with idempotent lifecycle semantics.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  application_id: {type: str, description: Existing application ID. When omitted, the exact name is used.}
  name: {type: str, required: true, description: Application name.}
  application_type: {type: str, choices: [V, C, S], description: Application runtime target; required when creating.}
  microservice_type: {type: str, choices: [N, M, G, NATIVE, RAW], description: Microservice type; required when creating.}
  description: {type: str, description: Application description.}
  remark_name: {type: str, description: Application display remark.}
  runtime_type: {type: str, description: Application runtime type, immutable after creation.}
  program_language: {type: str, choices: [Java, C/C++, Python, Go, Other], description: Programming language, immutable after creation.}
  framework_type: {type: str, choices: [SpringCloud, Dubbo, Go-GRPC, Other], description: Development framework.}
  apm_instance_id: {type: str, description: APM business system ID, immutable after creation.}
  ignore_create_image_repository: {type: bool, description: Do not create an image repository with the application.}
  create_same_name_image_repository: {type: bool, description: Create and bind a same-name image repository.}
  sync_delete_image_repository: {type: bool, default: false, description: Delete the associated image repository when removing the application.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- name: Manage a container application
  susunola.tencentcloud.tsf_application:
    name: orders
    application_type: C
    microservice_type: N
    description: Order service
    framework_type: SpringCloud
'''
RETURN = r'''application: {description: Effective application metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


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
        "name": "ApplicationName", "application_type": "ApplicationType",
        "microservice_type": "MicroserviceType", "description": "ApplicationDesc",
        "remark_name": "ApplicationRemarkName", "runtime_type": "ApplicationRuntimeType",
        "program_language": "ProgramLanguage", "framework_type": "FrameworkType",
        "apm_instance_id": "ApmInstanceId",
        "ignore_create_image_repository": "IgnoreCreateImageRepository",
        "create_same_name_image_repository": "CreateSameNameImageRepository",
    }
    return {target: params[source] for source, target in mapping.items() if params.get(source) is not None}


def comparable(current, target):
    return {key: current.get(key) for key in target}


def run_module():
    module = TencentCloudModule(argument_spec={
        "state": {"choices": ["present", "absent"], "default": "present"},
        "application_id": {}, "name": {"required": True},
        "application_type": {"choices": ["V", "C", "S"]},
        "microservice_type": {"choices": ["N", "M", "G", "NATIVE", "RAW"]},
        "description": {}, "remark_name": {}, "runtime_type": {},
        "program_language": {"choices": ["Java", "C/C++", "Python", "Go", "Other"]},
        "framework_type": {"choices": ["SpringCloud", "Dubbo", "Go-GRPC", "Other"]},
        "apm_instance_id": {}, "ignore_create_image_repository": {"type": "bool"},
        "create_same_name_image_repository": {"type": "bool"},
        "sync_delete_image_repository": {"type": "bool", "default": False},
    }, supports_check_mode=True)
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
            require_immutable_unchanged(module, current, target,
                                        ["ApplicationType", "ApplicationRuntimeType", "ProgramLanguage",
                                         "ApmInstanceId", "IgnoreCreateImageRepository",
                                         "CreateSameNameImageRepository"], "TSF application")
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
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
