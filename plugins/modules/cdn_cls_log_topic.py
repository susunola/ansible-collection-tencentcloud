#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: cdn_cls_log_topic
short_description: Manage Tencent Cloud CDN real-time CLS log topics
version_added: "0.14.0"
description:
  - Creates, enables, disables and deletes CDN real-time log topics.
  - Reconciles the complete set of CDN domain and acceleration-area bindings.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired topic state.}
  topic_id: {type: str, description: Existing CLS topic ID; preferred for updates and deletion.}
  topic_name: {type: str, description: "Topic name, also used for lookup when topic_id is omitted."}
  logset_id: {type: str, description: CLS logset ID; required for creation and topic operations.}
  channel: {type: str, choices: [cdn, ecdn], default: cdn, description: CDN access channel.}
  enabled: {type: bool, default: true, description: Whether real-time log delivery is enabled.}
  domain_area_configs:
    description: Exact set of CDN domains and acceleration areas bound to the topic.
    type: list
    elements: dict
    default: []
    suboptions:
      domain: {type: str, required: true, description: CDN acceleration domain.}
      areas: {type: list, elements: str, choices: [mainland, overseas], required: true, description: Acceleration areas.}
  inherit_domain_tags: {type: bool, default: false, description: Whether the CLS topic inherits CDN domain tags.}
  force_replace: {type: bool, default: false, description: Recreate the topic when its immutable name or logset differs.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""

EXAMPLES = r"""
- name: Send CDN access logs to CLS
  susunola.tencentcloud.cdn_cls_log_topic:
    region: ap-guangzhou
    topic_name: cdn-access
    logset_id: logset-xxxxxxxx
    enabled: true
    inherit_domain_tags: true
    domain_area_configs:
      - domain: static.example.com
        areas: [mainland]
      - domain: global.example.com
        areas: [overseas]

- name: Remove a CDN real-time log topic
  susunola.tencentcloud.cdn_cls_log_topic:
    region: ap-guangzhou
    topic_id: topic-xxxxxxxx
    logset_id: logset-xxxxxxxx
    state: absent
"""

RETURN = r"""topic: {description: CDN CLS topic metadata and exact domain bindings., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.cdn.v20180606 import models, cdn_client

    return models, cdn_client


def list_topics_request(models, channel):
    request = models.ListClsLogTopicsRequest()
    request.Channel = channel
    return request


def list_domains_request(models, p, topic_id, logset_id):
    request = models.ListClsTopicDomainsRequest()
    request.TopicId, request.LogsetId, request.Channel = topic_id, logset_id, p["channel"]
    return request


def _domain_configs(models, values):
    result = []
    for value in sorted(values or [], key=lambda item: item["domain"]):
        config = models.DomainAreaConfig()
        config.Domain, config.Area = value["domain"], sorted(value["areas"])
        result.append(config)
    return result


def create_request(models, p):
    request = models.CreateClsLogTopicRequest()
    request.TopicName, request.LogsetId, request.Channel = p["topic_name"], p["logset_id"], p["channel"]
    request.DomainAreaConfigs = _domain_configs(models, p["domain_area_configs"])
    request.InheritDomainTags = p["inherit_domain_tags"]
    return request


def manage_domains_request(models, p, topic_id, logset_id):
    request = models.ManageClsTopicDomainsRequest()
    request.TopicId, request.LogsetId, request.Channel = topic_id, logset_id, p["channel"]
    request.DomainAreaConfigs = _domain_configs(models, p["domain_area_configs"])
    request.InheritDomainTags = p["inherit_domain_tags"]
    return request


def enable_request(models, p, topic_id, logset_id):
    request = models.EnableClsLogTopicRequest()
    request.TopicId, request.LogsetId, request.Channel = topic_id, logset_id, p["channel"]
    return request


def disable_request(models, p, topic_id, logset_id):
    request = models.DisableClsLogTopicRequest()
    request.TopicId, request.LogsetId, request.Channel = topic_id, logset_id, p["channel"]
    return request


def delete_request(models, p, topic_id, logset_id):
    request = models.DeleteClsLogTopicRequest()
    request.TopicId, request.LogsetId, request.Channel = topic_id, logset_id, p["channel"]
    return request


def _topic_candidates(response):
    values = []
    default_logset = response.Logset._serialize(allow_none=True) if response.Logset else {}
    for topic in response.Topics or []:
        item = topic._serialize(allow_none=True)
        item["LogsetId"] = default_logset.get("LogsetId")
        values.append(item)
    for extra in response.ExtraLogset or []:
        logset = extra.Logset._serialize(allow_none=True) if extra.Logset else {}
        for topic in extra.Topics or []:
            item = topic._serialize(allow_none=True)
            item["LogsetId"] = logset.get("LogsetId")
            values.append(item)
    return values


def find_topic(module, client, models, p):
    response = module.sdk_call(client.ListClsLogTopics, list_topics_request(models, p["channel"]))
    matches = []
    for item in _topic_candidates(response):
        if p.get("topic_id") and item.get("TopicId") == p["topic_id"]:
            matches.append(item)
        elif not p.get("topic_id") and p.get("topic_name") and item.get("TopicName") == p["topic_name"]:
            matches.append(item)
    if p.get("logset_id"):
        matches = [item for item in matches if item.get("LogsetId") == p["logset_id"]]
    if len(matches) > 1:
        module.fail_json(msg="Multiple CDN CLS topics matched; specify topic_id and logset_id")
    if not matches:
        return None
    topic = matches[0]
    logset_id = topic.get("LogsetId") or p.get("logset_id")
    if logset_id:
        details = module.sdk_call(client.ListClsTopicDomains, list_domains_request(models, p, topic["TopicId"], logset_id))
        topic["DomainAreaConfigs"] = [item._serialize(allow_none=True) for item in details.DomainAreaConfigs or []]
        topic["InheritDomainTags"] = bool(details.InheritDomainTags)
    return topic


def _normalized(values):
    return sorted(
        ({"Domain": item.get("Domain") or item.get("domain"), "Area": sorted(item.get("Area") or item.get("areas") or [])} for item in values or []),
        key=lambda item: item["Domain"],
    )


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "topic_id": {},
            "topic_name": {},
            "logset_id": {},
            "channel": {"choices": ["cdn", "ecdn"], "default": "cdn"},
            "enabled": {"type": "bool", "default": True},
            "domain_area_configs": {
                "type": "list",
                "elements": "dict",
                "default": [],
                "options": {"domain": {"required": True}, "areas": {"type": "list", "elements": "str", "required": True, "choices": ["mainland", "overseas"]}},
            },
            "inherit_domain_tags": {"type": "bool", "default": False},
            "force_replace": {"type": "bool", "default": False},
        },
        required_one_of=[("topic_id", "topic_name")],
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CdnClient, "cdn.tencentcloudapi.com")
    try:
        current = find_topic(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, topic=None)
            logset_id = p.get("logset_id") or current.get("LogsetId")
            if not logset_id:
                module.fail_json(msg="logset_id is required to delete this topic")
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteClsLogTopic, delete_request(models, p, current["TopicId"], logset_id))
            module.exit_json(changed=True, **(diff or {}), topic=current if module.check_mode else None)
        if not current and (not p.get("topic_name") or not p.get("logset_id")):
            module.fail_json(msg="topic_name and logset_id are required when creating a topic")
        immutable = current and (
            (p.get("topic_name") and current.get("TopicName") != p["topic_name"]) or (p.get("logset_id") and current.get("LogsetId") != p["logset_id"])
        )
        if immutable and not p["force_replace"]:
            module.fail_json(msg="Topic name or logset is immutable; set force_replace=true to recreate", topic=current)
        desired = {
            "TopicName": p.get("topic_name") or (current and current.get("TopicName")),
            "LogsetId": p.get("logset_id") or (current and current.get("LogsetId")),
            "Enabled": p["enabled"],
            "DomainAreaConfigs": _normalized(p["domain_area_configs"]),
            "InheritDomainTags": p["inherit_domain_tags"],
        }
        before = (
            None
            if not current
            else {
                "TopicName": current.get("TopicName"),
                "LogsetId": current.get("LogsetId"),
                "Enabled": bool(current.get("Enabled")),
                "DomainAreaConfigs": _normalized(current.get("DomainAreaConfigs")),
                "InheritDomainTags": bool(current.get("InheritDomainTags")),
            }
        )
        if before == desired:
            module.exit_json(changed=False, topic=current)
        diff = maybe_diff(module, before, desired)
        if not module.check_mode:
            if immutable:
                module.sdk_call(client.DeleteClsLogTopic, delete_request(models, p, current["TopicId"], current["LogsetId"]))
                current = None
            if not current:
                p["topic_id"] = module.sdk_call(client.CreateClsLogTopic, create_request(models, p)).TopicId
                current = find_topic(module, client, models, p)
            else:
                domains_changed = before["DomainAreaConfigs"] != desired["DomainAreaConfigs"] or before["InheritDomainTags"] != desired["InheritDomainTags"]
                if domains_changed:
                    module.sdk_call(client.ManageClsTopicDomains, manage_domains_request(models, p, current["TopicId"], current["LogsetId"]))
            current_enabled = bool(current and current.get("Enabled"))
            if current_enabled != p["enabled"]:
                action = client.EnableClsLogTopic if p["enabled"] else client.DisableClsLogTopic
                builder = enable_request if p["enabled"] else disable_request
                module.sdk_call(action, builder(models, p, current["TopicId"], current["LogsetId"]))
            current = find_topic(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), topic=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
