#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tke_cluster_deletion_protection
short_description: Enable or disable deletion protection for a Tencent Cloud TKE cluster
version_added: "1.1.0"
description:
  - Enables or disables deletion protection on a Tencent Cloud TKE cluster.
  - Deletion protection prevents accidental cluster deletion through the console, CLI or API.
  - The module is idempotent; it reads the current protection state before changing it.
options:
  state:
    description: Desired protection state.
    type: str
    choices: [present, absent]
    default: present
  cluster_id:
    description: ID of the TKE cluster to protect or unprotect.
    type: str
    required: true
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Enable deletion protection on a cluster
  susunola.tencentcloud.tke_cluster_deletion_protection:
    cluster_id: cls-xxxxxxxx
    state: present

- name: Disable deletion protection on a cluster
  susunola.tencentcloud.tke_cluster_deletion_protection:
    cluster_id: cls-xxxxxxxx
    state: absent
'''

RETURN = r'''
cluster_id:
  description: Cluster ID the operation targeted.
  returned: always
  type: str
deletion_protection:
  description: Whether deletion protection is enabled after the operation.
  returned: always
  type: bool
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def _load_tke():
    from tencentcloud.tke.v20180525 import tke_client, models
    return models, tke_client


def describe_state(module, client, models, cluster_id):
    request = models.DescribeClustersRequest()
    request.ClusterIds = [cluster_id]
    response = module.sdk_call(client.DescribeClusters, request)
    clusters = list(getattr(response, "Clusters", None) or [])
    if not clusters:
        module.fail_json(msg="TKE cluster %s not found" % cluster_id, cluster_id=cluster_id)
    return bool(getattr(clusters[0], "DeletionProtection", False))


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "cluster_id": {"type": "str", "required": True},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, client_module = _load_tke()
    client = module.create_client(client_module.TkeClient, "tke.tencentcloudapi.com")
    desired = p["state"] == "present"
    try:
        current = describe_state(module, client, models, p["cluster_id"])
        if current == desired:
            module.exit_json(
                changed=False,
                cluster_id=p["cluster_id"],
                deletion_protection=current,
                msg="Deletion protection already %s" % ("enabled" if desired else "disabled"),
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                cluster_id=p["cluster_id"],
                deletion_protection=desired,
                msg="Would %s deletion protection" % ("enable" if desired else "disable"),
            )
        if desired:
            request = models.EnableClusterDeletionProtectionRequest()
        else:
            request = models.DisableClusterDeletionProtectionRequest()
        request.ClusterId = p["cluster_id"]
        if desired:
            module.sdk_call(client.EnableClusterDeletionProtection, request)
        else:
            module.sdk_call(client.DisableClusterDeletionProtection, request)
        final = describe_state(module, client, models, p["cluster_id"])
        module.exit_json(
            changed=True,
            cluster_id=p["cluster_id"],
            deletion_protection=final,
            msg="Deletion protection %s" % ("enabled" if desired else "disabled"),
        )
    except Exception as exc:
        module.fail_sdk_error(exc, "Tencent Cloud TKE deletion protection request failed")


def main():
    run_module()


if __name__ == "__main__":
    main()
