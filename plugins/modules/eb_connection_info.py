#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: eb_connection_info
short_description: Gather Tencent Cloud EventBridge connections
version_added: "1.4.0"
description: Lists EventBridge connections with complete pagination and optional exact identity filtering.
options:
  event_bus_id: {description: Event bus ID., type: str, required: true}
  connection_id: {description: Connection ID., type: str}
  name: {description: Exact connection name., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.eb_connection_info:
    region: ap-guangzhou
    event_bus_id: eb-l65vlc2
    name: orders-source
'''
RETURN = r'''
connections: {description: Matching connections., returned: always, type: list, elements: dict}
connection: {description: The single matching connection when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error

def list_request(models, event_bus_id, offset=0, limit=100):
    request = models.ListConnectionsRequest()
    request.EventBusId, request.Offset, request.Limit = event_bus_id, offset, limit
    return request

def matches(value, connection_id=None, name=None):
    return (connection_id is None or value.get("ConnectionId") == connection_id) and (name is None or value.get("ConnectionName") == name)

def run_module():
    module = TencentCloudModule(
        argument_spec={"event_bus_id": {"required": True}, "connection_id": {}, "name": {}},
        mutually_exclusive=[("connection_id", "name")], supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    try:
        from tencentcloud.eb.v20210416 import eb_client, models
        client = module.create_client(eb_client.EbClient, "eb.tencentcloudapi.com")
        offset, values, request_id = 0, [], None
        while True:
            response = module.sdk_call(client.ListConnections, list_request(models, p["event_bus_id"], offset))
            request_id = getattr(response, "RequestId", None)
            page = list(response.Connections or [])
            values.extend(value for value in (item._serialize(allow_none=True) for item in page) if matches(value, p.get("connection_id"), p.get("name")))
            offset += len(page)
            total = getattr(response, "TotalCount", None)
            if not page or (total is not None and offset >= int(total)) or (total is None and len(page) < 100):
                break
        module.exit_json(changed=False, connections=values, connection=values[0] if len(values) == 1 else None, request_id=request_id)
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
