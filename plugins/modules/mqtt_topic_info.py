#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: mqtt_topic_info
short_description: Gather a Tencent Cloud MQTT topic
version_added: "1.4.0"
description: Returns one MQTT topic through the exact topic lookup API.
options:
  instance_id: {description: MQTT instance ID., type: str, required: true}
  topic: {description: Topic name., type: str, required: true}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.mqtt_topic_info:
    region: ap-guangzhou
    instance_id: mqtt-xxxxxxxx
    topic: orders
'''
RETURN = r'''
topics: {description: Matching topic as an empty or single-element list., returned: always, type: list, elements: dict}
topic_info: {description: MQTT topic metadata or null., returned: always, type: dict}
request_id: {description: Request ID returned by the API., returned: always, type: str}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.modules.mqtt_topic import describe_request

def run_module():
    module = TencentCloudModule(argument_spec={"instance_id": {"required": True}, "topic": {"required": True}}, supports_check_mode=True)
    module.require_sdk()
    try:
        from tencentcloud.mqtt.v20240516 import models, mqtt_client
        client = module.create_client(mqtt_client.MqttClient, "mqtt.tencentcloudapi.com")
        try:
            response = module.sdk_call(client.DescribeTopic, describe_request(models, module.params))
        except Exception as exc:
            if is_not_found(exc) or "not exist" in str(exc).lower():
                module.exit_json(changed=False, topics=[], topic_info=None, request_id=getattr(exc, "request_id", None))
            raise
        value = response._serialize(allow_none=True)
        request_id = value.pop("RequestId", getattr(response, "RequestId", None))
        module.exit_json(changed=False, topics=[value], topic_info=value, request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
