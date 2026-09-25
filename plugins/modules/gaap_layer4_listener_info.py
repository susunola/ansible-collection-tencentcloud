#!/usr/bin/python
# -*- coding: utf-8 -*-
# Hand-written: GAAP exposes layer-4 listeners through two sibling list
# actions (DescribeTCPListeners and DescribeUDPListeners) with identical
# request and response shapes, so the generator -- which maps one write
# module to one action -- cannot express this module. Do not regenerate;
# edit this file instead.
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: gaap_layer4_listener_info
short_description: Gather information about Tencent Cloud GAAP TCP and UDP listeners
version_added: "1.5.0"
description:
  - Returns GAAP (Global Application Acceleration Platform) layer-4 listeners visible in a Tencent Cloud region.
  - Layer-4 listeners have no single list API; the module queries C(DescribeTCPListeners) and C(DescribeUDPListeners)
    and merges the results, marking each listener with the protocol it came from.
options:
  protocol:
    description:
      - Restrict the query to one protocol.
      - By default both protocols are queried and the results are merged.
    type: str
    choices: [TCP, UDP]
  proxy_id:
    description: Connection (proxy) ID the listeners belong to. API field C(ProxyId).
    type: str
  listener_id:
    description: Listener ID to return. API field C(ListenerId).
    type: str
  listener_name:
    description: Listener name to return. API field C(ListenerName).
    type: str
  port:
    description: Listener port to return. API field C(Port).
    type: int
  page_size:
    description: Number of results requested per API call.
    type: int
    default: 100
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
attributes:
  check_mode:
    description:
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  idempotent:
    description:
      - Read-only, so every run returns the current state and never changes
        the target, and a repeated run reports C(changed=false).
    support: full
seealso:
  - module: susunola.tencentcloud.gaap_layer4_listener
    description: Manage Tencent Cloud GAAP TCP and UDP listeners.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: List every layer-4 listener
  susunola.tencentcloud.gaap_layer4_listener_info:
    region: ap-guangzhou

- name: List only the TCP listeners of one connection
  susunola.tencentcloud.gaap_layer4_listener_info:
    region: ap-guangzhou
    proxy_id: link-xxxxxxxx
    protocol: TCP

- name: Find the UDP listener on port 53
  susunola.tencentcloud.gaap_layer4_listener_info:
    region: ap-guangzhou
    protocol: UDP
    port: 53
'''

RETURN = r'''
listeners:
  description: Matching GAAP layer-4 listeners, each carrying the C(protocol) it was read from.
  returned: always
  type: list
  elements: dict
total_count:
  description: Number of listeners reported by the API across the queried protocols.
  returned: always
  type: int
request_id:
  description: Request ID of the last API call, for cross-referencing cloud audit logs.
  returned: always
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.paging import Paginator
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile, create_credential, sdk_call, serialize_sdk_object,
    tencentcloud_argument_spec,
)

# The two layer-4 list actions are identical in shape: keeping the pairing
# here means adding a protocol later is a one-line change.
PROTOCOL_ACTIONS = (
    ("TCP", "DescribeTCPListeners", "DescribeTCPListenersRequest"),
    ("UDP", "DescribeUDPListeners", "DescribeUDPListenersRequest"),
)


def build_request(models, request_name, params, offset, limit):
    request = getattr(models, request_name)()
    request.Offset = offset
    request.Limit = limit
    for field in ("ProxyId", "ListenerId", "ListenerName", "Port"):
        value = params.get(field)
        if value is not None:
            setattr(request, field, value)
    return request


def query_protocol(module, models, client, action, request_name, params, page_size):
    """Return (listeners, total_count, request_id) for one protocol."""
    paginator = Paginator(
        page_size,
        lambda offset, limit: build_request(models, request_name, params, offset, limit),
        lambda request: sdk_call(module, getattr(client, action), request),
        lambda response: response.ListenerSet,
        lambda response: response.TotalCount,
    )
    item_set, total_count = paginator.fetch_all()
    return item_set, total_count, paginator.request_id


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "protocol": {"type": "str", "choices": ["TCP", "UDP"]},
        "proxy_id": {"type": "str"},
        "listener_id": {"type": "str"},
        "listener_name": {"type": "str"},
        "port": {"type": "int"},
        "page_size": {"type": "int", "default": 100},
    })
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )
    try:
        from tencentcloud.gaap.v20180529 import models, gaap_client
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-gaap package is required.")

    client = gaap_client.GaapClient(
        create_credential(module), module.params["region"],
        create_client_profile(module, "gaap.tencentcloudapi.com"),
    )
    params = {
        "ProxyId": module.params["proxy_id"],
        "ListenerId": module.params["listener_id"],
        "ListenerName": module.params["listener_name"],
        "Port": module.params["port"],
    }
    wanted = module.params["protocol"]
    page_size = module.params["page_size"]

    listeners, total_count, request_id = [], 0, None
    for protocol, action, request_name in PROTOCOL_ACTIONS:
        if wanted and protocol != wanted:
            continue
        items, count, last_request_id = query_protocol(
            module, models, client, action, request_name, params, page_size)
        for item in items:
            listener = serialize_sdk_object(item)
            listener["protocol"] = protocol
            listeners.append(listener)
        total_count += count
        if last_request_id:
            request_id = last_request_id
    module.exit_json(changed=False, listeners=listeners,
                     total_count=total_count, request_id=request_id)


def main():
    run_module()


if __name__ == "__main__":
    main()
