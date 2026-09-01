#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tke_cluster_autoscaler
short_description: Manage the cluster autoscaler options of a Tencent Cloud TKE cluster
version_added: "0.14.0"
description:
  - Reconcile the cluster-level autoscaler (CA) options of a TKE cluster
    through the C(tke.v20180525) API C(DescribeClusterAsGroupOption) and
    C(ModifyClusterAsGroupOptionAttribute).
  - Only the options explicitly passed to the module are compared and
    written; options left unset are left untouched on the platform.
  - This module is idempotent. Running it twice with the same options
    reports C(changed=false) on the second run.
  - Supports check mode; no API write happens in check mode, only reads.
options:
  cluster_id:
    description: ID of the TKE cluster, e.g. C(cls-xxxxxxxx).
    type: str
    required: true
  is_scale_down_enabled:
    description:
      - Whether scale-down is enabled, written to
        V(ClusterAsGroupOption.IsScaleDownEnabled).
    type: bool
  expander:
    description:
      - Expansion algorithm when multiple scaling groups compete, written to
        V(ClusterAsGroupOption.Expander).
    type: str
    choices: [random, most-pods, least-waste]
  max_empty_bulk_delete:
    description:
      - Maximum number of concurrent scale-down nodes, written to
        V(ClusterAsGroupOption.MaxEmptyBulkDelete).
    type: int
  scale_down_delay:
    description:
      - Minutes after a scale-up before scale-down is considered, written to
        V(ClusterAsGroupOption.ScaleDownDelay).
    type: int
  scale_down_unneeded_time:
    description:
      - Minutes a node must be continuously idle before it is scaled down,
        written to V(ClusterAsGroupOption.ScaleDownUnneededTime).
    type: int
  scale_down_utilization_threshold:
    description:
      - Node utilization percentage below which a node is considered idle,
        written to V(ClusterAsGroupOption.ScaleDownUtilizationThreshold).
    type: int
  skip_nodes_with_local_storage:
    description:
      - Whether nodes with local-storage pods are never scaled down, written
        to V(ClusterAsGroupOption.SkipNodesWithLocalStorage).
    type: bool
  skip_nodes_with_system_pods:
    description:
      - Whether nodes hosting non-DaemonSet pods in kube-system are never
        scaled down, written to
        V(ClusterAsGroupOption.SkipNodesWithSystemPods).
    type: bool
  ignore_daemon_sets_utilization:
    description:
      - Whether DaemonSet pods are ignored when computing utilization,
        written to V(ClusterAsGroupOption.IgnoreDaemonSetsUtilization).
    type: bool
  ok_total_unready_count:
    description:
      - Number of unready nodes tolerated before CA performs a health check,
        written to V(ClusterAsGroupOption.OkTotalUnreadyCount).
    type: int
  max_total_unready_percentage:
    description:
      - Maximum percentage of unready nodes after which CA stops working,
        written to V(ClusterAsGroupOption.MaxTotalUnreadyPercentage).
    type: int
  scale_down_unready_time:
    description:
      - Minutes an unready node must wait before being eligible for
        scale-down, written to V(ClusterAsGroupOption.ScaleDownUnreadyTime).
    type: int
  unregistered_node_removal_time:
    description:
      - Minutes CA waits before removing a node that is not registered in
        Kubernetes, written to
        V(ClusterAsGroupOption.UnregisteredNodeRemovalTime).
    type: int
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
  - The autoscaler only acts on node pools created with
    C(EnableAutoscale=true); create those through C(tke_node_pool).
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Enable scale-down and tune the idle thresholds
  susunola.tencentcloud.tke_cluster_autoscaler:
    region: ap-guangzhou
    cluster_id: cls-xxxxxxxx
    is_scale_down_enabled: true
    scale_down_unneeded_time: 15
    scale_down_utilization_threshold: 40

- name: Switch the expander algorithm to least-waste
  susunola.tencentcloud.tke_cluster_autoscaler:
    region: ap-guangzhou
    cluster_id: cls-xxxxxxxx
    expander: least-waste
