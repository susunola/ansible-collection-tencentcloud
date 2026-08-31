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
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  shipper_id: {type: str, description: Existing shipper ID; preferred for rename and deletion.}
  topic_id: {type: str, required: true, description: CLS topic ID.}
  name: {type: str, required: true, description: Shipper name.}
  bucket: {type: str, required: true, description: Destination COS bucket full name.}
  prefix: {type: str, default: '', description: Destination object prefix.}
  enabled: {type: bool, default: true, description: Enable continuous delivery.}
  interval: {type: int, default: 300, description: Delivery interval in seconds.}
  max_size: {type: int, default: 256, description: Maximum output file size in MB.}
  partition: {type: str, default: '%Y/%m/%d/%H', description: COS path partition pattern.}
  compress: {type: dict, default: {Format: gzip}, description: SDK-compatible CompressInfo configuration.}
  content: {type: dict, default: {Format: json}, description: SDK-compatible ContentInfo configuration.}
  filter_rules: {type: list, elements: dict, default: [], description: SDK-compatible FilterRuleInfo list.}
  filename_mode: {type: int, choices: [0, 1], default: 0, description: Random or delivery-time file naming.}
  storage_type: {type: str, default: STANDARD, description: COS storage class.}
  role_arn: {type: str, description: CAM role ARN used to write COS.}
  external_id: {type: str, description: External ID paired with the CAM role.}
  time_zone: {type: str, default: UTC+08:00, description: Time zone used by path time variables.}
  dsl_filter: {type: str, default: '', description: Optional CLS DSL pre-filter expression.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
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
RETURN = r"""shipper: {description: CLS COS shipper metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


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
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
