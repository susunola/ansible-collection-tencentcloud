#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cloudaudit_track
short_description: Manage Tencent Cloud CloudAudit tracks
version_added: "0.14.0"
description: Creates, updates and deletes audit tracks and their delivery destinations.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  track_id: {description: Existing audit track ID., type: int}
  name: {description: Audit track name., type: str}
  enabled: {description: Enable event delivery., type: bool, default: true}
  action_type: {description: Event action category., type: str, choices: ['*', Read, Write], default: '*'}
  resource_type: {description: Product identifier or C(*) for every product., type: str, default: '*'}
  event_names: {description: Exact event API name list., type: list, elements: str, default: ['*']}
  track_all_members: {description: Deliver organization member events., type: bool, default: false}
  storage_type: {description: Delivery storage type., type: str, choices: [cos, cls, ckafka]}
  storage_region: {description: Delivery storage region., type: str}
  storage_name: {description: Delivery destination storage identifier., type: str}
  storage_prefix: {description: COS object prefix., type: str, default: ''}
  storage_account_id: {description: Destination account ID., type: str}
  storage_app_id: {description: Destination application ID., type: str}
  compress: {description: Compress delivered logs., type: bool, default: true}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cloudaudit_track:
    name: organization-events
    storage_type: cls
    storage_region: ap-guangzhou
    storage_name: topic-xxxxxxxx
    action_type: '*'
    resource_type: '*'
    event_names: ['*']
'''
RETURN = r'''
track: {description: CloudAudit track metadata., type: dict, returned: always}
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_cloudaudit():
    from tencentcloud.cloudaudit.v20190319 import cloudaudit_client, models
    return models, cloudaudit_client


def build_list_request(models, page=1):
    request = models.DescribeAuditTracksRequest()
    request.PageNumber, request.PageSize = page, 50
    return request


def build_describe_request(models, track_id):
    request = models.DescribeAuditTrackRequest()
    request.TrackId = track_id
    return request


def build_storage(models, params):
    storage = models.Storage()
    storage.StorageType, storage.StorageRegion = params["storage_type"], params["storage_region"]
    storage.StorageName, storage.StoragePrefix = params["storage_name"], params["storage_prefix"]
    storage.Compress = 1 if params["compress"] else 2
    if params.get("storage_account_id"):
        storage.StorageAccountId = params["storage_account_id"]
    if params.get("storage_app_id"):
        storage.StorageAppId = params["storage_app_id"]
    return storage


def _apply(request, models, params):
    request.Name, request.Status = params["name"], int(params["enabled"])
    request.ActionType, request.ResourceType = params["action_type"], params["resource_type"]
    request.EventNames = sorted(set(params["event_names"]))
    request.TrackForAllMembers = int(params["track_all_members"])
    request.Storage = build_storage(models, params)
    return request


def build_create_request(models, params):
    return _apply(models.CreateAuditTrackRequest(), models, params)


def build_update_request(models, track_id, params):
    request = _apply(models.ModifyAuditTrackRequest(), models, params)
    request.TrackId = track_id
    return request


def build_delete_request(models, track_id):
    request = models.DeleteAuditTrackRequest()
    request.TrackId = track_id
    return request


def find_track(module, client, models, track_id=None, name=None):
    page, matches = 1, []
    while True:
        response = module.sdk_call(client.DescribeAuditTracks, build_list_request(models, page))
        items = list(response.Tracks or [])
        for item in items:
            if (track_id and item.TrackId == track_id) or (not track_id and item.Name == name):
                matches.append(item)
        if page * 50 >= int(response.TotalCount or 0):
            break
        page += 1
    if len(matches) > 1:
        module.fail_json(msg="Multiple CloudAudit tracks have the requested name", name=name)
    if not matches:
        return None
    detail = module.sdk_call(client.DescribeAuditTrack, build_describe_request(models, matches[0].TrackId))
    value = detail._serialize(allow_none=True)
    value["TrackId"] = matches[0].TrackId
    value.pop("RequestId", None)
    return value


