#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: gaap_proxy
short_description: Manage Tencent Cloud GAAP proxies
version_added: "0.13.0"
description:
  - Create, rename, start, stop and destroy Tencent Cloud GAAP (Global
    Application Accelerator) proxies through the C(gaap.v20180529) API.
  - This module is idempotent. Running it twice leaves the proxy unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
  - A proxy is identified by O(proxy_id) or by O(name). The connection
    configuration (access region, real server region, bandwidth,
    concurrency) is only applied at creation; resizing is out of scope for
    this module.
options:
  state:
    description:
      - C(present) creates the proxy when it does not exist and renames it
        when O(name) differs.
      - C(absent) destroys the proxy with V(DestroyProxies).
      - C(running) opens a closed proxy with V(OpenProxies).
      - C(stopped) closes a running proxy with V(CloseProxies).
    type: str
    choices: [present, absent, running, stopped]
    default: present
  proxy_id:
    description:
      - ID of an existing proxy, e.g. C(proxy-xxxxxxxx).
      - When given, the module operates on that proxy; otherwise it is
        matched by O(name).
    type: str
  name:
    description:
      - Name of the proxy, written to V(CreateProxyRequest.ProxyName) and
        V(ModifyProxiesAttributeRequest.ProxyName).
    type: str
  access_region:
    description:
      - Access region of the proxy, e.g. C(ap-guangzhou), written to
        V(CreateProxyRequest.AccessRegion).
      - Required when creating the proxy.
    type: str
  real_server_region:
    description:
      - Origin region of the proxy, e.g. C(ap-hongkong), written to
        V(CreateProxyRequest.RealServerRegion).
      - Required when creating the proxy outside a proxy group.
    type: str
  bandwidth:
    description:
      - Bandwidth cap in Mbps, written to V(CreateProxyRequest.Bandwidth).
      - Required when creating the proxy.
    type: int
  concurrent:
    description:
      - Concurrency cap in ten-thousands of connections, written to
        V(CreateProxyRequest.Concurrent).
      - Required when creating the proxy.
    type: int
  project_id:
    description:
      - Project the proxy belongs to, written to
        V(CreateProxyRequest.ProjectId).
      - Only applied at creation.
    type: int
  billing_type:
    description:
      - Billing mode, written to V(CreateProxyRequest.BillingType).
      - C(0) bills by bandwidth, C(1) by traffic.
      - Only applied at creation.
    type: int
    choices: [0, 1]
  network_type:
    description:
      - Network type, written to V(CreateProxyRequest.NetworkType).
      - C(normal) is standard BGP, C(cn2) is premium BGP, C(triple) is
        triple-network.
      - Only applied at creation.
    type: str
    choices: [normal, cn2, triple]
  ip_address_version:
    description:
      - IP version, written to V(CreateProxyRequest.IPAddressVersion).
      - Only applied at creation.
    type: str
    choices: [IPv4, IPv6]
  group_id:
    description:
      - Proxy group the proxy belongs to, written to
        V(CreateProxyRequest.GroupId).
      - Only applied at creation.
    type: str
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
  - Requires the C(tencentcloud-sdk-python-gaap) package on the controller.
  - GAAP proxies are billed while present; destroy them as soon as they are
    no longer needed to avoid unnecessary charges.
  - O(state=absent) destroys the proxy; this cannot be undone.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a 20 Mbps GAAP proxy
  susunola.tencentcloud.gaap_proxy:
    region: ap-guangzhou
    state: present
    name: prod-gaap
    access_region: ap-guangzhou
    real_server_region: ap-hongkong
    bandwidth: 20
    concurrent: 2

- name: Stop it (close the proxy)
  susunola.tencentcloud.gaap_proxy:
    region: ap-guangzhou
    state: stopped
    name: prod-gaap

- name: Start it again
  susunola.tencentcloud.gaap_proxy:
    region: ap-guangzhou
    state: running
    name: prod-gaap

- name: Destroy it
  susunola.tencentcloud.gaap_proxy:
    region: ap-guangzhou
    state: absent
    name: prod-gaap
'''

RETURN = r'''
proxy:
  description: The proxy as reported by V(DescribeProxies) after the
    operation.
  returned: success
  type: dict
  sample:
    ProxyId: proxy-xxxxxxxx
    ProxyName: prod-gaap
    Status: running
    AccessRegion: ap-guangzhou
    RealServerRegion: ap-hongkong
    Bandwidth: 20
    Concurrent: 2
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_gaap():
    from tencentcloud.gaap.v20180529 import models, gaap_client
    return models, gaap_client


def build_describe_request(models, proxy_id, name):
    request = models.DescribeProxiesRequest()
    request.Limit = 100
    if proxy_id:
        request.ProxyIds = [proxy_id]
    # The DescribeProxies filters do not support the proxy name, so the
    # caller filters the full page set by name instead.
    return request


def _first(collection):
    return collection[0] if collection else None


def _serialize(item):
    return item._serialize(allow_none=True)


def find_proxy(module, client, models, proxy_id, name):
    """Return the matching proxy dict or None."""
    request = build_describe_request(models, proxy_id, name)
    response = module.sdk_call(client.DescribeProxies, request)
    if proxy_id:
        proxy = _first(response.ProxySet or [])
        return _serialize(proxy) if proxy is not None else None
    for proxy in response.ProxySet or []:
        current = _serialize(proxy)
        if current.get("ProxyName") == name:
            return current
    return None


