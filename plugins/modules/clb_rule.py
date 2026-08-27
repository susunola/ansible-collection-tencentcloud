#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: clb_rule
short_description: Manage Tencent Cloud CLB L7 forwarding rules
version_added: "0.12.0"
description:
  - Create, update and delete HTTP/HTTPS forwarding rules (locations) on a
    CLB listener through the C(clb.v20180317) API.
  - This module is idempotent. Running it twice leaves the rule unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
  - A rule is identified by the combination of O(load_balancer_id),
    O(listener_id), O(domain) and O(url), or directly by O(location_id).
    Use the O(location_id) returned here as the O(location_id) input of
    M(susunola.tencentcloud.clb_listener_target) to manage the rule's
    targets.
options:
  state:
    description:
      - C(present) creates the rule when it does not exist and updates its
        attributes when it does.
      - C(absent) deletes the rule.
    type: str
    choices: [present, absent]
    default: present
  load_balancer_id:
    description:
      - ID of the load balancer the listener belongs to, e.g. C(lb-xxxxxxxx).
    type: str
    required: true
  listener_id:
    description:
      - ID of the HTTP/HTTPS listener, e.g. C(lbl-xxxxxxxx).
    type: str
    required: true
  location_id:
    description:
      - ID of an existing forwarding rule, e.g. C(loc-xxxxxxxx).
      - When given, the rule is operated on directly; otherwise it is matched
        by O(domain) and O(url).
    type: str
  domain:
    description:
      - Domain of the rule, written to V(RuleInput.Domain).
      - Required when creating a rule and used to match existing rules.
    type: str
  url:
    description:
      - URL path of the rule, e.g. C(/api), written to V(RuleInput.Url) and
        V(ModifyRuleRequest.Url).
    type: str
    required: true
  scheduler:
    description:
      - Balancing method, written to V(RuleInput.Scheduler) and
        V(ModifyRuleRequest.Scheduler).
    type: str
    choices: [WRR, LEAST_CONN, IP_HASH]
  session_expire_time:
    description:
      - Session persistence time in seconds, written to
        V(RuleInput.SessionExpireTime).
    type: int
  forward_type:
    description:
      - Forwarding type of the rule, written to V(RuleInput.ForwardType).
    type: str
    choices: [TRADITIONAL]
  http2:
    description:
      - Enable HTTP/2 for the rule, written to V(RuleInput.Http2).
    type: bool
  cookie_name:
    description:
      - Cookie name for session persistence, written to
        V(ModifyRuleRequest.CookieName).
    type: str
  health_check:
    description:
      - Health check configuration as a dict with the same suboptions as
        M(susunola.tencentcloud.clb_listener).
    type: dict
    suboptions:
      health_switch:
        description: Whether to enable the health check.
        type: bool
      interval_time:
        description: Probe interval in seconds, 2-60.
        type: int
      health_num:
        description: Healthy threshold, 2-10.
        type: int
      un_health_num:
        description: Unhealthy threshold, 2-10.
        type: int
      time_out:
        description: Probe response timeout in seconds, 2-60.
        type: int
      check_type:
        description: Protocol of the probe.
        type: str
        choices: [TCP, HTTP, HTTPS, GRPC, PING, CUSTOM]
      check_port:
        description: Port of the probe.
        type: int
      http_check_path:
        description: Path of the HTTP probe.
        type: str
      http_check_domain:
        description: Domain of the HTTP probe.
        type: str
      http_check_method:
        description: Method of the HTTP probe.
        type: str
        choices: [HEAD, GET]
      http_code:
        description: Expected HTTP status code of the probe.
        type: int
      http_version:
        description: HTTP version of the probe.
        type: str
        choices: [HTTP/1.0, HTTP/1.1]
  retries:
    description: Number of retries for transient SDK failures.
    type: int
    default: 5
  waiter_delay:
    description: Seconds to wait between state-polling attempts.
    type: int
    default: 5
  waiter_timeout:
    description: Overall timeout in seconds for state polling.
    type: int
    default: 120
  user_agent:
    description:
      - Value appended to the SDK User-Agent header so API usage can be
        attributed to this collection.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-clb) package on the controller.
  - Rule creation is asynchronous; use
    M(susunola.tencentcloud.clb_load_balancer) or the V(DescribeTaskStatus)
    API to wait for the operation to complete before changing targets.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create an L7 rule for /api on the HTTPS listener
  susunola.tencentcloud.clb_rule:
    region: ap-guangzhou
    state: present
    load_balancer_id: lb-xxxxxxxx
    listener_id: lbl-xxxxxxxx
    domain: api.example.com
    url: /api
    scheduler: WRR
    session_expire_time: 300
    health_check:
      health_switch: true
      http_check_path: /healthz
      interval_time: 10

