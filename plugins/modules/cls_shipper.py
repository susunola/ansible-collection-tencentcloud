#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: cls_shipper
short_description: Manage Tencent Cloud CLS delivery tasks to COS
version_added: "0.14.0"
description: Creates, updates and deletes a CLS shipper that continuously delivers a log topic to COS.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  shipper_id:
    description:
      - Existing shipper ID; preferred for rename and deletion.
    type: str
  topic_id:
    description:
      - CLS topic ID.
    type: str
    required: true
  name:
    description:
      - Shipper name.
    type: str
    required: true
  bucket:
    description:
      - Destination COS bucket full name.
    type: str
    required: true
  prefix:
    description:
      - Destination object prefix.
    type: str
    default: ''
  enabled:
    description:
      - Enable continuous delivery.
    type: bool
    default: true
  interval:
    description:
      - Delivery interval in seconds.
    type: int
    default: 300
  max_size:
    description:
      - Maximum output file size in MB.
    type: int
    default: 256
  partition:
    description:
      - COS path partition pattern.
    type: str
    default: '%Y/%m/%d/%H'
  compress:
    description:
      - SDK-compatible CompressInfo configuration.
    type: dict
    default:
      Format: gzip
  content:
    description:
      - SDK-compatible ContentInfo configuration.
    type: dict
    default:
      Format: json
  filter_rules:
    description:
      - SDK-compatible FilterRuleInfo list.
    type: list
    default: []
    elements: dict
  filename_mode:
    description:
      - Random or delivery-time file naming.
    type: int
    choices: [0, 1]
    default: 0
  storage_type:
    description:
      - COS storage class.
    type: str
    default: STANDARD
  role_arn:
    description:
      - CAM role ARN used to write COS.
    type: str
  external_id:
    description:
      - External ID paired with the CAM role.
    type: str
  time_zone:
    description:
      - Time zone used by path time variables.
    type: str
    default: UTC+08:00
  dsl_filter:
    description:
      - Optional CLS DSL pre-filter expression.
    type: str
    default: ''

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
- susunola.tencentcloud.cls_shipper:
    topic_id: 0f6c6e3a-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    name: archive-to-cos
    bucket: logs-1250000000
    prefix: cls/archive/
    content: {Format: json}
    compress: {Format: gzip}
"""
RETURN = r"""shipper:
  description:
    - CLS COS shipper metadata.
  returned: always
  type: dict"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.cls.v20201016 import cls_client, models

    return models, cls_client


def _model(models, name, value):
    item = getattr(models, name)()
    item._deserialize(value)
    return item


def _models(models, name, values):
    return [_model(models, name, value) for value in values]


def describe_request(models, p, offset=0):
    request = models.DescribeShippersRequest()
    request.Offset, request.Limit, request.PreciseSearch = offset, 100, 1
    if not p.get("shipper_id"):
        item = models.Filter()
        item.Key, item.Values = "shipperName", [p["name"]]
        request.Filters = [item]
    return request


def _common(request, models, p):
    request.Bucket, request.Prefix, request.ShipperName = p["bucket"], p["prefix"], p["name"]
    request.Interval, request.MaxSize, request.Partition = p["interval"], p["max_size"], p["partition"]
    request.FilterRules, request.Compress, request.Content = (
        _models(models, "FilterRuleInfo", p["filter_rules"]),
        _model(models, "CompressInfo", p["compress"]),
        _model(models, "ContentInfo", p["content"]),
    )
    request.FilenameMode, request.StorageType = p["filename_mode"], p["storage_type"]
    request.RoleArn, request.ExternalId, request.TimeZone, request.DSLFilter = p.get("role_arn"), p.get("external_id"), p["time_zone"], p["dsl_filter"]
    return request


def create_request(models, p):
    request = models.CreateShipperRequest()
    request.TopicId = p["topic_id"]
    return _common(request, models, p)


def update_request(models, p, shipper_id):
    request = models.ModifyShipperRequest()
    request.ShipperId, request.Status = shipper_id, p["enabled"]
    return _common(request, models, p)