def build_create_request(models, params):
    request = models.CreateProxyRequest()
    request.ProxyName = params["name"]
    request.AccessRegion = params["access_region"]
    request.RealServerRegion = params["real_server_region"]
    request.Bandwidth = params["bandwidth"]
    request.Concurrent = params["concurrent"]
    if params["project_id"] is not None:
        request.ProjectId = params["project_id"]
    if params["billing_type"] is not None:
        request.BillingType = params["billing_type"]
    if params["network_type"]:
        request.NetworkType = params["network_type"]
    if params["ip_address_version"]:
        request.IPAddressVersion = params["ip_address_version"]
    if params["group_id"]:
        request.GroupId = params["group_id"]
    return request


def _create(module, client, models, params):
    request = build_create_request(models, params)
    module.sdk_call(client.CreateProxy, request)


def _rename(module, client, models, proxy_id, name):
    request = models.ModifyProxiesAttributeRequest()
    request.ProxyIds = [proxy_id]
    request.ProxyName = name
    module.sdk_call(client.ModifyProxiesAttribute, request)


def _open(module, client, models, proxy_id):
    request = models.OpenProxiesRequest()
    request.ProxyIds = [proxy_id]
    module.sdk_call(client.OpenProxies, request)


def _close(module, client, models, proxy_id):
    request = models.CloseProxiesRequest()
    request.ProxyIds = [proxy_id]
    module.sdk_call(client.CloseProxies, request)


def _destroy(module, client, models, proxy_id):
    request = models.DestroyProxiesRequest()
    request.ProxyIds = [proxy_id]
    request.Force = 1
    module.sdk_call(client.DestroyProxies, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent", "running", "stopped"], "default": "present"},
            "proxy_id": {"type": "str"},
            "name": {"type": "str"},
            "access_region": {"type": "str"},
            "real_server_region": {"type": "str"},
            "bandwidth": {"type": "int"},
            "concurrent": {"type": "int"},
            "project_id": {"type": "int"},
            "billing_type": {"type": "int", "choices": [0, 1]},
            "network_type": {"type": "str", "choices": ["normal", "cn2", "triple"]},
            "ip_address_version": {"type": "str", "choices": ["IPv4", "IPv6"]},
            "group_id": {"type": "str"},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    proxy_id = module.params["proxy_id"]
    name = module.params["name"]

    if not proxy_id and not name:
        module.fail_json(msg="proxy_id or name is required to identify the proxy")

    models, gaap_client = _load_gaap()
    client = module.create_client(gaap_client.GaapClient, "gaap.tencentcloudapi.com")

    try:
        current = find_proxy(module, client, models, proxy_id, name)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="GAAP proxy already absent")
        target_id = current["ProxyId"]
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would destroy GAAP proxy")
        _destroy(module, client, models, target_id)
        module.exit_json(changed=True, **(diff or {}), proxy=None, msg="GAAP proxy destroyed")

    if state in ("running", "stopped"):
        if current is None:
            module.fail_json(
                msg="Proxy not found; use state=present to create it",
                proxy_id=proxy_id,
                name=name,
            )
        target_id = current["ProxyId"]
        status = current.get("Status")
        if state == "running":
            if status == "running":
                module.exit_json(changed=False, proxy=current, msg="GAAP proxy already running")
            if module.check_mode:
                module.exit_json(changed=True, proxy=current, msg="Would open GAAP proxy")
            _open(module, client, models, target_id)
            module.exit_json(changed=True, proxy=current, msg="GAAP proxy opened")
        # state == "stopped"
        if status == "closed":
            module.exit_json(changed=False, proxy=current, msg="GAAP proxy already stopped")
        if module.check_mode:
            module.exit_json(changed=True, proxy=current, msg="Would close GAAP proxy")
        _close(module, client, models, target_id)
        module.exit_json(changed=True, proxy=current, msg="GAAP proxy closed")

    # state == present
    if current is None:
        missing = [key for key in ("name", "access_region", "real_server_region", "bandwidth", "concurrent") if not module.params[key]]
        if missing:
            module.fail_json(msg="%s is required when creating a GAAP proxy" % ", ".join(missing))
        desired = {
            "ProxyName": name,
            "AccessRegion": module.params["access_region"],
            "RealServerRegion": module.params["real_server_region"],
            "Bandwidth": module.params["bandwidth"],
            "Concurrent": module.params["concurrent"],
        }
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create GAAP proxy")
        _create(module, client, models, module.params)
        current = find_proxy(module, client, models, None, name)
        module.exit_json(changed=True, **(diff or {}), proxy=current, msg="GAAP proxy created")

    target_id = current["ProxyId"]
    if name and current.get("ProxyName") != name:
        diff = maybe_diff(module, current, {"ProxyName": name})
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would rename GAAP proxy")
        _rename(module, client, models, target_id, name)
        updated = find_proxy(module, client, models, target_id, None)
        module.exit_json(changed=True, **(diff or {}), proxy=updated, msg="GAAP proxy renamed")

    module.exit_json(changed=False, proxy=current, msg="GAAP proxy is up to date")


def main():
    run_module()


if __name__ == "__main__":
    main()
