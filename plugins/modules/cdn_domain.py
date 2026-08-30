#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cdn_domain
short_description: Manage Tencent Cloud CDN domains
version_added: "0.13.0"
description:
  - Add, start, stop and delete Tencent Cloud CDN acceleration domains
    through the C(cdn.v20180606) API.
  - This module is idempotent. Running it twice leaves the domain unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
  - A domain is identified by its O(domain) name. Origin, service type,
    project and acceleration area are reconciled on existing domains.
options:
  state:
    description:
      - C(present) adds the domain with V(AddCdnDomain) when it does not
        exist.
      - C(absent) deletes the domain with V(DeleteCdnDomain).
      - C(running) starts a stopped domain with V(StartCdnDomain).
      - C(stopped) stops a running domain with V(StopCdnDomain).
    type: str
    choices: [present, absent, running, stopped]
    default: present
  domain:
    description:
      - Domain name to accelerate, e.g. C(cdn.example.com), written to
        V(AddCdnDomainRequest.Domain).
      - Required.
    type: str
  service_type:
    description:
      - Business type of the domain, written to
        V(AddCdnDomainRequest.ServiceType).
      - C(web) is a static acceleration site, C(download) is download
        acceleration, C(media) is VOD streaming.
      - Required when adding the domain.
    type: str
    choices: [web, download, media]
  origins:
    description:
      - Origin addresses, written to V(Origin.Origins), e.g.
        C([origin.example.com]) or C([1.2.3.4]).
      - Required when adding the domain.
    type: list
    elements: str
  origin_type:
    description:
      - Type of the origins, written to V(Origin.OriginType).
      - C(domain) is a domain origin, C(ip) is an IP origin, C(cos) is a
        COS bucket origin.
      - Required when adding the domain.
    type: str
    choices: [domain, ip, cos]
  origin_protocol:
    description:
      - Protocol used when pulling from the origin, written to
        V(Origin.OriginPullProtocol).
      - C(http) and C(https) force the protocol, C(follow) follows the
        client request.
      - Updated on existing domains when supplied.
    type: str
    choices: [http, https, follow]
  backup_origins:
    description:
      - Backup origin addresses, written to V(Origin.BackupOrigins).
      - Updated on existing domains when supplied.
    type: list
    elements: str
  project_id:
    description:
      - Project the domain belongs to, written to
        V(AddCdnDomainRequest.ProjectId).
      - Updated on existing domains when supplied.
    type: int
  area:
    description:
      - Acceleration area, written to V(AddCdnDomainRequest.Area).
      - C(mainland) accelerates in mainland China, C(overseas) outside,
        C(global) everywhere.
      - Updated on existing domains when supplied.
    type: str
    choices: [mainland, overseas, global]
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
  - Requires the C(tencentcloud-sdk-python-cdn) package on the controller.
  - The O(domain) must be owned and the origin must be reachable before
    V(AddCdnDomain) succeeds.
  - O(state=absent) deletes the domain configuration; the domain can be
    re-added afterwards.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Add a CDN domain with a domain origin
  susunola.tencentcloud.cdn_domain:
    region: ap-guangzhou
    state: present
    domain: cdn.example.com
    service_type: web
    origins:
      - origin.example.com
    origin_type: domain
    origin_protocol: http

- name: Stop the domain
  susunola.tencentcloud.cdn_domain:
    region: ap-guangzhou
    state: stopped
    domain: cdn.example.com

- name: Start it again
  susunola.tencentcloud.cdn_domain:
    region: ap-guangzhou
    state: running
    domain: cdn.example.com

- name: Delete the domain
  susunola.tencentcloud.cdn_domain:
    region: ap-guangzhou
    state: absent
    domain: cdn.example.com
'''

RETURN = r'''
domain:
  description: The domain as reported by V(DescribeDomains) after the
    operation.
  returned: success
  type: dict
  sample:
    Domain: cdn.example.com
    Status: online
    ServiceType: web
    Cname: cdn.example.com.cdn.dnsv1.com
    Origin:
      Origins:
        - origin.example.com
      OriginType: domain
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_cdn():
    from tencentcloud.cdn.v20180606 import models, cdn_client
    return models, cdn_client


def build_describe_request(models, domain):
    request = models.DescribeDomainsRequest()
    request.Limit = 100
    if domain:
        domain_filter = models.DomainFilter()
        domain_filter.Name = "domain"
        domain_filter.Value = [domain]
        request.Filters = [domain_filter]
    return request


def _first(collection):
    return collection[0] if collection else None


def find_domain(module, client, models, domain):
    """Return the matching domain dict or None."""
    request = build_describe_request(models, domain)
    response = module.sdk_call(client.DescribeDomains, request)
    item = _first(response.Domains or [])
    if item is None:
        return None
    current = item._serialize(allow_none=True)
    if current.get("Domain") == domain:
        return current
    return None


def build_add_request(models, params):
    request = models.AddCdnDomainRequest()
    request.Domain = params["domain"]
    request.ServiceType = params["service_type"]
    origin = models.Origin()
    origin.Origins = params["origins"]
    origin.OriginType = params["origin_type"]
    if params["origin_protocol"]:
        origin.OriginPullProtocol = params["origin_protocol"]
    if params["backup_origins"]:
        origin.BackupOrigins = params["backup_origins"]
    request.Origin = origin
    if params["project_id"] is not None:
        request.ProjectId = params["project_id"]
    if params["area"]:
        request.Area = params["area"]
    return request


