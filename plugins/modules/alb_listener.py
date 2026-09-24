#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: alb_listener
short_description: Manage Tencent Cloud ALB listeners
version_added: "0.14.0"
description:
  - Creates, updates, and deletes ALB HTTP, HTTPS, and QUIC listeners.
  - Identify an existing listener by C(listener_id), or by the combination of
    C(load_balancer_id), C(port), and C(protocol). Supply C(name), C(port),
    C(protocol), and C(default_actions) when creating a listener.
  - Port and protocol cannot be changed in place. Delete and recreate the
    listener explicitly if either must change.
options:
  state:
    description: Whether the listener should exist.
    type: str
    choices: [present, absent]
    default: present
  load_balancer_id:
    description: ID of the ALB load balancer that owns the listener.
    type: str
    required: true
  listener_id:
    description: ID of an existing listener to update or delete.
    type: str
  name:
    description: Listener name. Required when creating a listener.
    type: str
  port:
    description: Frontend port. Required on creation and immutable thereafter.
    type: int
  protocol:
    description: Listener protocol. Required on creation and immutable thereafter.
    type: str
    choices: [HTTP, HTTPS, QUIC]
  default_actions:
    description:
      - Default actions sent to the ALB API. Required on creation.
      - Each entry uses the Tencent Cloud C(DefaultAction) API structure;
        for example, C(Type=ForwardGroup) with C(TargetGroupConfig).
    type: list
    elements: dict
  certificate_ids:
    description: Server certificate IDs for HTTPS or QUIC listeners.
    type: list
    elements: str
  ca_enabled:
    description: Whether mutual TLS is enabled.
    type: bool
    default: false
  ca_certificate_ids:
    description: CA certificate IDs used when mutual TLS is enabled.
    type: list
    elements: str
  security_policy_id:
    description: TLS security policy ID.
    type: str
  gzip_enabled:
    description: Whether Gzip compression is enabled.
    type: bool
    default: true
  http2_enabled:
    description: Whether HTTP/2 is enabled for HTTPS.
    type: bool
  idle_timeout:
    description: Client connection idle timeout in seconds.
    type: int
    default: 15
  request_timeout:
    description: Backend request timeout in seconds.
    type: int
    default: 60
  x_forwarded_for:
    description: ALB API C(XForwardedForConfig) settings for forwarded headers.
    type: dict
  tags:
    description: Tags applied only when the listener is created.
    type: dict
  client_token:
    description: API request token used to deduplicate create or delete calls.
    type: str
attributes:
  check_mode:
    description: Predicts changes without sending create, update, or delete requests.
    support: full
  diff_mode:
    description: Returns a comparison of the observed and requested listener settings.
    support: partial
    details: API-assigned and other unmanaged fields are not part of the diff.
  idempotent:
    description: Compares observable listener settings before sending write requests.
    support: partial
    details: Waits for observable listener settings to converge after writes.

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- name: Ensure an HTTPS listener forwards to a target group
  susunola.tencentcloud.alb_listener:
    load_balancer_id: alb-xxxxxxxx
    name: https
    port: 443
    protocol: HTTPS
    certificate_ids: [cert-xxxxxxxx]
    default_actions:
      - Type: ForwardGroup
        TargetGroupConfig:
          TargetGroups: [{TargetGroupId: alb-tg-xxxxxxxx, Weight: 100}]

- name: Remove a listener by ID
  susunola.tencentcloud.alb_listener:
    load_balancer_id: alb-xxxxxxxx
    listener_id: lbl-xxxxxxxx
    state: absent
"""
RETURN = r"""
listener:
  description: Observed listener details, or C(null) when absent.
  type: dict
  returned: always
