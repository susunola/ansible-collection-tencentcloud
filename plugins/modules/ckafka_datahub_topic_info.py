#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: ckafka_datahub_topic_info
short_description: Gather Tencent Cloud CKafka Datahub topics
version_added: "1.4.0"
description:
  - Returns a CKafka Datahub elastic topic by name.
  - Returned credentials are suppressed.
options:
  name:
    description: Datahub topic resource name.
    type: str
    required: true
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Read a CKafka Datahub topic
  susunola.tencentcloud.ckafka_datahub_topic_info:
    region: ap-guangzhou
    name: 1250000000-orders-stream
'''

RETURN = r'''
topics:
  description: Matching Datahub topics. Empty when the topic is not found.
  returned: always
  type: list
  elements: dict
topic:
  description: Matching Datahub topic, without returned credentials.
  returned: always
  type: dict
request_id:
  description: Request ID returned by the API, for cross-referencing cloud audit logs.
  returned: always
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile,
    create_credential,
    sdk_call,
    tencentcloud_argument_spec,
)


def build_request(models, name):
    request = models.DescribeDatahubTopicRequest()
    request.Name = name
    return request


def sanitize(value):
    return {key: item for key, item in (value or {}).items() if key not in ("UserName", "Password")}


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({"name": {"type": "str", "required": True}})
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    try:
        from tencentcloud.ckafka.v20190819 import ckafka_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-ckafka package is required.")

    client = ckafka_client.CkafkaClient(create_credential(module), module.params["region"], create_client_profile(module, "ckafka.tencentcloudapi.com"))
    try:
        response = sdk_call(module, client.DescribeDatahubTopic, build_request(models, module.params["name"]))
    except Exception as exc:
        if is_not_found(exc):
            module.exit_json(changed=False, topics=[], topic=None, request_id=getattr(exc, "request_id", None))
        raise
    topic = sanitize(response.Result._serialize(allow_none=True)) if getattr(response, "Result", None) else None
    module.exit_json(changed=False, topics=[topic] if topic else [], topic=topic, request_id=getattr(response, "RequestId", None))


def main():
    run_module()


if __name__ == "__main__":
    main()
