#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: tione_model_service_diagnostics_info
short_description: Gather Tencent Cloud TIONE model service diagnostics
version_added: "0.14.0"
description:
  - Returns callable endpoint metadata for an existing service group, or validates whether a proposed image/model/mount combination permits model acceleration.
  - Exactly one mode is selected by providing C(service_group_id) or at least one hot-update input.
options:
  service_group_id: {type: str, description: Service-group ID whose call metadata is requested.}
  project_id: {type: str, description: Optional TI workspace ID for call-info mode.}
  image_info: {type: dict, description: ImageInfo-compatible candidate image for acceleration preflight mode.}
  model_info: {type: dict, description: ModelInfo-compatible candidate model for acceleration preflight mode.}
  volume_mount: {type: dict, description: VolumeMount-compatible candidate mount for acceleration preflight mode.}
  retries: {type: int, default: 5, description: Retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tione_model_service_diagnostics_info:
    service_group_id: ms-group-xxxxxxxx

- susunola.tencentcloud.tione_model_service_diagnostics_info:
    image_info: {ImageType: TCR, ImageUrl: ccr.ccs.tencentyun.com/team/infer:v2}
    model_info: {ModelVersionId: modelversion-xxxxxxxx}
'''
RETURN = r'''
call_info: {description: All available gateway and intranet call metadata., type: dict, returned: in service_group_id mode}
model_turbo_flag: {description: Allowed or Forbidden acceleration preflight result., type: str, returned: in preflight mode}
request_id: {description: Tencent Cloud request ID., type: str, returned: always}
'''

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tione.v20211111 import models, tione_client
    return models, tione_client


def _model(cls, value):
    item = cls(); item.from_json_string(json.dumps(value)); return item


def call_request(models, p):
    request = models.DescribeModelServiceCallInfoRequest(); request.ServiceGroupId = p["service_group_id"]
    if p.get("project_id") is not None: request.TiProjectId = p["project_id"]
    return request


def preflight_request(models, p):
    request = models.DescribeModelServiceHotUpdatedRequest()
    for source, target, cls_name in (("image_info", "ImageInfo", "ImageInfo"), ("model_info", "ModelInfo", "ModelInfo"), ("volume_mount", "VolumeMount", "VolumeMount")):
        if p.get(source) is not None: setattr(request, target, _model(getattr(models, cls_name), p[source]))
    return request


def serialize_call_info(response):
    result = {}
    for key in ("ServiceCallInfo", "InferGatewayCallInfo", "DefaultNginxGatewayCallInfo", "TJCallInfo", "IntranetCallInfo", "ServiceCallInfoV2"):
        value = getattr(response, key, None)
        result[key] = value._serialize(allow_none=True) if value else None
    return result


def run_module():
    spec = {"service_group_id": {}, "project_id": {}, "image_info": {"type": "dict"}, "model_info": {"type": "dict"}, "volume_mount": {"type": "dict"}}
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True); p = module.params
    preflight = any(p.get(key) is not None for key in ("image_info", "model_info", "volume_mount"))
    if bool(p.get("service_group_id")) == preflight: module.fail_json(msg="provide service_group_id for call-info mode or hot-update inputs for preflight mode, but not both")
    if p.get("project_id") is not None and not p.get("service_group_id"): module.fail_json(msg="project_id is only valid with service_group_id")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TioneClient, "tione.tencentcloudapi.com")
    try:
        if p.get("service_group_id"):
            response = module.sdk_call(client.DescribeModelServiceCallInfo, call_request(models, p))
            module.exit_json(changed=False, call_info=serialize_call_info(response), request_id=response.RequestId)
        response = module.sdk_call(client.DescribeModelServiceHotUpdated, preflight_request(models, p))
        module.exit_json(changed=False, model_turbo_flag=response.ModelTurboFlag, request_id=response.RequestId)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