"""
import json
import time
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, fail_from_sdk_error


def _load():
    from tencentcloud.alb.v20251030 import models, alb_client

    return models, alb_client


def _model(cls, value):
    if value is None:
        return None
    x = cls()
    x.from_json_string(json.dumps(value))
    return x


def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        x = models.TagInfo()
        x.TagKey, x.TagValue = key, value
        result.append(x)
    return result


def list_request(models, p, next_token=None):
    r = models.DescribeListenersRequest()
    r.LoadBalancerId, r.MaxResults = p["load_balancer_id"], 100
    if p.get("listener_id"):
        r.ListenerIds = [p["listener_id"]]
    if next_token:
        r.NextToken = next_token
    return r


def describe_request(models, p, listener_id):
    r = models.DescribeListenerDetailRequest()
    r.LoadBalancerId, r.ListenerId = p["load_balancer_id"], listener_id
    return r


def _fill(r, models, p):
    r.DefaultActions = [_model(models.DefaultAction, x) for x in p.get("default_actions") or []]
    r.CaCertificateIds, r.CaEnabled, r.CertificateIds = p.get("ca_certificate_ids"), p["ca_enabled"], p.get("certificate_ids")
    r.GzipEnabled, r.Http2Enabled = p["gzip_enabled"], p.get("http2_enabled")
    r.IdleTimeout, r.RequestTimeout, r.ListenerName, r.SecurityPolicyId = p["idle_timeout"], p["request_timeout"], p["name"], p.get("security_policy_id")
    r.XForwardedForConfig = _model(models.XForwardedForConfig, p.get("x_forwarded_for"))
    r.ClientToken = p.get("client_token")
    return r


def create_request(models, p):
    r = _fill(models.CreateListenerRequest(), models, p)
    r.ListenerPort, r.ListenerProtocol, r.LoadBalancerId, r.Tags = p["port"], p["protocol"], p["load_balancer_id"], _tags(models, p.get("tags"))
    return r


def update_request(models, p, listener_id):
    r = _fill(models.ModifyListenerAttributesRequest(), models, p)
    r.ListenerId, r.LoadBalancerId = listener_id, p["load_balancer_id"]
    return r


def delete_request(models, p, listener_id):
    r = models.DeleteListenerRequest()
    r.LoadBalancerId, r.ListenerIds, r.ClientToken = p["load_balancer_id"], [listener_id], p.get("client_token")
    return r


def find(module, client, models, p):
    matches = []
    next_token = None
    seen_tokens = set()
    while True:
        response = module.sdk_call(client.DescribeListeners, list_request(models, p, next_token))
        if getattr(response, "Listeners", None) is None:
            module.fail_json(msg="ALB listener list is not observable")
        for item in response.Listeners:
            value = item._serialize(allow_none=True)
            if (p.get("listener_id") and value.get("ListenerId") == p["listener_id"]) or (
                not p.get("listener_id") and value.get("ListenerPort") == p.get("port") and value.get("ListenerProtocol") == p.get("protocol")
            ):
                matches.append(value)
        next_token = getattr(response, "NextToken", None)
        if not next_token:
            break
        if next_token in seen_tokens:
            module.fail_json(msg="ALB listener pagination returned a repeated token")
        seen_tokens.add(next_token)
    if len(matches) > 1:
        module.fail_json(msg="Multiple ALB listeners matched; specify listener_id")
    if not matches:
        return None
    value = module.sdk_call(client.DescribeListenerDetail, describe_request(models, p, matches[0]["ListenerId"]))._serialize(allow_none=True)
    value.pop("RequestId", None)
    if value.get("ListenerId") != matches[0]["ListenerId"]:
        module.fail_json(msg="ALB listener detail is not observable", listener_id=matches[0]["ListenerId"])
    return value


def comparable(v):
    return {
        "ListenerName": v.get("ListenerName"),
        "ListenerPort": v.get("ListenerPort"),
        "ListenerProtocol": v.get("ListenerProtocol"),
        "DefaultActions": v.get("DefaultActions") or [],
        "CertificateIds": sorted(v.get("CertificateIds") or []),
        "CaEnabled": bool(v.get("CaEnabled")),
        "CaCertificateIds": sorted(v.get("CaCertificateIds") or []),
        "SecurityPolicyId": v.get("SecurityPolicyId"),
        "GzipEnabled": bool(v.get("GzipEnabled")),
        "Http2Enabled": v.get("Http2Enabled"),
        "IdleTimeout": v.get("IdleTimeout"),
        "RequestTimeout": v.get("RequestTimeout"),
        "XForwardedForConfig": v.get("XForwardedForConfig"),
    }


def desired(p, current=None):
    old = comparable(current) if current else {}
    return {
        "ListenerName": p.get("name") or old.get("ListenerName"),
        "ListenerPort": p.get("port") if p.get("port") is not None else old.get("ListenerPort"),
        "ListenerProtocol": p.get("protocol") or old.get("ListenerProtocol"),
        "DefaultActions": p.get("default_actions") if p.get("default_actions") is not None else old.get("DefaultActions", []),
        "CertificateIds": sorted(p["certificate_ids"]) if p.get("certificate_ids") is not None else old.get("CertificateIds", []),
        "CaEnabled": p["ca_enabled"],
        "CaCertificateIds": sorted(p["ca_certificate_ids"]) if p.get("ca_certificate_ids") is not None else old.get("CaCertificateIds", []),
        "SecurityPolicyId": p.get("security_policy_id") if p.get("security_policy_id") is not None else old.get("SecurityPolicyId"),
        "GzipEnabled": p["gzip_enabled"],
        "Http2Enabled": p.get("http2_enabled") if p.get("http2_enabled") is not None else old.get("Http2Enabled"),
        "IdleTimeout": p["idle_timeout"],
        "RequestTimeout": p["request_timeout"],
        "XForwardedForConfig": p.get("x_forwarded_for") if p.get("x_forwarded_for") is not None else old.get("XForwardedForConfig"),
    }


def wait_for_listener(module, client, models, p, expected):
    deadline = time.monotonic() + max(0, p["waiter_timeout"])
    while True:
        observed = find(module, client, models, p)
        if (observed is None if expected is None else observed is not None and comparable(observed) == expected):
            return observed
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            module.fail_json(msg="ALB listener did not converge before timeout", listener=observed, expected=expected)
        time.sleep(min(max(0, p["waiter_delay"]), remaining))


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "load_balancer_id": {"required": True},
        "listener_id": {},
        "name": {},
        "port": {"type": "int"},
        "protocol": {"choices": ["HTTP", "HTTPS", "QUIC"]},
        "default_actions": {"type": "list", "elements": "dict"},
        "certificate_ids": {"type": "list", "elements": "str"},
        "ca_enabled": {"type": "bool", "default": False},
        "ca_certificate_ids": {"type": "list", "elements": "str"},
        "security_policy_id": {},
        "gzip_enabled": {"type": "bool", "default": True},
        "http2_enabled": {"type": "bool"},
        "idle_timeout": {"type": "int", "default": 15},
        "request_timeout": {"type": "int", "default": 60},
        "x_forwarded_for": {"type": "dict"},
        "tags": {"type": "dict"},
        "client_token": {"no_log": False},
    }
    module = TencentCloudModule(
        argument_spec=spec, required_one_of=[("listener_id", "port")], required_if=[("ca_enabled", True, ["ca_certificate_ids"])], supports_check_mode=True
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.AlbClient, "alb.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, listener=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteListener, delete_request(models, p, current["ListenerId"]))
                p["listener_id"] = current["ListenerId"]
                wait_for_listener(module, client, models, p, None)
            module.exit_json(changed=True, **(diff or {}), listener=None)
        if not current:
            missing = [k for k in ("name", "port", "protocol", "default_actions") if p.get(k) is None]
            if missing:
                module.fail_json(msg="creation parameters are required for a new ALB listener", missing=missing)
        before, target = comparable(current) if current else None, desired(p, current)
        if before == target:
            module.exit_json(changed=False, listener=current)
        if current:
            require_immutable_unchanged(module, before, target, ("ListenerPort", "ListenerProtocol"), "ALB listener")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            effective = dict(p)
            effective.update(
                {
                    "name": target["ListenerName"],
                    "default_actions": target["DefaultActions"],
                    "certificate_ids": target["CertificateIds"],
                    "ca_enabled": target["CaEnabled"],
                    "ca_certificate_ids": target["CaCertificateIds"],
                    "security_policy_id": target["SecurityPolicyId"],
                    "gzip_enabled": target["GzipEnabled"],
                    "http2_enabled": target["Http2Enabled"],
                    "idle_timeout": target["IdleTimeout"],
                    "request_timeout": target["RequestTimeout"],
                    "x_forwarded_for": target["XForwardedForConfig"],
                }
            )
            response = module.sdk_call(
                client.ModifyListenerAttributes if current else client.CreateListener,
                update_request(models, effective, current["ListenerId"]) if current else create_request(models, effective),
            )
            p["listener_id"] = current["ListenerId"] if current else response.ListenerId
            current = wait_for_listener(module, client, models, p, target)
        module.exit_json(changed=True, **(diff or {}), listener=current if not module.check_mode else target)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
