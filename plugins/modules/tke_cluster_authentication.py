#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tke_cluster_authentication
short_description: Manage Tencent Cloud TKE cluster authentication options
version_added: "0.14.0"
description: Reconciles service-account and OIDC authentication options for a TKE cluster.
options:
  cluster_id: {type: str, required: true, description: TKE cluster ID.}
  service_accounts: {type: dict, required: true, description: SDK-compatible ServiceAccount authentication options.}
  oidc: {type: dict, required: true, description: SDK-compatible OIDC authentication options.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tke_cluster_authentication:
    cluster_id: cls-xxxxxxxx
    service_accounts: {UseTKEDefault: true, AutoCreateDiscoveryAnonymousAuth: true}
    oidc: {AutoCreateOIDCConfig: true, AutoCreateClientId: [kubernetes], AutoInstallPodIdentityWebhookAddon: true}
"""
RETURN = r"""authentication: {description: Effective authentication options., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tke.v20180525 import models, tke_client

    return models, tke_client


def build_describe(models, cluster_id):
    request = models.DescribeClusterAuthenticationOptionsRequest()
    request.ClusterId = cluster_id
    return request


def _model(models, name, value):
    item = getattr(models, name)()
    item._deserialize(value)
    return item


def build_modify(models, p):
    request = models.ModifyClusterAuthenticationOptionsRequest()
    request.ClusterId = p["cluster_id"]
    request.ServiceAccounts = _model(models, "ServiceAccountAuthenticationOptions", p["service_accounts"])
    request.OIDCConfig = _model(models, "OIDCConfigAuthenticationOptions", p["oidc"])
    return request


def desired(p):
    return {"ServiceAccounts": p["service_accounts"], "OIDCConfig": p["oidc"]}


def find(module, client, models, cluster_id):
    response = module.sdk_call(client.DescribeClusterAuthenticationOptions, build_describe(models, cluster_id))
    return {
        "ServiceAccounts": response.ServiceAccounts._serialize(allow_none=True) if response.ServiceAccounts else {},
        "OIDCConfig": response.OIDCConfig._serialize(allow_none=True) if response.OIDCConfig else {},
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={"cluster_id": {"required": True}, "service_accounts": {"type": "dict", "required": True}, "oidc": {"type": "dict", "required": True}},
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TkeClient, "tke.tencentcloudapi.com")
    try:
        current, target = find(module, client, models, p["cluster_id"]), desired(p)
        if current == target:
            module.exit_json(changed=False, authentication=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            module.sdk_call(client.ModifyClusterAuthenticationOptions, build_modify(models, p))
            current = find(module, client, models, p["cluster_id"])
        module.exit_json(changed=True, **(diff or {}), authentication=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
