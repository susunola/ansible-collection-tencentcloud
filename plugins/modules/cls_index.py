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

  state:
    description:
      - C(present) creates the index with V(CreateIndex) when it does not exist and updates it with V(ModifyIndex)
        when it differs. C(absent) deletes it with V(DeleteIndex).
    type: str
    choices: [present, absent]
    default: present
  topic_id:
    description:
      - CLS topic ID.
    type: str
    required: true
  enabled:
    description:
      - Enable indexing.
    type: bool
    default: true
  case_sensitive:
    description:
      - Use case-sensitive full-text matching.
    type: bool
    default: false
  full_text_delimiters:
    description:
      - Full-text tokenizer characters.
    type: str
    default: ',; '
  contain_zh:
    description:
      - Enable Chinese tokenization.
    type: bool
    default: true
  include_internal_fields:
    description:
      - Index internal fields.
    type: bool
    default: false
  metadata_flag:
    description:
      - Metadata indexing flag.
    type: int
    choices: [0, 1]
    default: 0
  coverage_field:
    description:
      - Field used for log coverage.
    type: str
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
seealso:
  - module: susunola.tencentcloud.cls_index_info
    description: Gather information about a Tencent Cloud CLS topic index.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.cls_index:
    topic_id: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    contain_zh: true

- name: Delete the index
  susunola.tencentcloud.cls_index:
    state: absent
    topic_id: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
"""
RETURN = r"""index:
  description:
    - CLS index metadata.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    Status: false
    IncludeInternalFields: false
    MetadataFlag: 0
    CoverageField: message
    Rule:
      FullText:
        CaseSensitive: false
        Tokenizer: ',; '
        ContainZH: true
"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


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
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
