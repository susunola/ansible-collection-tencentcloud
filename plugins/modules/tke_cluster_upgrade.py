#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tke_cluster_upgrade
short_description: Upgrade the Kubernetes version of a Tencent Cloud TKE cluster
version_added: "0.14.0"
description:
  - Upgrade the Kubernetes version of an existing TKE cluster through the
    C(tke.v20180525) API C(UpdateClusterVersion).
  - This module is idempotent. When the cluster already runs the requested
    version, the module reports C(changed=false) and issues no API write.
  - Supports check mode; no API write happens in check mode, only reads.
  - The upgrade is submitted asynchronously by the platform and can take a
    long time. This module returns as soon as the upgrade request is
    accepted; it does not wait for the upgrade to finish.
options:
  cluster_id:
    description: ID of the TKE cluster to upgrade, e.g. C(cls-xxxxxxxx).
    type: str
    required: true
  version:
    description:
      - Kubernetes version to upgrade to, written to
        V(UpdateClusterVersionRequest.DstVersion), e.g. C(1.28.5).
    type: str
    required: true
  max_not_ready_percent:
    description:
      - Maximum tolerated percentage of unready pods during the upgrade,
        written to V(UpdateClusterVersionRequest.MaxNotReadyPercent).
    type: float
    default: 0
  skip_pre_check:
    description:
      - Skip the pre-check stage of the upgrade, written to
        V(UpdateClusterVersionRequest.SkipPreCheck).
    type: bool
    default: false
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
  - Requires the C(tencentcloud-sdk-python-tke) package on the controller.
  - Upgrades are only supported between adjacent minor versions; list the
    target versions with C(DescribeAvailableClusterVersion) first.
  - Node-level upgrades are not handled by this module; use the node-pool
    tooling for that.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Upgrade a cluster to Kubernetes 1.28.5
  susunola.tencentcloud.tke_cluster_upgrade:
    region: ap-guangzhou
    cluster_id: cls-xxxxxxxx
    version: "1.28.5"
    max_not_ready_percent: 10

- name: Upgrade, skipping the pre-check stage
  susunola.tencentcloud.tke_cluster_upgrade:
    region: ap-guangzhou
    cluster_id: cls-xxxxxxxx
    version: "1.30.1"
    skip_pre_check: true
'''

RETURN = r'''
cluster_id:
  description: ID of the upgraded cluster.
  returned: always
  type: str
current_version:
  description: Kubernetes version the cluster was running before this run.
  returned: always
  type: str
desired_version:
  description: Kubernetes version requested by the module.
  returned: always
  type: str
changed:
  description: Whether an upgrade was submitted.
  returned: always
  type: bool
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load_tke():
    from tencentcloud.tke.v20180525 import models, tke_client
    return models, tke_client


def find_cluster(module, client, models, cluster_id):
    """Return the serialized cluster dict or None."""
    request = models.DescribeClustersRequest()
    request.ClusterIds = [cluster_id]
    response = module.sdk_call(client.DescribeClusters, request)
    cluster = (response.Clusters or [None])[0]
    if cluster is None:
        return None
    return cluster._serialize(allow_none=True)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "cluster_id": {"type": "str", "required": True},
            "version": {"type": "str", "required": True},
            "max_not_ready_percent": {"type": "float", "default": 0},
            "skip_pre_check": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )
    module.require_sdk()
    p = module.params

    models, tke_client = _load_tke()
    client = module.create_client(tke_client.TkeClient, "tke.tencentcloudapi.com")
    try:
        cluster = find_cluster(module, client, models, p["cluster_id"])
        if cluster is None:
            module.fail_json(msg="cluster {0} not found".format(p["cluster_id"]))

        current = cluster.get("ClusterVersion")
        desired = p["version"]
        if current == desired:
            module.exit_json(
                changed=False,
                cluster_id=p["cluster_id"],
                current_version=current,
                desired_version=desired,
                msg="Cluster already running version {0}".format(desired),
            )

        diff = maybe_diff(module, {"ClusterVersion": current}, {"ClusterVersion": desired})
        if module.check_mode:
            module.exit_json(
                changed=True,
                **(diff or {}),
                cluster_id=p["cluster_id"],
                current_version=current,
                desired_version=desired,
                msg="Would upgrade cluster from {0} to {1}".format(current, desired),
            )

        request = models.UpdateClusterVersionRequest()
        request.ClusterId = p["cluster_id"]
        request.DstVersion = desired
        if p["max_not_ready_percent"]:
            request.MaxNotReadyPercent = p["max_not_ready_percent"]
        request.SkipPreCheck = p["skip_pre_check"]
        module.sdk_call(client.UpdateClusterVersion, request)
        module.exit_json(
            changed=True,
            **(diff or {}),
            cluster_id=p["cluster_id"],
            current_version=current,
            desired_version=desired,
            msg="Upgrade to {0} submitted".format(desired),
        )
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
