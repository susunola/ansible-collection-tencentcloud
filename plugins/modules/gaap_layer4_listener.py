#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: gaap_layer4_listener
short_description: Manage Tencent Cloud GAAP TCP and UDP listeners
version_added: "0.14.0"
description: Creates, updates and deletes one idempotent GAAP layer-4 listener on a proxy or proxy group.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  listener_id: {type: str, description: Existing listener ID.}
  proxy_id: {type: str, description: Parent GAAP proxy ID.}
  group_id: {type: str, description: Parent GAAP proxy group ID.}
  name: {type: str, description: Listener name.}
  protocol: {type: str, choices: [TCP, UDP], required: true, description: Listener protocol.}
  port: {type: int, description: Listener port; immutable after creation.}
  scheduler: {type: str, choices: [rr, wrr, lc, lrtt], default: rr, description: Origin scheduling algorithm.}
  real_server_type: {type: str, choices: [IP, DOMAIN], default: IP, description: Origin identity type.}
  health_check: {type: bool, default: false, description: Enable origin health checks.}
  delay_loop: {type: int, description: Health-check interval in seconds.}
  connect_timeout: {type: int, description: Health-check timeout in seconds.}
  healthy_threshold: {type: int, description: Consecutive successes required.}
  unhealthy_threshold: {type: int, description: Consecutive failures required.}
  failover: {type: bool, default: false, description: Enable master/standby origin mode.}
  client_ip_method: {type: int, choices: [0, 1], description: TCP client IP method; 0 is TOA and 1 is Proxy Protocol.}
  udp_check_type: {type: str, choices: [PORT, PING], description: UDP health-check type.}
  udp_check_port: {type: int, description: UDP probe port.}
  send_context: {type: str, description: UDP probe request text.}
  receive_context: {type: str, description: UDP probe expected response text.}
  force_delete_bound: {type: bool, default: false, description: Allow deletion when origins remain bound.}
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.gaap_layer4_listener:
    proxy_id: proxy-xxxxxxxx
    protocol: TCP
    name: mysql
    port: 3306
    scheduler: wrr
    health_check: true