- name: Register targets for the rule (rule-level integration)
  susunola.tencentcloud.clb_listener_target:
    region: ap-guangzhou
    load_balancer_id: lb-xxxxxxxx
    listener_id: lbl-xxxxxxxx
    location_id: "{{ rule.location_id }}"
    targets:
      - instance_id: ins-aaaaaaaa
        port: 8080

- name: Delete the rule
  susunola.tencentcloud.clb_rule:
    region: ap-guangzhou
    state: absent
    load_balancer_id: lb-xxxxxxxx
    listener_id: lbl-xxxxxxxx
    domain: api.example.com
    url: /api
'''

RETURN = r'''
rule:
  description: The rule as reported by V(DescribeListeners) after the
    operation.
  returned: success
  type: dict
  sample:
    LocationId: loc-xxxxxxxx
    Domain: api.example.com
    Url: /api
    Scheduler: WRR
    SessionExpireTime: 300
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff

# Maps the health_check suboption names to the HealthCheck model attributes.
HEALTH_CHECK_FIELDS = {
    "health_switch": "HealthSwitch",
    "interval_time": "IntervalTime",
    "health_num": "HealthNum",
    "un_health_num": "UnHealthNum",
    "time_out": "TimeOut",
    "check_type": "CheckType",
    "check_port": "CheckPort",
    "http_check_path": "HttpCheckPath",
    "http_check_domain": "HttpCheckDomain",
    "http_check_method": "HttpCheckMethod",
    "http_code": "HttpCode",
    "http_version": "HttpVersion",
}


def _load_clb():
    from tencentcloud.clb.v20180317 import models, clb_client
    return models, clb_client


def build_describe_request(models, load_balancer_id, listener_id):
    request = models.DescribeListenersRequest()
    request.LoadBalancerId = load_balancer_id
    request.ListenerIds = [listener_id]
    return request


def _first(collection):
    return collection[0] if collection else None


def find_rule(module, client, models, load_balancer_id, listener_id, location_id, domain, url):
    """Return the matching forwarding rule dict or None."""
    request = build_describe_request(models, load_balancer_id, listener_id)
    response = module.sdk_call(client.DescribeListeners, request)
    listener = _first(response.Listeners or [])
    if listener is None:
        return None
    rules = listener.Rules or []
    for rule in rules:
        current = rule._serialize(allow_none=True)
        if location_id:
            if current.get("LocationId") == location_id:
                return current
            continue
        if current.get("Domain") == domain and current.get("Url") == url:
            return current
    return None


def build_health_check(models, health_check):
    """Build a HealthCheck model from the module's health_check dict."""
    if not health_check:
        return None
    model = models.HealthCheck()
    for option, attribute in sorted(HEALTH_CHECK_FIELDS.items()):
        value = health_check.get(option)
        if value is None:
            continue
        if isinstance(value, bool):
            value = int(value)
        setattr(model, attribute, value)
    return model


def health_check_differs(current_health_check, health_check):
    """Return True when any provided health_check suboption differs."""
    if not health_check:
        return False
    current = current_health_check or {}
    for option, attribute in sorted(HEALTH_CHECK_FIELDS.items()):
        value = health_check.get(option)
        if value is None:
            continue
        current_value = current.get(attribute)
        if isinstance(value, bool):
            current_value = bool(current_value)
        if current_value != value:
            return True
    return False


def _create(module, client, models, params):
    request = models.CreateRuleRequest()
    request.LoadBalancerId = params["load_balancer_id"]
    request.ListenerId = params["listener_id"]
    rule = models.RuleInput()
    rule.Domain = params["domain"]
    rule.Url = params["url"]
    for key, attr in (
        ("scheduler", "Scheduler"),
        ("session_expire_time", "SessionExpireTime"),
        ("forward_type", "ForwardType"),
        ("cookie_name", "CookieName"),
    ):
        value = params[key]
        if value is not None:
            setattr(rule, attr, value)
    if params["http2"]:
        rule.Http2 = True
    if params["health_check"]:
        rule.HealthCheck = build_health_check(models, params["health_check"])
    request.Rules = [rule]
    response = module.sdk_call(client.CreateRule, request)
    return _first(response.LocationIds or [])


def _update(module, client, models, params, location_id):
    request = models.ModifyRuleRequest()
    request.LoadBalancerId = params["load_balancer_id"]
    request.ListenerId = params["listener_id"]
    request.LocationId = location_id
    request.Url = params["url"]
    for key, attr in (
        ("scheduler", "Scheduler"),
        ("session_expire_time", "SessionExpireTime"),
        ("forward_type", "ForwardType"),
        ("cookie_name", "CookieName"),
    ):
        value = params[key]
        if value is not None:
            setattr(request, attr, value)
    if params["health_check"]:
        request.HealthCheck = build_health_check(models, params["health_check"])
    module.sdk_call(client.ModifyRule, request)