def _origin(models, params):
    origin = models.Origin()
    origin.Origins = params["origins"]
    origin.OriginType = params["origin_type"]
    if params["origin_protocol"]:
        origin.OriginPullProtocol = params["origin_protocol"]
    if params["backup_origins"] is not None:
        origin.BackupOrigins = params["backup_origins"]
    return origin


def build_update_request(models, params):
    request = models.UpdateDomainConfigRequest()
    request.Domain = params["domain"]
    if params["origins"] is not None or params["origin_type"] is not None or params["origin_protocol"] is not None or params["backup_origins"] is not None:
        request.Origin = _origin(models, params)
    if params["service_type"] is not None:
        request.ServiceType = params["service_type"]
    if params["project_id"] is not None:
        request.ProjectId = params["project_id"]
    if params["area"] is not None:
        request.Area = params["area"]
    return request


def _add(module, client, models, params):
    request = build_add_request(models, params)
    module.sdk_call(client.AddCdnDomain, request)


def _update(module, client, models, params):
    module.sdk_call(client.UpdateDomainConfig, build_update_request(models, params))


def _desired_config(params):
    desired = {}
    mapping = (("service_type", "ServiceType"), ("project_id", "ProjectId"), ("area", "Area"))
    for source, target in mapping:
        if params[source] is not None:
            desired[target] = params[source]
    origin = {}
    for source, target in (("origins", "Origins"), ("origin_type", "OriginType"), ("origin_protocol", "OriginPullProtocol"), ("backup_origins", "BackupOrigins")):
        if params[source] is not None:
            origin[target] = params[source]
    if origin:
        desired["Origin"] = origin
    return desired


def _current_config(current, desired):
    result = {}
    for key, value in desired.items():
        if key != "Origin":
            result[key] = current.get(key)
            continue
        existing = current.get("Origin") or {}
        result["Origin"] = {name: existing.get(name) for name in value}
    return result


def _delete(module, client, models, domain):
    request = models.DeleteCdnDomainRequest()
    request.Domain = domain
    module.sdk_call(client.DeleteCdnDomain, request)


def _start(module, client, models, domain):
    request = models.StartCdnDomainRequest()
    request.Domain = domain
    module.sdk_call(client.StartCdnDomain, request)


def _stop(module, client, models, domain):
    request = models.StopCdnDomainRequest()
    request.Domain = domain
    module.sdk_call(client.StopCdnDomain, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent", "running", "stopped"], "default": "present"},
            "domain": {"type": "str"},
            "service_type": {"type": "str", "choices": ["web", "download", "media"]},
            "origins": {"type": "list", "elements": "str"},
            "origin_type": {"type": "str", "choices": ["domain", "ip", "cos"]},
            "origin_protocol": {"type": "str", "choices": ["http", "https", "follow"]},
            "backup_origins": {"type": "list", "elements": "str"},
            "project_id": {"type": "int"},
            "area": {"type": "str", "choices": ["mainland", "overseas", "global"]},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    domain = module.params["domain"]

    if not domain:
        module.fail_json(msg="domain is required to identify the CDN domain")

    models, cdn_client = _load_cdn()
    client = module.create_client(cdn_client.CdnClient, "cdn.tencentcloudapi.com")

    try:
        current = find_domain(module, client, models, domain)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="CDN domain already absent")
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete CDN domain")
        _delete(module, client, models, domain)
        module.exit_json(changed=True, **(diff or {}), domain=None, msg="CDN domain deleted")

    if state in ("running", "stopped"):
        if current is None:
            module.fail_json(
                msg="Domain not found; use state=present to add it",
                domain=domain,
            )
        status = current.get("Status")
        if state == "running":
            if status == "online":
                module.exit_json(changed=False, domain=current, msg="CDN domain already online")
            if module.check_mode:
                module.exit_json(changed=True, domain=current, msg="Would start CDN domain")
            _start(module, client, models, domain)
            module.exit_json(changed=True, domain=current, msg="CDN domain started")
        # state == "stopped"
        if status == "offline":
            module.exit_json(changed=False, domain=current, msg="CDN domain already stopped")
        if module.check_mode:
            module.exit_json(changed=True, domain=current, msg="Would stop CDN domain")
        _stop(module, client, models, domain)
        module.exit_json(changed=True, domain=current, msg="CDN domain stopped")

    # state == present
    if current is None:
        missing = [key for key in ("domain", "service_type", "origins", "origin_type") if not module.params[key]]
        if missing:
            module.fail_json(msg="%s is required when adding a CDN domain" % ", ".join(missing))
        desired = {
            "Domain": domain,
            "ServiceType": module.params["service_type"],
            "Origins": module.params["origins"],
        }
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would add CDN domain")
        _add(module, client, models, module.params)
        current = find_domain(module, client, models, domain)
        module.exit_json(changed=True, **(diff or {}), domain=current, msg="CDN domain added")

    desired = _desired_config(module.params)
    before = _current_config(current, desired)
    if before == desired:
        module.exit_json(changed=False, domain=current, msg="CDN domain is up to date")
    diff = maybe_diff(module, before, desired)
    if module.check_mode:
        module.exit_json(changed=True, **(diff or {}), domain=current, msg="Would update CDN domain")
    update_params = dict(module.params)
    existing_origin = current.get("Origin") or {}
    for source, target in (("origins", "Origins"), ("origin_type", "OriginType"), ("origin_protocol", "OriginPullProtocol"), ("backup_origins", "BackupOrigins")):
        if update_params[source] is None:
            update_params[source] = existing_origin.get(target)
    _update(module, client, models, update_params)
    current = find_domain(module, client, models, domain)
    module.exit_json(changed=True, **(diff or {}), domain=current, msg="CDN domain updated")


def main():
    run_module()


if __name__ == "__main__":
    main()