def _desired(params):
    storage = {"StorageType": params["storage_type"], "StorageRegion": params["storage_region"], "StorageName": params["storage_name"], "StoragePrefix": params["storage_prefix"], "Compress": 1 if params["compress"] else 2}
    if params.get("storage_account_id"):
        storage["StorageAccountId"] = params["storage_account_id"]
    if params.get("storage_app_id"):
        storage["StorageAppId"] = params["storage_app_id"]
    return {"Name": params["name"], "Status": int(params["enabled"]), "ActionType": params["action_type"], "ResourceType": params["resource_type"], "EventNames": sorted(set(params["event_names"])), "TrackForAllMembers": int(params["track_all_members"]), "Storage": storage}


def _matches(current, desired):
    for key, value in desired.items():
        actual = current.get(key)
        if key == "EventNames":
            actual = sorted(set(actual or []))
        if key == "Storage":
            actual = {field: (actual or {}).get(field) for field in value}
        if actual != value:
            return False
    return True


def wait_for_track(module, client, models, track_id, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_track(module, client, models, track_id, None)
        if absent and current is None:
            return None
        if not absent and current and _matches(current, desired):
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for CloudAudit track convergence", track=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"type": "str", "choices": ["present", "absent"], "default": "present"}, "track_id": {"type": "int"}, "name": {"type": "str"}, "enabled": {"type": "bool", "default": True}, "action_type": {"type": "str", "choices": ["*", "Read", "Write"], "default": "*"}, "resource_type": {"type": "str", "default": "*"}, "event_names": {"type": "list", "elements": "str", "default": ["*"]}, "track_all_members": {"type": "bool", "default": False}, "storage_type": {"type": "str", "choices": ["cos", "cls", "ckafka"]}, "storage_region": {"type": "str"}, "storage_name": {"type": "str"}, "storage_prefix": {"type": "str", "default": ""}, "storage_account_id": {"type": "str"}, "storage_app_id": {"type": "str"}, "compress": {"type": "bool", "default": True}}, required_one_of=[("track_id", "name")], required_if=[("state", "present", ("name", "storage_type", "storage_region", "storage_name"))], supports_check_mode=True)
    p = module.params
    if p["resource_type"] == "*" and p["event_names"] != ["*"]:
        module.fail_json(msg="event_names must be ['*'] when resource_type is '*'")
    module.require_sdk()
    models, client_module = _load_cloudaudit()
    client = module.create_client(client_module.CloudauditClient, "cloudaudit.tencentcloudapi.com")
    try:
        current = find_track(module, client, models, p["track_id"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, track=None, msg="CloudAudit track is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), track=current, msg="Would delete CloudAudit track")
            module.sdk_call(client.DeleteAuditTrack, build_delete_request(models, current["TrackId"]))
            wait_for_track(module, client, models, current["TrackId"], absent=True)
            module.exit_json(changed=True, **(diff or {}), track=None, msg="CloudAudit track deleted")
        desired = _desired(p)
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), track=None, msg="Would create CloudAudit track")
            response = module.sdk_call(client.CreateAuditTrack, build_create_request(models, p))
            current = wait_for_track(module, client, models, response.TrackId, desired)
            module.exit_json(changed=True, **(diff or {}), track=current, msg="CloudAudit track created")
        if _matches(current, desired):
            module.exit_json(changed=False, track=current, msg="CloudAudit track is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), track=current, msg="Would update CloudAudit track")
        module.sdk_call(client.ModifyAuditTrack, build_update_request(models, current["TrackId"], p))
        current = wait_for_track(module, client, models, current["TrackId"], desired)
        module.exit_json(changed=True, **(diff or {}), track=current, msg="CloudAudit track updated")
    except Exception as exc:
        module.fail_json(msg="Tencent Cloud API request failed", error=str(exc), error_code=getattr(exc, "get_code", lambda: None)(), request_id=getattr(exc, "get_request_id", lambda: None)())


def main():
    run_module()


if __name__ == "__main__":
    main()
