#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cdn_cls_log_topic_info
short_description: Gather information about Tencent Cloud CDN real-time CLS log topics
version_added: "1.4.0"
description:
  - Returns CDN real-time CLS log topics and their domain/area bindings.
  - This module is the read side for C(cdn_cls_log_topic).
options:
  topic_id:
    description: CLS topic ID to return.
    type: str
  topic_name:
    description: CLS topic name used to narrow the returned topics.
    type: str
  logset_id:
    description: CLS logset ID used to narrow the returned topics and fetch domain bindings.
    type: str
  channel:
    description: CDN access channel.
    type: str
    choices: [cdn, ecdn]
    default: cdn
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: List CDN real-time CLS log topics
  susunola.tencentcloud.cdn_cls_log_topic_info:
    region: ap-guangzhou

- name: Find a CDN real-time CLS log topic by name
  susunola.tencentcloud.cdn_cls_log_topic_info:
    region: ap-guangzhou
    topic_name: cdn-access
    logset_id: logset-xxxxxxxx
'''

RETURN = r'''
topics:
  description: Matching CDN CLS log topics, including domain-area bindings when a logset can be resolved.
  returned: always
  type: list
  elements: dict
topic:
  description: First matching topic when C(topic_id) or C(topic_name) is supplied.
  returned: always
  type: dict
request_id:
  description: Request ID returned by the API, for cross-referencing cloud audit logs.
  returned: always
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile,
    create_credential,
    sdk_call,
    serialize_sdk_object,
    tencentcloud_argument_spec,
)


def list_topics_request(models, channel):
    request = models.ListClsLogTopicsRequest()
    request.Channel = channel
    return request


def list_domains_request(models, topic_id, logset_id, channel):
    request = models.ListClsTopicDomainsRequest()
    request.TopicId = topic_id
    request.LogsetId = logset_id
    request.Channel = channel
    return request


def _topic_candidates(response):
    values = []
    default_logset = serialize_sdk_object(response.Logset) if getattr(response, "Logset", None) else {}
    for topic in getattr(response, "Topics", None) or []:
        item = serialize_sdk_object(topic)
        item["LogsetId"] = default_logset.get("LogsetId")
        values.append(item)
    for extra in getattr(response, "ExtraLogset", None) or []:
        logset = serialize_sdk_object(extra.Logset) if getattr(extra, "Logset", None) else {}
        for topic in getattr(extra, "Topics", None) or []:
            item = serialize_sdk_object(topic)
            item["LogsetId"] = logset.get("LogsetId")
            values.append(item)
    return values


def _matches(item, topic_id, topic_name, logset_id):
    if topic_id and item.get("TopicId") != topic_id:
        return False
    if topic_name and item.get("TopicName") != topic_name:
        return False
    if logset_id and item.get("LogsetId") != logset_id:
        return False
    return True


def _attach_domains(module, client, models, topic, channel):
    logset_id = topic.get("LogsetId")
    topic_id = topic.get("TopicId")
    if not topic_id or not logset_id:
        return topic
    response = sdk_call(module, client.ListClsTopicDomains, list_domains_request(models, topic_id, logset_id, channel))
    topic["DomainAreaConfigs"] = [
        serialize_sdk_object(item) for item in getattr(response, "DomainAreaConfigs", None) or []
    ]
    topic["InheritDomainTags"] = bool(getattr(response, "InheritDomainTags", False))
    return topic


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "topic_id": {"type": "str"},
        "topic_name": {"type": "str"},
        "logset_id": {"type": "str"},
        "channel": {"type": "str", "choices": ["cdn", "ecdn"], "default": "cdn"},
    })
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    try:
        from tencentcloud.cdn.v20180606 import cdn_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-cdn package is required.")

    client = cdn_client.CdnClient(
        create_credential(module),
        module.params["region"],
        create_client_profile(module, "cdn.tencentcloudapi.com"),
    )
    response = sdk_call(module, client.ListClsLogTopics, list_topics_request(models, module.params["channel"]))
    topics = [
        _attach_domains(module, client, models, item, module.params["channel"])
        for item in _topic_candidates(response)
        if _matches(item, module.params["topic_id"], module.params["topic_name"], module.params["logset_id"])
    ]
    selected = topics[0] if (module.params["topic_id"] or module.params["topic_name"]) and topics else None
    module.exit_json(
        changed=False,
        topics=topics,
        topic=selected,
        request_id=getattr(response, "RequestId", None),
    )


def main():
    run_module()


if __name__ == "__main__":
    main()