'''

RETURN = r'''
cluster_id:
  description: ID of the cluster whose autoscaler options were managed.
  returned: always
  type: str
changed:
  description: Whether any autoscaler option was modified.
  returned: always
  type: bool
'''

# module parameter -> ClusterAsGroupOption field
OPTION_FIELDS = (
    ("is_scale_down_enabled", "IsScaleDownEnabled"),
    ("expander", "Expander"),
    ("max_empty_bulk_delete", "MaxEmptyBulkDelete"),
    ("scale_down_delay", "ScaleDownDelay"),
    ("scale_down_unneeded_time", "ScaleDownUnneededTime"),
    ("scale_down_utilization_threshold", "ScaleDownUtilizationThreshold"),
    ("skip_nodes_with_local_storage", "SkipNodesWithLocalStorage"),
    ("skip_nodes_with_system_pods", "SkipNodesWithSystemPods"),
    ("ignore_daemon_sets_utilization", "IgnoreDaemonSetsUtilization"),
    ("ok_total_unready_count", "OkTotalUnreadyCount"),
    ("max_total_unready_percentage", "MaxTotalUnreadyPercentage"),
    ("scale_down_unready_time", "ScaleDownUnreadyTime"),
    ("unregistered_node_removal_time", "UnregisteredNodeRemovalTime"),
)

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load_tke():
    from tencentcloud.tke.v20180525 import models, tke_client
    return models, tke_client


def current_options(module, client, models, cluster_id):
    """Return the serialized ClusterAsGroupOption dict or an empty dict."""
    request = models.DescribeClusterAsGroupOptionRequest()
    request.ClusterId = cluster_id
    response = module.sdk_call(client.DescribeClusterAsGroupOption, request)
    option = response.ClusterAsGroupOption
    if option is None:
        return {}
    return option._serialize(allow_none=True)


def run_module():
    argument_spec = {"cluster_id": {"type": "str", "required": True}}
    for param, _field in OPTION_FIELDS:
        spec = {"type": "str"} if param == "expander" else {"type": "int"}
        if param == "expander":
            spec["choices"] = ["random", "most-pods", "least-waste"]
        elif param in ("is_scale_down_enabled", "skip_nodes_with_local_storage",
                       "skip_nodes_with_system_pods", "ignore_daemon_sets_utilization"):
            spec = {"type": "bool"}
        argument_spec[param] = spec

    module = TencentCloudModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )
    module.require_sdk()
    p = module.params

    models, tke_client = _load_tke()
    client = module.create_client(tke_client.TkeClient, "tke.tencentcloudapi.com")
    try:
        current = current_options(module, client, models, p["cluster_id"])

        provided = {}
        for param, field in OPTION_FIELDS:
            if p[param] is not None:
                provided[field] = p[param]

        changed_fields = {}
        for field, value in provided.items():
            if current.get(field) != value:
                changed_fields[field] = (current.get(field), value)

        if not changed_fields:
            module.exit_json(changed=False, cluster_id=p["cluster_id"],
                             msg="Cluster autoscaler options are up to date")

        before = {f: v[0] for f, v in changed_fields.items()}
        after = {f: v[1] for f, v in changed_fields.items()}
        diff = maybe_diff(module, before, after)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), cluster_id=p["cluster_id"],
                             msg="Would update autoscaler options: {0}".format(", ".join(sorted(changed_fields))))

        option = models.ClusterAsGroupOption()
        for field, value in provided.items():
            setattr(option, field, value)
        request = models.ModifyClusterAsGroupOptionAttributeRequest()
        request.ClusterId = p["cluster_id"]
        request.ClusterAsGroupOption = option
        module.sdk_call(client.ModifyClusterAsGroupOptionAttribute, request)
        module.exit_json(changed=True, **(diff or {}), cluster_id=p["cluster_id"],
                         msg="Updated autoscaler options: {0}".format(", ".join(sorted(changed_fields))))
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
