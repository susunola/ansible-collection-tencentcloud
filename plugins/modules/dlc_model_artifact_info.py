#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: dlc_model_artifact_info
short_description: Inspect Tencent Cloud DLC model-version artifacts
version_added: "0.14.0"
description:
  - Reads configuration, file-tree and README metadata for one exact DLC model version.
  - Each artifact call can be disabled independently to fit least-privilege automation and model formats without that artifact.
options:
  model_uid: {type: str, required: true, description: Parent inference-model UID.}
  model_version: {type: str, required: true, description: Exact immutable model version.}
  include_config: {type: bool, default: true, description: Read the model config.json artifact.}
  include_files: {type: bool, default: true, description: Read the model file tree.}
  include_readme: {type: bool, default: true, description: Read model README metadata and Markdown.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dlc_model_artifact_info:
    model_uid: model-bge-managed
    model_version: v2

- susunola.tencentcloud.dlc_model_artifact_info:
    model_uid: model-xgboost-risk
    model_version: production
    include_readme: false
"""
RETURN = r"""
config: {description: 'Model config response, including raw ConfigJson and parsed Config when valid JSON.', type: dict, returned: when include_config}
files: {description: Model file-tree response., type: dict, returned: when include_files}
readme: {description: Model README and descriptive metadata., type: dict, returned: when include_readme}
request_ids: {description: Request IDs keyed by requested artifact., type: dict, returned: always}
"""

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.dlc.v20210125 import models, dlc_client

    return models, dlc_client


def build_request(cls, p):
    request = cls()
    request.ModelUid, request.ModelVersion = p["model_uid"], p["model_version"]
    return request


def serialize(response):
    return response._serialize(allow_none=True)


def read(module, client, models, p):
    result, request_ids = {}, {}
    calls = (
        ("config", "include_config", client.GetModelConfig, models.GetModelConfigRequest),
        ("files", "include_files", client.GetModelFiles, models.GetModelFilesRequest),
        ("readme", "include_readme", client.GetModelReadme, models.GetModelReadmeRequest),
    )
    for name, option, method, cls in calls:
        if not p[option]:
            continue
        value = serialize(module.sdk_call(method, build_request(cls, p)))
        request_ids[name] = value.pop("RequestId", None)
        if name == "config" and value.get("ConfigJson") is not None:
            try:
                value["Config"] = json.loads(value["ConfigJson"])
            except (TypeError, ValueError):
                value["Config"] = None
        result[name] = value
    return result, request_ids


def run_module():
    spec = {
        "model_uid": {"required": True},
        "model_version": {"required": True},
        "include_config": {"type": "bool", "default": True},
        "include_files": {"type": "bool", "default": True},
        "include_readme": {"type": "bool", "default": True},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    if not any(p[key] for key in ("include_config", "include_files", "include_readme")):
        module.fail_json(msg="at least one model artifact must be selected")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DlcClient, "dlc.tencentcloudapi.com")
    try:
        result, request_ids = read(module, client, models, p)
        module.exit_json(changed=False, request_ids=request_ids, **result)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
