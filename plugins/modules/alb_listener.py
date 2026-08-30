#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: alb_listener
short_description: Manage Tencent Cloud ALB listeners
version_added: "0.14.0"
description: Creates, updates and deletes ALB HTTP, HTTPS and QUIC listeners with default target-group actions.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  load_balancer_id: {type: str, required: true, description: ALB ID.}
  listener_id: {type: str, description: Existing listener ID.}
  name: {type: str, description: Listener name.}
  port: {type: int, description: Frontend port; immutable after creation.}
  protocol: {type: str, choices: [HTTP, HTTPS, QUIC], description: Listener protocol; immutable after creation.}
  default_actions: {type: list, elements: dict, description: SDK DefaultAction payloads normally forwarding to target groups.}
  certificate_ids: {type: list, elements: str, description: Server certificate IDs.}
  ca_enabled: {type: bool, default: false, description: Enable mutual TLS.}
  ca_certificate_ids: {type: list, elements: str, description: CA certificate IDs.}
  security_policy_id: {type: str, description: TLS security policy ID.}
  gzip_enabled: {type: bool, default: true, description: Enable Gzip compression.}
  http2_enabled: {type: bool, description: Enable HTTP/2 for HTTPS.}
  idle_timeout: {type: int, default: 15, description: Idle timeout in seconds.}
  request_timeout: {type: int, default: 60, description: Backend request timeout in seconds.}
  x_forwarded_for: {type: dict, description: SDK XForwardedForConfig payload.}
  tags: {type: dict, description: Creation-time tags.}
  client_token: {type: str, description: Optional idempotency token.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.alb_listener:
    load_balancer_id: alb-xxxxxxxx
    name: https
    port: 443
    protocol: HTTPS
    certificate_ids: [cert-xxxxxxxx]
    default_actions:
      - Type: ForwardGroup
        TargetGroupConfig:
          TargetGroups: [{TargetGroupId: alb-tg-xxxxxxxx, Weight: 100}]
'''
RETURN = r'''listener: {description: Effective ALB listener metadata., type: dict, returned: always}'''
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.alb.v20251030 import models, alb_client
    return models, alb_client
def _model(cls, value):
    if value is None: return None
    x = cls(); x.from_json_string(json.dumps(value)); return x
def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()): x = models.TagInfo(); x.TagKey, x.TagValue = key, value; result.append(x)
    return result
def list_request(models, p):
    r = models.DescribeListenersRequest(); r.LoadBalancerId, r.MaxResults = p["load_balancer_id"], 100
    if p.get("listener_id"): r.ListenerIds = [p["listener_id"]]
    return r
def describe_request(models, p, listener_id):
    r = models.DescribeListenerDetailRequest(); r.LoadBalancerId, r.ListenerId = p["load_balancer_id"], listener_id; return r
def _fill(r, models, p):
    r.DefaultActions = [_model(models.DefaultAction, x) for x in p.get("default_actions") or []]; r.CaCertificateIds, r.CaEnabled, r.CertificateIds = p.get("ca_certificate_ids"), p["ca_enabled"], p.get("certificate_ids"); r.GzipEnabled, r.Http2Enabled = p["gzip_enabled"], p.get("http2_enabled"); r.IdleTimeout, r.RequestTimeout, r.ListenerName, r.SecurityPolicyId = p["idle_timeout"], p["request_timeout"], p["name"], p.get("security_policy_id"); r.XForwardedForConfig = _model(models.XForwardedForConfig, p.get("x_forwarded_for")); r.ClientToken = p.get("client_token"); return r
def create_request(models, p):
    r = _fill(models.CreateListenerRequest(), models, p); r.ListenerPort, r.ListenerProtocol, r.LoadBalancerId, r.Tags = p["port"], p["protocol"], p["load_balancer_id"], _tags(models, p.get("tags")); return r
def update_request(models, p, listener_id):
    r = _fill(models.ModifyListenerAttributesRequest(), models, p); r.ListenerId, r.LoadBalancerId = listener_id, p["load_balancer_id"]; return r
def delete_request(models, p, listener_id):
    r = models.DeleteListenerRequest(); r.LoadBalancerId, r.ListenerIds, r.ClientToken = p["load_balancer_id"], [listener_id], p.get("client_token"); return r
def find(module, client, models, p):
    response = module.sdk_call(client.DescribeListeners, list_request(models, p)); matches = []
    for item in response.Listeners or []:
        value = item._serialize(allow_none=True)
        if (p.get("listener_id") and value.get("ListenerId") == p["listener_id"]) or (not p.get("listener_id") and value.get("ListenerPort") == p.get("port") and value.get("ListenerProtocol") == p.get("protocol")): matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple ALB listeners matched; specify listener_id")
    if not matches: return None
    value = module.sdk_call(client.DescribeListenerDetail, describe_request(models, p, matches[0]["ListenerId"]))._serialize(allow_none=True); value.pop("RequestId", None); return value
def comparable(v): return {"ListenerName": v.get("ListenerName"), "ListenerPort": v.get("ListenerPort"), "ListenerProtocol": v.get("ListenerProtocol"), "DefaultActions": v.get("DefaultActions") or [], "CertificateIds": sorted(v.get("CertificateIds") or []), "CaEnabled": bool(v.get("CaEnabled")), "CaCertificateIds": sorted(v.get("CaCertificateIds") or []), "SecurityPolicyId": v.get("SecurityPolicyId"), "GzipEnabled": bool(v.get("GzipEnabled")), "Http2Enabled": v.get("Http2Enabled"), "IdleTimeout": v.get("IdleTimeout"), "RequestTimeout": v.get("RequestTimeout"), "XForwardedForConfig": v.get("XForwardedForConfig")}
def desired(p, current=None):
    old = comparable(current) if current else {}; return {"ListenerName": p.get("name") or old.get("ListenerName"), "ListenerPort": p.get("port") if p.get("port") is not None else old.get("ListenerPort"), "ListenerProtocol": p.get("protocol") or old.get("ListenerProtocol"), "DefaultActions": p.get("default_actions") if p.get("default_actions") is not None else old.get("DefaultActions", []), "CertificateIds": sorted(p["certificate_ids"]) if p.get("certificate_ids") is not None else old.get("CertificateIds", []), "CaEnabled": p["ca_enabled"], "CaCertificateIds": sorted(p["ca_certificate_ids"]) if p.get("ca_certificate_ids") is not None else old.get("CaCertificateIds", []), "SecurityPolicyId": p.get("security_policy_id") if p.get("security_policy_id") is not None else old.get("SecurityPolicyId"), "GzipEnabled": p["gzip_enabled"], "Http2Enabled": p.get("http2_enabled") if p.get("http2_enabled") is not None else old.get("Http2Enabled"), "IdleTimeout": p["idle_timeout"], "RequestTimeout": p["request_timeout"], "XForwardedForConfig": p.get("x_forwarded_for") if p.get("x_forwarded_for") is not None else old.get("XForwardedForConfig")}
def run_module():
    spec = {"state": {"choices": ["present", "absent"], "default": "present"}, "load_balancer_id": {"required": True}, "listener_id": {}, "name": {}, "port": {"type": "int"}, "protocol": {"choices": ["HTTP", "HTTPS", "QUIC"]}, "default_actions": {"type": "list", "elements": "dict"}, "certificate_ids": {"type": "list", "elements": "str"}, "ca_enabled": {"type": "bool", "default": False}, "ca_certificate_ids": {"type": "list", "elements": "str"}, "security_policy_id": {}, "gzip_enabled": {"type": "bool", "default": True}, "http2_enabled": {"type": "bool"}, "idle_timeout": {"type": "int", "default": 15}, "request_timeout": {"type": "int", "default": 60}, "x_forwarded_for": {"type": "dict"}, "tags": {"type": "dict"}, "client_token": {"no_log": False}}
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("listener_id", "port")], required_if=[("ca_enabled", True, ["ca_certificate_ids"])], supports_check_mode=True); p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.AlbClient, "alb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, listener=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteListener, delete_request(models, p, current["ListenerId"]))
            module.exit_json(changed=True, **(diff or {}), listener=None)
        if not current:
            missing = [k for k in ("name", "port", "protocol", "default_actions") if p.get(k) is None]
            if missing: module.fail_json(msg="creation parameters are required for a new ALB listener", missing=missing)
        before, target = comparable(current) if current else None, desired(p, current)
        if before == target: module.exit_json(changed=False, listener=current)
        if current: require_immutable_unchanged(module, before, target, ("ListenerPort", "ListenerProtocol"), "ALB listener")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            effective = dict(p); effective.update({"name": target["ListenerName"], "default_actions": target["DefaultActions"], "certificate_ids": target["CertificateIds"], "ca_enabled": target["CaEnabled"], "ca_certificate_ids": target["CaCertificateIds"], "security_policy_id": target["SecurityPolicyId"], "gzip_enabled": target["GzipEnabled"], "http2_enabled": target["Http2Enabled"], "idle_timeout": target["IdleTimeout"], "request_timeout": target["RequestTimeout"], "x_forwarded_for": target["XForwardedForConfig"]})
            response = module.sdk_call(client.ModifyListenerAttributes if current else client.CreateListener, update_request(models, effective, current["ListenerId"]) if current else create_request(models, effective)); p["listener_id"] = current["ListenerId"] if current else response.ListenerId; current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), listener=current if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__ == "__main__": main()
