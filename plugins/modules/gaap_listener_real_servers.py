#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: gaap_listener_real_servers
short_description: Reconcile Tencent Cloud GAAP listener origin bindings
version_added: "0.14.0"
description:
  - Replaces a TCP or UDP listener's complete origin binding set through BindListenerRealServers.
  - Empty O(real_servers) safely unbinds all origins without deleting the reusable origin resources.
options:
  listener_id: {type: str, required: true, description: GAAP TCP or UDP listener ID.}
  real_servers:
    type: list
    elements: dict
    default: []
    description: Complete desired origin binding set.
    suboptions:
      real_server_id: {type: str, required: true, description: Registered GAAP origin ID.}
      address: {type: str, required: true, description: Origin IP address or domain.}
      port: {type: int, required: true, description: Origin port.}
      weight: {type: int, default: 1, description: Weight for weighted round-robin.}
      failover_role: {type: str, choices: [master, slave], description: Role when listener failover is enabled.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.gaap_listener_real_servers:
    listener_id: listener-xxxxxxxx
    real_servers:
      - {real_server_id: rs-aaaaaaaa, address: 10.0.1.10, port: 3306, weight: 10}
      - {real_server_id: rs-bbbbbbbb, address: 10.0.1.11, port: 3306, weight: 20}
"""
RETURN = r"""real_servers: {description: Effective GAAP listener bindings., type: list, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.gaap.v20180529 import models, gaap_client

    return models, gaap_client


def canonical(values):
    result = []
    for value in values or []:
        result.append(
            {
                "RealServerId": value.get("RealServerId") or value.get("real_server_id"),
                "RealServerIP": value.get("RealServerIP") or value.get("address"),
                "RealServerPort": value.get("RealServerPort") if value.get("RealServerPort") is not None else value.get("port"),
                "RealServerWeight": value.get("RealServerWeight") if value.get("RealServerWeight") is not None else value.get("weight", 1),
                "RealServerFailoverRole": value.get("RealServerFailoverRole") or value.get("failover_role"),
            }
        )
    return sorted(result, key=lambda item: (item["RealServerId"], item["RealServerPort"]))


def describe(module, client, models, listener_id):
    request = models.DescribeListenerRealServersRequest()
    request.ListenerId = listener_id
    response = module.sdk_call(client.DescribeListenerRealServers, request)
    return canonical([item._serialize(allow_none=True) for item in (response.BindRealServerSet or [])])


def bind(module, client, models, listener_id, values):
    request = models.BindListenerRealServersRequest()
    request.ListenerId = listener_id
    request.RealServerBindSet = []
    for value in values:
        item = models.RealServerBindSetReq()
        item._deserialize(value)
        request.RealServerBindSet.append(item)
    module.sdk_call(client.BindListenerRealServers, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "listener_id": {"required": True},
            "real_servers": {
                "type": "list",
                "elements": "dict",
                "default": [],
                "options": {
                    "real_server_id": {"required": True},
                    "address": {"required": True},
                    "port": {"type": "int", "required": True},
                    "weight": {"type": "int", "default": 1},
                    "failover_role": {"choices": ["master", "slave"]},
                },
            },
        },
        supports_check_mode=True,
    )
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.GaapClient, "gaap.tencentcloudapi.com")
    try:
        current, wanted = describe(module, client, models, module.params["listener_id"]), canonical(module.params["real_servers"])
        if current == wanted:
            module.exit_json(changed=False, real_servers=current)
        diff = maybe_diff(module, current, wanted)
        if not module.check_mode:
            bind(module, client, models, module.params["listener_id"], wanted)
            current = describe(module, client, models, module.params["listener_id"])
        module.exit_json(changed=True, **(diff or {}), real_servers=current if not module.check_mode else wanted)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
