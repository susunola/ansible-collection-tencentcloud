#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: gaap_layer4_listener_info
short_description: Gather Tencent Cloud GAAP TCP or UDP listeners
version_added: "1.4.0"
description: Lists GAAP layer-4 listeners with complete pagination and optional parent or exact identity filtering.
options:
  protocol: {description: Listener protocol., type: str, choices: [TCP, UDP], required: true}
  listener_id: {description: Listener ID., type: str}
  proxy_id: {description: Parent GAAP proxy ID., type: str}
  group_id: {description: Parent GAAP proxy group ID., type: str}
  name: {description: Exact listener name., type: str}
  port: {description: Listener port., type: int}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.gaap_layer4_listener_info:
    region: ap-guangzhou
    proxy_id: proxy-xxxxxxxx
    protocol: TCP
'''
RETURN = r'''
listeners: {description: Matching layer-4 listeners., returned: always, type: list, elements: dict}
listener: {description: The single matching listener when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error

def describe_request(models, p, offset=0, limit=100):
    cls = models.DescribeTCPListenersRequest if p["protocol"] == "TCP" else models.DescribeUDPListenersRequest
    request = cls()
    request.ProxyId, request.GroupId = p.get("proxy_id"), p.get("group_id")
    request.ListenerId, request.ListenerName, request.Port = p.get("listener_id"), p.get("name"), p.get("port")
    request.Offset, request.Limit = offset, limit
    return request

def matches(value, p):
    return all((
        p.get("listener_id") is None or value.get("ListenerId") == p["listener_id"],
        p.get("name") is None or value.get("ListenerName") == p["name"],
        p.get("port") is None or value.get("Port") == p["port"],
    ))

def run_module():
    module = TencentCloudModule(argument_spec={
        "protocol": {"choices": ["TCP", "UDP"], "required": True}, "listener_id": {},
        "proxy_id": {}, "group_id": {}, "name": {}, "port": {"type": "int"},
    }, mutually_exclusive=[("proxy_id", "group_id")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    try:
        from tencentcloud.gaap.v20180529 import gaap_client, models
        client = module.create_client(gaap_client.GaapClient, "gaap.tencentcloudapi.com")
        method = client.DescribeTCPListeners if p["protocol"] == "TCP" else client.DescribeUDPListeners
        offset, values, request_id = 0, [], None
        while True:
            response = module.sdk_call(method, describe_request(models, p, offset))
            request_id = getattr(response, "RequestId", None)
            page = list(response.ListenerSet or [])
            values.extend(value for value in (item._serialize(allow_none=True) for item in page) if matches(value, p))
            offset += len(page)
            total = getattr(response, "TotalCount", None)
            if not page or (total is not None and offset >= int(total)) or (total is None and len(page) < 100):
                break
        module.exit_json(changed=False, listeners=values, listener=values[0] if len(values) == 1 else None, request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