def _delete(module, client, models, params, location_id):
    request = models.DeleteRuleRequest()
    request.LoadBalancerId = params["load_balancer_id"]
    request.ListenerId = params["listener_id"]
    request.LocationIds = [location_id]
    request.Domain = params["domain"]
    request.Url = params["url"]
    module.sdk_call(client.DeleteRule, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "load_balancer_id": {"type": "str", "required": True},
            "listener_id": {"type": "str", "required": True},
            "location_id": {"type": "str"},
            "domain": {"type": "str"},
            "url": {"type": "str", "required": True},
            "scheduler": {"type": "str", "choices": ["WRR", "LEAST_CONN", "IP_HASH"]},
            "session_expire_time": {"type": "int"},
            "forward_type": {"type": "str", "choices": ["TRADITIONAL"]},
            "http2": {"type": "bool"},
            "cookie_name": {"type": "str"},
            "health_check": {
                "type": "dict",
                "options": {
                    "health_switch": {"type": "bool"},
                    "interval_time": {"type": "int"},
                    "health_num": {"type": "int"},
                    "un_health_num": {"type": "int"},
                    "time_out": {"type": "int"},
                    "check_type": {"type": "str", "choices": ["TCP", "HTTP", "HTTPS", "GRPC", "PING", "CUSTOM"]},
                    "check_port": {"type": "int"},
                    "http_check_path": {"type": "str"},
                    "http_check_domain": {"type": "str"},
                    "http_check_method": {"type": "str", "choices": ["HEAD", "GET"]},
                    "http_code": {"type": "int"},
                    "http_version": {"type": "str", "choices": ["HTTP/1.0", "HTTP/1.1"]},
                },
            },
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    load_balancer_id = module.params["load_balancer_id"]
    listener_id = module.params["listener_id"]
    location_id = module.params["location_id"]
    domain = module.params["domain"]
    url = module.params["url"]

    if not location_id and not domain:
        module.fail_json(msg="location_id or domain is required to identify the rule")

    models, clb_client = _load_clb()
    client = module.create_client(clb_client.ClbClient, "clb.tencentcloudapi.com")

    try:
        current = find_rule(module, client, models, load_balancer_id, listener_id, location_id, domain, url)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="Forwarding rule already absent")
        target_id = current["LocationId"]
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete forwarding rule")
        _delete(module, client, models, module.params, target_id)
        module.exit_json(changed=True, **(diff or {}), rule=None, msg="Forwarding rule deleted")

    # state == present
    if current is None:
        if not domain:
            module.fail_json(msg="domain is required when creating a forwarding rule")
        desired = {
            "Domain": domain,
            "Url": url,
            "Scheduler": module.params["scheduler"] or "WRR",
        }
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create forwarding rule")
        created_id = _create(module, client, models, module.params)
        current = find_rule(module, client, models, load_balancer_id, listener_id, created_id, None, None)
        module.exit_json(changed=True, **(diff or {}), rule=current, msg="Forwarding rule created")

    target_id = current["LocationId"]
    changes = []
    if current.get("Url") != url:
        changes.append("url")
    scheduler = module.params["scheduler"]
    if scheduler is not None and current.get("Scheduler") != scheduler:
        changes.append("scheduler")
    session_expire_time = module.params["session_expire_time"]
    if session_expire_time is not None and current.get("SessionExpireTime") != session_expire_time:
        changes.append("session_expire_time")
    forward_type = module.params["forward_type"]
    if forward_type is not None and current.get("ForwardType") != forward_type:
        changes.append("forward_type")
    cookie_name = module.params["cookie_name"]
    if cookie_name is not None and current.get("CookieName") != cookie_name:
        changes.append("cookie_name")
    if health_check_differs(current.get("HealthCheck"), module.params["health_check"]):
        changes.append("health_check")

    if not changes:
        module.exit_json(changed=False, rule=current, msg="Forwarding rule is up to date")

    diff = maybe_diff(module, current, {
        "Url": url,
        "Scheduler": scheduler if scheduler is not None else current.get("Scheduler"),
        "SessionExpireTime": (
            session_expire_time if session_expire_time is not None else current.get("SessionExpireTime")
        ),
        "ForwardType": forward_type if forward_type is not None else current.get("ForwardType"),
        "CookieName": cookie_name if cookie_name is not None else current.get("CookieName"),
    })
    if module.check_mode:
        module.exit_json(changed=True, **(diff or {}), msg="Would update forwarding rule")

    _update(module, client, models, module.params, target_id)
    updated = find_rule(module, client, models, load_balancer_id, listener_id, target_id, None, None)
    module.exit_json(changed=True, **(diff or {}), rule=updated, msg="Forwarding rule updated")


def main():
    run_module()


if __name__ == "__main__":
    main()
