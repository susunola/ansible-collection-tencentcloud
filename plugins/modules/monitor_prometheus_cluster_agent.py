#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__=type
DOCUMENTATION = r'''
---
module: monitor_prometheus_cluster_agent
short_description: Manage Managed Prometheus cluster agents
version_added: "0.14.0"
description: Binds or unbinds a Kubernetes cluster as a Prometheus collection agent.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: Prometheus instance ID.}
  cluster_id: {type: str, required: true, description: Kubernetes cluster ID.}
  cluster_type: {type: str, default: tke, description: Kubernetes cluster type.}
  region: {type: str, description: Cluster region.}
  agent: {type: dict, default: {}, description: Additional SDK-compatible PrometheusClusterAgentBasic fields.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.monitor_prometheus_cluster_agent:
    instance_id: prom-xxxxxxxx
    cluster_id: cls-xxxxxxxx
    cluster_type: tke
    region: ap-guangzhou
'''
RETURN = r'''agent: {description: Cluster-agent metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
def _load():
    from tencentcloud.monitor.v20180724 import models,monitor_client
    return models,monitor_client
def build_describe(models,p): request=models.DescribePrometheusClusterAgentsRequest(); request.InstanceId,request.ClusterIds,request.ClusterTypes,request.Offset,request.Limit=p["instance_id"],[p["cluster_id"]],[p["cluster_type"]],0,100; return request
def _agent(models,p): value=dict(p["agent"]); value.update({"ClusterId":p["cluster_id"],"ClusterType":p["cluster_type"],"Region":p.get("region")}); item=models.PrometheusClusterAgentBasic(); item._deserialize(value); return item
def build_create(models,p): request=models.CreatePrometheusClusterAgentRequest(); request.InstanceId,request.Agents=p["instance_id"],[_agent(models,p)]; return request
def build_delete(models,p): request=models.DeletePrometheusClusterAgentRequest(); item=models.PrometheusAgentInfo(); item.ClusterId,item.ClusterType=p["cluster_id"],p["cluster_type"]; request.InstanceId,request.Agents=p["instance_id"],[item]; return request
def find(module,client,models,p):
    response=module.sdk_call(client.DescribePrometheusClusterAgents,build_describe(models,p))
    for x in list(response.Agents or []):
        value=x._serialize(allow_none=True)
        if value.get("ClusterId")==p["cluster_id"] and value.get("ClusterType")==p["cluster_type"]: return value
    return None
def run_module():
    module=TencentCloudModule(argument_spec={"state":{"choices":["present","absent"],"default":"present"},"instance_id":{"required":True},"cluster_id":{"required":True},"cluster_type":{"default":"tke"},"region":{},"agent":{"type":"dict","default":{}}},supports_check_mode=True); p=module.params; module.require_sdk(); models,cm=_load(); client=module.create_client(cm.MonitorClient,"monitor.tencentcloudapi.com")
    try:
        current=find(module,client,models,p); present=p["state"]=="present"; target={"ClusterId":p["cluster_id"],"ClusterType":p["cluster_type"]}
        if (present and current) or (not present and not current): module.exit_json(changed=False,agent=current)
        diff=maybe_diff(module,current,target if present else None)
        if not module.check_mode: module.sdk_call(client.CreatePrometheusClusterAgent if present else client.DeletePrometheusClusterAgent,build_create(models,p) if present else build_delete(models,p))
        module.exit_json(changed=True,**(diff or {}),agent=target if present else None)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
