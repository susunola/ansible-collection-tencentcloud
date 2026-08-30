#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: teo_acceleration_domain
short_description: Manage Tencent Cloud EdgeOne acceleration domains
version_added: "0.14.0"
description: Creates, updates, enables, disables and deletes EdgeOne acceleration domains.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired domain state.}
  zone_id: {type: str, required: true, description: EdgeOne zone ID.}
  domain_name: {type: str, required: true, description: Acceleration domain name.}
  origin_type: {type: str, choices: [IP_DOMAIN, COS, AWS_S3, ORIGIN_GROUP, VOD], default: IP_DOMAIN, description: Origin type.}
  origin: {type: str, description: "Origin address, origin-group ID, or VOD application ID."}
  host_header: {type: str, description: Custom origin Host header for IP_DOMAIN origins.}
  origin_protocol: {type: str, choices: [FOLLOW, HTTP, HTTPS], default: FOLLOW, description: Origin protocol.}
  http_origin_port: {type: int, default: 80, description: HTTP origin port.}
  https_origin_port: {type: int, default: 443, description: HTTPS origin port.}
  ipv6_status: {type: str, choices: [follow, 'on', 'off'], default: follow, description: IPv6 access state.}
  enabled: {type: bool, default: true, description: Whether the acceleration domain is online.}
  force: {type: bool, default: false, description: Force disabling or deletion when associated resources exist.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Accelerate an application through an origin group
  susunola.tencentcloud.teo_acceleration_domain:
    region: ap-guangzhou
    zone_id: zone-xxxxxxxx
    domain_name: app.example.com
    origin_type: ORIGIN_GROUP
    origin: origin-xxxxxxxx
    origin_protocol: HTTPS
'''

RETURN = r'''acceleration_domain: {description: EdgeOne acceleration-domain metadata., type: dict, returned: always}'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.teo.v20220901 import models, teo_client
    return models, teo_client


def describe_request(models, p, offset=0):
    request = models.DescribeAccelerationDomainsRequest(); request.ZoneId, request.Offset, request.Limit = p["zone_id"], offset, 200
    item = models.AdvancedFilter(); item.Name, item.Values = "domain-name", [p["domain_name"]]; request.Filters = [item]; return request


def _origin_info(models, p):
    item = models.OriginInfo(); item.OriginType, item.Origin = p["origin_type"], p["origin"]
    if p["origin_type"] in ("COS", "AWS_S3"): item.PrivateAccess = "off"
    if p["origin_type"] == "IP_DOMAIN" and p.get("host_header") is not None: item.HostHeader = p["host_header"]
    return item


def create_request(models, p):
    request = models.CreateAccelerationDomainRequest(); request.ZoneId, request.DomainName = p["zone_id"], p["domain_name"]
    request.OriginInfo, request.OriginProtocol = _origin_info(models, p), p["origin_protocol"]
    request.HttpOriginPort, request.HttpsOriginPort, request.IPv6Status = p["http_origin_port"], p["https_origin_port"], p["ipv6_status"]; return request


def update_request(models, p):
    request = models.ModifyAccelerationDomainRequest(); request.ZoneId, request.DomainName = p["zone_id"], p["domain_name"]
    request.OriginInfo, request.OriginProtocol = _origin_info(models, p), p["origin_protocol"]
    request.HttpOriginPort, request.HttpsOriginPort, request.IPv6Status = p["http_origin_port"], p["https_origin_port"], p["ipv6_status"]; return request


def status_request(models, p):
    request = models.ModifyAccelerationDomainStatusesRequest(); request.ZoneId, request.DomainNames = p["zone_id"], [p["domain_name"]]
    request.Status, request.Force = "online" if p["enabled"] else "offline", p["force"]; return request


def delete_request(models, p):
    request = models.DeleteAccelerationDomainsRequest(); request.ZoneId, request.DomainNames, request.Force = p["zone_id"], [p["domain_name"]], p["force"]; return request


def find_domain(module, client, models, p):
    offset = 0; matches = []
    while True:
        response = module.sdk_call(client.DescribeAccelerationDomains, describe_request(models, p, offset)); values = list(response.AccelerationDomains or [])
        matches.extend(value._serialize(allow_none=True) for value in values if value.DomainName == p["domain_name"])
        offset += len(values)
        if offset >= int(response.TotalCount or 0) or not values: break
    if len(matches) > 1: module.fail_json(msg="Multiple EdgeOne acceleration domains matched")
    return matches[0] if matches else None


def desired(p):
    return {"OriginType": p["origin_type"], "Origin": p["origin"], "HostHeader": p.get("host_header") or "", "OriginProtocol": p["origin_protocol"], "HttpOriginPort": p["http_origin_port"], "HttpsOriginPort": p["https_origin_port"], "IPv6Status": p["ipv6_status"], "DomainStatus": "online" if p["enabled"] else "offline"}


def current_values(current):
    origin = current.get("OriginDetail") or {}
    return {"OriginType": origin.get("OriginType"), "Origin": origin.get("Origin"), "HostHeader": origin.get("HostHeader") or "", "OriginProtocol": current.get("OriginProtocol"), "HttpOriginPort": current.get("HttpOriginPort"), "HttpsOriginPort": current.get("HttpsOriginPort"), "IPv6Status": current.get("IPv6Status"), "DomainStatus": current.get("DomainStatus")}


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "zone_id": {"required": True}, "domain_name": {"required": True}, "origin_type": {"choices": ["IP_DOMAIN", "COS", "AWS_S3", "ORIGIN_GROUP", "VOD"], "default": "IP_DOMAIN"}, "origin": {}, "host_header": {}, "origin_protocol": {"choices": ["FOLLOW", "HTTP", "HTTPS"], "default": "FOLLOW"}, "http_origin_port": {"type": "int", "default": 80}, "https_origin_port": {"type": "int", "default": 443}, "ipv6_status": {"choices": ["follow", "on", "off"], "default": "follow"}, "enabled": {"type": "bool", "default": True}, "force": {"type": "bool", "default": False}}, supports_check_mode=True)
    p = module.params
    if p["state"] == "present" and not p.get("origin"): module.fail_json(msg="origin is required when state=present")
    if p.get("host_header") and p["origin_type"] != "IP_DOMAIN": module.fail_json(msg="host_header is only supported for IP_DOMAIN origins")
    if not 1 <= p["http_origin_port"] <= 65535 or not 1 <= p["https_origin_port"] <= 65535: module.fail_json(msg="origin ports must be between 1 and 65535")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.TeoClient, "teo.tencentcloudapi.com")
    try:
        current = find_domain(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, acceleration_domain=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteAccelerationDomains, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), acceleration_domain=current if module.check_mode else None)
        target = desired(p); before = current_values(current) if current else None
        if before == target: module.exit_json(changed=False, acceleration_domain=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            created = not current
            if created: module.sdk_call(client.CreateAccelerationDomain, create_request(models, p))
            elif any(before[key] != target[key] for key in target if key != "DomainStatus"): module.sdk_call(client.ModifyAccelerationDomain, update_request(models, p))
            if (created and not p["enabled"]) or (not created and before["DomainStatus"] != target["DomainStatus"]): module.sdk_call(client.ModifyAccelerationDomainStatuses, status_request(models, p))
            current = find_domain(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), acceleration_domain=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