def delete_request(models, shipper_id):
    request = models.DeleteShipperRequest()
    request.ShipperId = shipper_id
    return request


FIELDS = (
    "TopicId",
    "ShipperName",
    "Bucket",
    "Prefix",
    "Status",
    "Interval",
    "MaxSize",
    "Partition",
    "Compress",
    "Content",
    "FilterRules",
    "FilenameMode",
    "StorageType",
    "RoleArn",
    "ExternalId",
    "TimeZone",
    "DSLFilter",
)


def comparable(value):
    result = {key: value.get(key) for key in FIELDS}
    result["Prefix"], result["DSLFilter"] = result.get("Prefix") or "", result.get("DSLFilter") or ""
    result["FilterRules"] = sorted(result.get("FilterRules") or [], key=lambda x: (x.get("Key") or "", x.get("Regex") or "", x.get("Value") or ""))
    return result


def desired(p):
    return comparable(
        {
            "TopicId": p["topic_id"],
            "ShipperName": p["name"],
            "Bucket": p["bucket"],
            "Prefix": p["prefix"],
            "Status": p["enabled"],
            "Interval": p["interval"],
            "MaxSize": p["max_size"],
            "Partition": p["partition"],
            "Compress": p["compress"],
            "Content": p["content"],
            "FilterRules": p["filter_rules"],
            "FilenameMode": p["filename_mode"],
            "StorageType": p["storage_type"],
            "RoleArn": p.get("role_arn"),
            "ExternalId": p.get("external_id"),
            "TimeZone": p["time_zone"],
            "DSLFilter": p["dsl_filter"],
        }
    )


def find(module, client, models, p):
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeShippers, describe_request(models, p, offset))
        items = list(response.Shippers or [])
        matches = []
        for item in items:
            value = item._serialize(allow_none=True)
            if (
                (p.get("shipper_id") and value.get("ShipperId") == p["shipper_id"]) or (not p.get("shipper_id") and value.get("ShipperName") == p["name"])
            ) and value.get("TopicId") == p["topic_id"]:
                matches.append(value)
        if matches:
            if len(matches) > 1:
                module.fail_json(msg="multiple CLS shippers matched topic_id and name; specify shipper_id")
            return matches[0]
        offset += len(items)
        if not items or offset >= int(response.TotalCount or 0):
            return None


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "shipper_id": {},
        "topic_id": {"required": True},
        "name": {"required": True},
        "bucket": {"required": True},
        "prefix": {"default": ""},
        "enabled": {"type": "bool", "default": True},
        "interval": {"type": "int", "default": 300},
        "max_size": {"type": "int", "default": 256},
        "partition": {"default": "%Y/%m/%d/%H"},
        "compress": {"type": "dict", "default": {"Format": "gzip"}},
        "content": {"type": "dict", "default": {"Format": "json"}},
        "filter_rules": {"type": "list", "elements": "dict", "default": []},
        "filename_mode": {"type": "int", "choices": [0, 1], "default": 0},
        "storage_type": {"default": "STANDARD"},
        "role_arn": {},
        "external_id": {},
        "time_zone": {"default": "UTC+08:00"},
        "dsl_filter": {"default": ""},
    }
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.ClsClient, "cls.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, shipper=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteShipper, delete_request(models, current["ShipperId"]))
            module.exit_json(changed=True, **(diff or {}), shipper=current if module.check_mode else None)
        target, before = desired(p), comparable(current) if current else None
        if before == target:
            module.exit_json(changed=False, shipper=current)
        diff = maybe_diff(module, before, target)
        if not current and p.get("shipper_id"):
            module.fail_json(msg="CLS shipper_id was not found; omit shipper_id to create a new shipper")
        if not module.check_mode:
            if current:
                module.sdk_call(client.ModifyShipper, update_request(models, p, current["ShipperId"]))
            else:
                response = module.sdk_call(client.CreateShipper, create_request(models, p))
                p["shipper_id"] = response.ShipperId
                if not p["enabled"]:
                    module.sdk_call(client.ModifyShipper, update_request(models, p, response.ShipperId))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), shipper=current)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
