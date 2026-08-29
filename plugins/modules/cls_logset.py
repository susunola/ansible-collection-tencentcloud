#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cls_logset
short_description: Manage Tencent Cloud CLS logsets
version_added: "0.14.0"
description: Creates, renames, retags and deletes CLS logsets idempotently.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  logset_id: {description: Existing logset ID., type: str}
  name: {description: Logset name., type: str}
  tags: {description: Exact tag dictionary., type: dict}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cls_logset:
    name: production-logs
    tags: {env: prod}
'''
RETURN = r'''
logset: {description: CLS logset metadata., type: dict, returned: always}
'''

import time

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_cls():
    from tencentcloud.cls.v20201016 import cls_client, models
    return models, cls_client


def build_tags(models, tags):
    result = []
    for key, value in sorted((tags or {}).items()):
        tag = models.Tag()
        tag.Key, tag.Value = str(key), str(value)
        result.append(tag)
    return result


def build_describe_request(models, logset_id=None, name=None, offset=0):
    request = models.DescribeLogsetsRequest()
    request.Offset, request.Limit = offset, 100
    filters = []
    for key, value in (("logsetId", logset_id), ("logsetName", name)):
        if value:
            item = models.Filter()
            item.Key, item.Values = key, [value]
            filters.append(item)
    if filters:
        request.Filters = filters
    return request


def build_create_request(models, name, tags):
    request = models.CreateLogsetRequest()
    request.LogsetName = name
    if tags is not None:
        request.Tags = build_tags(models, tags)
    return request


def build_update_request(models, logset_id, name, tags):
    request = models.ModifyLogsetRequest()
    request.LogsetId, request.LogsetName = logset_id, name
    if tags is not None:
        request.Tags = build_tags(models, tags)
    return request


def build_delete_request(models, logset_id):
    request = models.DeleteLogsetRequest()
    request.LogsetId = logset_id
    return request


def _tags(values):
    return {x.get("Key"): x.get("Value") for x in (values or [])}


def find_logset(module, client, models, logset_id, name):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeLogsets, build_describe_request(models, logset_id, name, offset))
        items = list(getattr(response, "Logsets", None) or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if (logset_id and value.get("LogsetId") == logset_id) or (not logset_id and value.get("LogsetName") == name):
                matches.append(value)
        offset += len(items)
        if not items or offset >= int(getattr(response, "TotalCount", 0) or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple CLS logsets have the requested name", name=name)
    return matches[0] if matches else None


def wait_for_logset(module, client, models, logset_id, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_logset(module, client, models, logset_id, None)
        if absent and current is None:
            return None
        if not absent and current:
            name_ok = current.get("LogsetName") == desired["LogsetName"]
            tags_ok = "Tags" not in desired or _tags(current.get("Tags")) == desired["Tags"]
            if name_ok and tags_ok:
                return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for CLS logset convergence", logset=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"type": "str", "choices": ["present", "absent"], "default": "present"}, "logset_id": {"type": "str"}, "name": {"type": "str"}, "tags": {"type": "dict"}}, required_one_of=[("logset_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, client_module = _load_cls()
    client = module.create_client(client_module.ClsClient, "cls.tencentcloudapi.com")
    try:
        current = find_logset(module, client, models, p["logset_id"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, logset=None, msg="CLS logset is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), logset=current, msg="Would delete CLS logset")
            module.sdk_call(client.DeleteLogset, build_delete_request(models, current["LogsetId"]))
            wait_for_logset(module, client, models, current["LogsetId"], absent=True)
            module.exit_json(changed=True, **(diff or {}), logset=None, msg="CLS logset deleted")
        if current is None and not p["name"]:
            module.fail_json(msg="name is required when creating a CLS logset")
        desired = {"LogsetName": p["name"]}
        if p["tags"] is not None:
            desired["Tags"] = p["tags"]
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), logset=None, msg="Would create CLS logset")
            response = module.sdk_call(client.CreateLogset, build_create_request(models, p["name"], p["tags"]))
            current = wait_for_logset(module, client, models, response.LogsetId, desired)
            module.exit_json(changed=True, **(diff or {}), logset=current, msg="CLS logset created")
        changed = current.get("LogsetName") != p["name"] or (p["tags"] is not None and _tags(current.get("Tags")) != p["tags"])
        if not changed:
            module.exit_json(changed=False, logset=current, msg="CLS logset is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), logset=current, msg="Would update CLS logset")
        module.sdk_call(client.ModifyLogset, build_update_request(models, current["LogsetId"], p["name"], p["tags"]))
        current = wait_for_logset(module, client, models, current["LogsetId"], desired)
        module.exit_json(changed=True, **(diff or {}), logset=current, msg="CLS logset updated")
    except Exception as exc:
        module.fail_json(msg="Tencent Cloud API request failed", error=str(exc), error_code=getattr(exc, "get_code", lambda: None)(), request_id=getattr(exc, "get_request_id", lambda: None)())


def main():
    run_module()


if __name__ == "__main__":
    main()
