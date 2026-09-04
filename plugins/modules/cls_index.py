#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cls_index
short_description: Manage Tencent Cloud CLS topic indexes
version_added: "0.14.0"
description: Creates, updates and deletes full-text indexes for CLS topics.
options:
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  topic_id: {type: str, required: true, description: CLS topic ID.}
  enabled: {type: bool, default: true, description: Enable indexing.}
  case_sensitive: {type: bool, default: false, description: Use case-sensitive full-text matching.}
  full_text_delimiters: {type: str, default: ',; ', description: Full-text tokenizer characters.}
  contain_zh: {type: bool, default: true, description: Enable Chinese tokenization.}
  include_internal_fields: {type: bool, default: false, description: Index internal fields.}
  metadata_flag: {type: int, choices: [0, 1], default: 0, description: Metadata indexing flag.}
  coverage_field: {type: str, description: Field used for log coverage.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cls_index:
    topic_id: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    contain_zh: true
"""
RETURN = r"""index: {description: CLS index metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cls.v20201016 import cls_client, models

    return models, cls_client


def rule(models, p):
    full = models.FullTextInfo()
    full.CaseSensitive, full.Tokenizer, full.ContainZH = p["case_sensitive"], p["full_text_delimiters"], p["contain_zh"]
    value = models.RuleInfo()
    value.FullText = full
    return value


def wanted(p):
    result = {
        "Status": p["enabled"],
        "IncludeInternalFields": p["include_internal_fields"],
        "MetadataFlag": p["metadata_flag"],
        "Rule": {"FullText": {"CaseSensitive": p["case_sensitive"], "Tokenizer": p["full_text_delimiters"], "ContainZH": p["contain_zh"]}},
    }
    if p["coverage_field"] is not None:
        result["CoverageField"] = p["coverage_field"]
    return result


def current_values(value, target):
    full = (value.get("Rule") or {}).get("FullText") or {}
    result = {
        "Status": value.get("Status"),
        "IncludeInternalFields": value.get("IncludeInternalFields"),
        "MetadataFlag": value.get("MetadataFlag"),
        "Rule": {"FullText": {key: full.get(key) for key in ("CaseSensitive", "Tokenizer", "ContainZH")}},
    }
    if "CoverageField" in target:
        result["CoverageField"] = value.get("CoverageField")
    return result


def find(module, client, models, topic_id):
    request = models.DescribeIndexRequest()
    request.TopicId = topic_id
    try:
        return module.sdk_call(client.DescribeIndex, request)._serialize(allow_none=True)
    except Exception as exc:
        if is_not_found(exc):
            return None
        raise


def apply(request, models, p):
    request.TopicId, request.Status, request.Rule = p["topic_id"], p["enabled"], rule(models, p)
    request.IncludeInternalFields, request.MetadataFlag = p["include_internal_fields"], p["metadata_flag"]
    if p["coverage_field"] is not None:
        request.CoverageField = p["coverage_field"]
    return request


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "topic_id": {"required": True},
            "enabled": {"type": "bool", "default": True},
            "case_sensitive": {"type": "bool", "default": False},
            "full_text_delimiters": {"default": ",; "},
            "contain_zh": {"type": "bool", "default": True},
            "include_internal_fields": {"type": "bool", "default": False},
            "metadata_flag": {"type": "int", "choices": [0, 1], "default": 0},
            "coverage_field": {},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.ClsClient, "cls.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["topic_id"])
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, index=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.DeleteIndexRequest()
                request.TopicId = p["topic_id"]
                module.sdk_call(client.DeleteIndex, request)
            module.exit_json(changed=True, **(diff or {}), index=current if module.check_mode else None)
        target = wanted(p)
        before = current_values(current, target) if current else None
        if before == target:
            module.exit_json(changed=False, index=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            operation = client.ModifyIndex if current else client.CreateIndex
            request = models.ModifyIndexRequest() if current else models.CreateIndexRequest()
            module.sdk_call(operation, apply(request, models, p))
            current = find(module, client, models, p["topic_id"])
        module.exit_json(changed=True, **(diff or {}), index=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
