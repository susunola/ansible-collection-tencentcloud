#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: tione_training_model_version_info
short_description: Gather Tencent Cloud TIONE training-model versions
version_added: "0.14.0"
description:
  - Returns one exact TIONE training-model version by stable version ID or lists versions within one parent model.
  - Parent-scoped list mode prevents versions from different models being mixed by display name.
options:
  model_id: {type: str, description: Parent training-model ID; required in list mode.}
  version_id: {type: str, description: Exact model-version ID; switches to detail mode.}
  filters: {type: dict, default: {}, description: Parent-scoped version filters such as TrainingModelVersionId, ModelVersionType, ModelFormat or AlgorithmFramework.}
  retries: {type: int, default: 5, description: Retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tione_training_model_version_info:
    version_id: modelversion-xxxxxxxx

- susunola.tencentcloud.tione_training_model_version_info:
    model_id: model-xxxxxxxx
    filters:
      ModelVersionType: NORMAL
      AlgorithmFramework: PYTORCH
'''
RETURN = r'''
model_version: {description: Exact training-model version detail., type: dict, returned: when version_id is provided}
model_versions: {description: Versions within the selected parent model., type: list, elements: dict, returned: in list mode}
total_count: {description: Number of returned parent-scoped versions., type: int, returned: in list mode}
request_id: {description: Tencent Cloud request ID., type: str, returned: always}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tione.v20211111 import models, tione_client
    return models, tione_client


def detail_request(models, version_id):
    request = models.DescribeTrainingModelVersionRequest(); request.TrainingModelVersionId = version_id; return request


def list_request(models, model_id, filters):
    request = models.DescribeTrainingModelVersionsRequest(); request.TrainingModelId = model_id
    if filters:
        request.Filters = []
        for name, values in sorted(filters.items()):
            item = models.Filter(); item.Name, item.Values = name, values if isinstance(values, list) else [values]; request.Filters.append(item)
    return request


def run_module():
    spec = {"model_id": {}, "version_id": {}, "filters": {"type": "dict", "default": {}}}
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True, mutually_exclusive=[("version_id", "filters")]); p = module.params
    if not p.get("version_id") and not p.get("model_id"): module.fail_json(msg="model_id is required in list mode")
    if len(p["filters"]) > 10: module.fail_json(msg="filters accepts at most ten filter names")
    if any(len(value if isinstance(value, list) else [value]) > 100 for value in p["filters"].values()): module.fail_json(msg="each filter accepts at most 100 values")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TioneClient, "tione.tencentcloudapi.com")
    try:
        if p.get("version_id"):
            response = module.sdk_call(client.DescribeTrainingModelVersion, detail_request(models, p["version_id"]))
            value = response.TrainingModelVersion._serialize(allow_none=True) if response.TrainingModelVersion else None
            module.exit_json(changed=False, model_version=value, request_id=response.RequestId)
        response = module.sdk_call(client.DescribeTrainingModelVersions, list_request(models, p["model_id"], p["filters"]))
        values = [item._serialize(allow_none=True) for item in (response.TrainingModelVersions or [])]
        module.exit_json(changed=False, model_versions=values, total_count=len(values), request_id=response.RequestId)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
