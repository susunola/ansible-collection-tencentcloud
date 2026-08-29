#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cls_topic
short_description: Manage Tencent Cloud CLS topics
version_added: "0.14.0"
description: Creates, updates and deletes CLS log topics within a logset.
options:
  state: {description: Desired state., type: str, choices: [present, absent], default: present}
  topic_id: {description: Existing topic ID., type: str}
  logset_id: {description: Parent logset ID., type: str, required: true}
  name: {description: Topic name., type: str}
  partition_count: {description: Topic partition count., type: int, default: 1}
  period: {description: Retention period in days., type: int, default: 30}
  hot_period: {description: Hot storage retention in days., type: int}
  storage_type: {description: Storage class., type: str, choices: [hot, cold], default: hot}
  auto_split: {description: Enable automatic partition splitting., type: bool, default: true}
  max_split_partitions: {description: Maximum partitions after automatic splitting., type: int, default: 50}
  description: {description: Topic description., type: str, default: ''}
  tags: {description: Exact tag dictionary., type: dict}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cls_topic:
    logset_id: logset-xxxxxxxx
    name: network-flow
    period: 30
    partition_count: 2
'''
RETURN = r'''
topic: {description: CLS topic metadata., type: dict, returned: always}
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
        item = models.Tag()
        item.Key, item.Value = str(key), str(value)
        result.append(item)
    return result


def build_describe_request(models, topic_id=None, logset_id=None, name=None, offset=0):
    request = models.DescribeTopicsRequest()
    request.Offset, request.Limit = offset, 100
    filters = []
    for key, value in (("topicId", topic_id), ("logsetId", logset_id), ("topicName", name)):
        if value:
            item = models.Filter()
            item.Key, item.Values = key, [value]
            filters.append(item)
    if filters:
        request.Filters = filters
    return request


def _apply(request, models, params, creating=False):
    request.TopicName = params["name"]
    request.PartitionCount, request.Period = params["partition_count"], params["period"]
    request.StorageType, request.AutoSplit = params["storage_type"], params["auto_split"]
    request.MaxSplitPartitions, request.Describes = params["max_split_partitions"], params["description"]
    if params.get("hot_period") is not None:
        request.HotPeriod = params["hot_period"]
    if params.get("tags") is not None:
        request.Tags = build_tags(models, params["tags"])
    if creating:
        request.LogsetId = params["logset_id"]
    return request


def build_create_request(models, params):
    return _apply(models.CreateTopicRequest(), models, params, True)


def build_update_request(models, topic_id, params):
    request = _apply(models.ModifyTopicRequest(), models, params)
    request.TopicId = topic_id
    return request


def build_delete_request(models, topic_id):
    request = models.DeleteTopicRequest()
    request.TopicId = topic_id
    return request


def _tags(values):
    return {x.get("Key"): x.get("Value") for x in (values or [])}


def find_topic(module, client, models, topic_id, logset_id, name):
    offset, matches = 0, []
    while True:
        response = module.sdk_call(client.DescribeTopics, build_describe_request(models, topic_id, logset_id, name, offset))
        items = list(getattr(response, "Topics", None) or [])
        for item in items:
            value = item._serialize(allow_none=True)
            if (topic_id and value.get("TopicId") == topic_id) or (not topic_id and value.get("LogsetId") == logset_id and value.get("TopicName") == name):
                matches.append(value)
        offset += len(items)
        if not items or offset >= int(getattr(response, "TotalCount", 0) or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple CLS topics have the requested name", name=name)
    return matches[0] if matches else None


def _desired(params):
    result = {"TopicName": params["name"], "PartitionCount": params["partition_count"], "Period": params["period"], "StorageType": params["storage_type"], "AutoSplit": params["auto_split"], "MaxSplitPartitions": params["max_split_partitions"], "Describes": params["description"]}
    if params["hot_period"] is not None:
        result["HotPeriod"] = params["hot_period"]
    if params["tags"] is not None:
        result["Tags"] = params["tags"]
    return result


def _matches(current, desired):
    return all((_tags(current.get(k)) if k == "Tags" else current.get(k)) == v for k, v in desired.items())


def wait_for_topic(module, client, models, topic_id, logset_id, desired=None, absent=False):
    deadline = time.time() + module.params["waiter_timeout"]
    while True:
        current = find_topic(module, client, models, topic_id, logset_id, None)
        if absent and current is None:
            return None
        if not absent and current and _matches(current, desired):
            return current
        if time.time() >= deadline:
            module.fail_json(msg="Timed out waiting for CLS topic convergence", topic=current)
        time.sleep(module.params["waiter_delay"])


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"type": "str", "choices": ["present", "absent"], "default": "present"}, "topic_id": {"type": "str"}, "logset_id": {"type": "str", "required": True}, "name": {"type": "str"}, "partition_count": {"type": "int", "default": 1}, "period": {"type": "int", "default": 30}, "hot_period": {"type": "int"}, "storage_type": {"type": "str", "choices": ["hot", "cold"], "default": "hot"}, "auto_split": {"type": "bool", "default": True}, "max_split_partitions": {"type": "int", "default": 50}, "description": {"type": "str", "default": ""}, "tags": {"type": "dict"}}, required_one_of=[("topic_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, client_module = _load_cls()
    client = module.create_client(client_module.ClsClient, "cls.tencentcloudapi.com")
    try:
        current = find_topic(module, client, models, p["topic_id"], p["logset_id"], p["name"])
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, topic=None, msg="CLS topic is absent")
            diff = maybe_diff(module, current, None)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), topic=current, msg="Would delete CLS topic")
            module.sdk_call(client.DeleteTopic, build_delete_request(models, current["TopicId"]))
            wait_for_topic(module, client, models, current["TopicId"], p["logset_id"], absent=True)
            module.exit_json(changed=True, **(diff or {}), topic=None, msg="CLS topic deleted")
        if current is None and not p["name"]:
            module.fail_json(msg="name is required when creating a CLS topic")
        desired = _desired(p)
        if current is None:
            diff = maybe_diff(module, None, desired)
            if module.check_mode:
                module.exit_json(changed=True, **(diff or {}), topic=None, msg="Would create CLS topic")
            response = module.sdk_call(client.CreateTopic, build_create_request(models, p))
            current = wait_for_topic(module, client, models, response.TopicId, p["logset_id"], desired)
            module.exit_json(changed=True, **(diff or {}), topic=current, msg="CLS topic created")
        if _matches(current, desired):
            module.exit_json(changed=False, topic=current, msg="CLS topic is up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), topic=current, msg="Would update CLS topic")
        module.sdk_call(client.ModifyTopic, build_update_request(models, current["TopicId"], p))
        current = wait_for_topic(module, client, models, current["TopicId"], p["logset_id"], desired)
        module.exit_json(changed=True, **(diff or {}), topic=current, msg="CLS topic updated")
    except Exception as exc:
        module.fail_json(msg="Tencent Cloud API request failed", error=str(exc), error_code=getattr(exc, "get_code", lambda: None)(), request_id=getattr(exc, "get_request_id", lambda: None)())


def main():
    run_module()


if __name__ == "__main__":
    main()
