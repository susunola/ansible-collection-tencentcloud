#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: tsf_lane
short_description: Manage a Tencent Cloud TSF traffic lane
version_added: "0.15.0"
description: Creates, updates and deletes a TSF traffic lane while protecting its observable deployment-group membership as immutable.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired resource state.}
  lane_id: {type: str, description: Existing lane ID; exact name is used when omitted.}
  name: {type: str, required: true, description: Lane name.}
  remark: {type: str, description: Lane remark.}
  deployment_groups:
    type: list
    elements: dict
    description: Exact deployment-group membership, required when creating and immutable afterwards.
    suboptions:
      group_id: {type: str, required: true, description: TSF deployment group ID.}
      entrance: {type: bool, default: false, description: Whether this is the lane entrance group.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tsf_lane:
    name: checkout-canary
    remark: Canary request path
    deployment_groups:
      - {group_id: group-xxxxxxxx, entrance: true}
      - {group_id: group-yyyyyyyy}
'''
RETURN = r'''lane: {description: Effective TSF lane metadata., type: dict, returned: always}'''

import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.tsf.v20180326 import models, tsf_client
    return models, tsf_client


def _serialize(value):
    return value._serialize(allow_none=True) if value is not None else None


def normalize_groups(values):
    result = []
    for value in values or []:
        group_id = value.get("GroupId")
        if group_id is not None:
            result.append({"GroupId": group_id, "Entrance": bool(value.get("Entrance"))})
    return sorted(result, key=lambda item: item["GroupId"])


def desired(params):
    target = {"LaneName": params["name"]}
    if params.get("remark") is not None:
        target["Remark"] = params["remark"]
    if params.get("deployment_groups") is not None:
        target["LaneGroupList"] = normalize_groups([
            {"GroupId": item["group_id"], "Entrance": item["entrance"]}
            for item in params["deployment_groups"]
        ])
    return target


def comparable(current, target):
    result = {key: current.get(key) for key in target}
    if "LaneGroupList" in result:
        result["LaneGroupList"] = normalize_groups(result["LaneGroupList"])
    return result


def find(module, client, models, params):
    request = models.DescribeLanesRequest()
    request.Offset, request.Limit = 0, 100
    if params.get("lane_id"):
        request.LaneIdList = [params["lane_id"]]
    else:
        request.SearchWord = params["name"]
    result = module.sdk_call(client.DescribeLanes, request).Result
    values = (result.Content if result else None) or []
    matches = [item for item in values if item.LaneId == params.get("lane_id")] if params.get("lane_id") else [item for item in values if item.LaneName == params["name"]]
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSF lanes matched the exact name", name=params["name"])
    return _serialize(matches[0]) if matches else None


def group_models(models, groups):
    result = []
    for group in groups or []:
        item = models.LaneGroup()
        item.from_json_string(json.dumps({"GroupId": group["group_id"], "Entrance": group["entrance"]}))
        result.append(item)
    return result


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "lane_id": {}, "name": {"required": True}, "remark": {},
            "deployment_groups": {"type": "list", "elements": "dict", "options": {
                "group_id": {"required": True}, "entrance": {"type": "bool", "default": False},
            }},
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
                module.exit_json(changed=False, lane=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.DeleteLaneRequest(); request.LaneId = current["LaneId"]
                response = module.sdk_call(client.DeleteLane, request)
                if response.Result is False:
                    module.fail_json(msg="Tencent Cloud rejected the TSF lane deletion", request_id=response.RequestId)
            module.exit_json(changed=True, **(diff or {}), lane=None)

        target = desired(params)
        if current:
            require_immutable_unchanged(module, current, target, ["LaneGroupList"], "TSF lane")
        elif params.get("deployment_groups") is None:
            module.fail_json(msg="deployment_groups is required when creating a TSF lane")
        if current and comparable(current, target) == target:
            module.exit_json(changed=False, lane=current)
        diff = maybe_diff(module, comparable(current, target) if current else None, target)
        if not module.check_mode:
            if current:
                request = models.ModifyLaneRequest(); request.LaneId = current["LaneId"]
                request.LaneName, request.Remark = target["LaneName"], target.get("Remark")
                response = module.sdk_call(client.ModifyLane, request)
                if response.Result is False:
                    module.fail_json(msg="Tencent Cloud rejected the TSF lane update", request_id=response.RequestId)
                params["lane_id"] = current["LaneId"]
            else:
                request = models.CreateLaneRequest(); request.LaneName, request.Remark = target["LaneName"], target.get("Remark")
                request.LaneGroupList = group_models(models, params["deployment_groups"])
                params["lane_id"] = module.sdk_call(client.CreateLane, request).Result
            current = find(module, client, models, params)
        module.exit_json(changed=True, **(diff or {}), lane=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