"""
RETURN = r"""listener: {description: Effective GAAP listener., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import changed, maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.gaap.v20180529 import models, gaap_client

    return models, gaap_client


def describe(module, client, models, params):
    cls = models.DescribeTCPListenersRequest if params["protocol"] == "TCP" else models.DescribeUDPListenersRequest
    request = cls()
    request.ProxyId, request.GroupId = params.get("proxy_id"), params.get("group_id")
    request.ListenerId, request.ListenerName, request.Port = params.get("listener_id"), params.get("name"), params.get("port")
    request.Offset, request.Limit = 0, 100
    method = client.DescribeTCPListeners if params["protocol"] == "TCP" else client.DescribeUDPListeners
    values = module.sdk_call(method, request).ListenerSet or []
    matches = []
    for item in values:
        value = item._serialize(allow_none=True)
        if params.get("listener_id") and value.get("ListenerId") == params["listener_id"]:
            matches.append(value)
        elif not params.get("listener_id") and value.get("ListenerName") == params.get("name") and value.get("Port") == params.get("port"):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple GAAP listeners matched; specify listener_id")
    return matches[0] if matches else None


def target(params):
    names = {
        "name": "ListenerName",
        "port": "Port",
        "scheduler": "Scheduler",
        "real_server_type": "RealServerType",
        "delay_loop": "DelayLoop",
        "connect_timeout": "ConnectTimeout",
        "healthy_threshold": "HealthyThreshold",
        "unhealthy_threshold": "UnhealthyThreshold",
        "client_ip_method": "ClientIPMethod",
        "udp_check_type": "CheckType",
        "udp_check_port": "CheckPort",
        "send_context": "SendContext",
        "receive_context": "RecvContext",
    }
    value = {api: params[key] for key, api in names.items() if params.get(key) is not None}
    value["HealthCheck"], value["FailoverSwitch"] = int(params["health_check"]), int(params["failover"])
    return value


def create(module, client, models, params, wanted):
    payload = dict(wanted)
    payload["Ports"] = [payload.pop("Port")]
    payload["ProxyId"], payload["GroupId"] = params.get("proxy_id"), params.get("group_id")
    cls = models.CreateTCPListenersRequest if params["protocol"] == "TCP" else models.CreateUDPListenersRequest
    request = cls()
    request._deserialize(payload)
    method = client.CreateTCPListeners if params["protocol"] == "TCP" else client.CreateUDPListeners
    return module.sdk_call(method, request).ListenerIds[0]


def update(module, client, models, params, current, wanted):
    payload = {key: value for key, value in wanted.items() if key not in ("Port", "RealServerType", "ClientIPMethod")}
    payload.update({"ListenerId": current["ListenerId"], "ProxyId": params.get("proxy_id"), "GroupId": params.get("group_id")})
    cls = models.ModifyTCPListenerAttributeRequest if params["protocol"] == "TCP" else models.ModifyUDPListenerAttributeRequest
    request = cls()
    request._deserialize(payload)
    method = client.ModifyTCPListenerAttribute if params["protocol"] == "TCP" else client.ModifyUDPListenerAttribute
    module.sdk_call(method, request)


def delete(module, client, models, params, listener_id):
    request = models.DeleteListenersRequest()
    request.ListenerIds = [listener_id]
    request.ProxyId, request.GroupId = params.get("proxy_id"), params.get("group_id")
    request.Force = int(params["force_delete_bound"])
    module.sdk_call(client.DeleteListeners, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "listener_id": {},
            "proxy_id": {},
            "group_id": {},
            "name": {},
            "protocol": {"choices": ["TCP", "UDP"], "required": True},
            "port": {"type": "int"},
            "scheduler": {"choices": ["rr", "wrr", "lc", "lrtt"], "default": "rr"},
            "real_server_type": {"choices": ["IP", "DOMAIN"], "default": "IP"},
            "health_check": {"type": "bool", "default": False},
            "delay_loop": {"type": "int"},
            "connect_timeout": {"type": "int"},
            "healthy_threshold": {"type": "int"},
            "unhealthy_threshold": {"type": "int"},
            "failover": {"type": "bool", "default": False},
            "client_ip_method": {"type": "int", "choices": [0, 1]},
            "udp_check_type": {"choices": ["PORT", "PING"]},
            "udp_check_port": {"type": "int"},
            "send_context": {},
            "receive_context": {},
            "force_delete_bound": {"type": "bool", "default": False},
        },
        required_one_of=[("listener_id", "name"), ("proxy_id", "group_id")],
        mutually_exclusive=[("proxy_id", "group_id")],
        supports_check_mode=True,
    )
    p = module.params
    if not p.get("listener_id") and p.get("port") is None:
        module.fail_json(msg="port is required when resolving a listener by name")
    if p["state"] == "present" and (not p.get("name") or p.get("port") is None):
        module.fail_json(msg="name and port are required to create a listener")
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.GaapClient, "gaap.tencentcloudapi.com")
    try:
        current = describe(module, client, models, p)
        if p["state"] == "absent":
            if current is None:
                module.exit_json(changed=False, listener=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                delete(module, client, models, p, current["ListenerId"])
            module.exit_json(changed=True, **(diff or {}), listener=current if module.check_mode else None)
        wanted = target(p)
        if current is not None:
            before = {key: current.get(key) for key in wanted}
            if not changed(before, wanted):
                module.exit_json(changed=False, listener=current)
            if current.get("Port") != wanted.get("Port") or current.get("RealServerType") != wanted.get("RealServerType"):
                module.fail_json(msg="GAAP listener port and real_server_type are immutable; replace the listener", listener=current)
        else:
            before = None
        diff = maybe_diff(module, before, wanted)
        if not module.check_mode:
            if current is None:
                p["listener_id"] = create(module, client, models, p, wanted)
            else:
                update(module, client, models, p, current, wanted)
                p["listener_id"] = current["ListenerId"]
            current = describe(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), listener=current if not module.check_mode else wanted)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
