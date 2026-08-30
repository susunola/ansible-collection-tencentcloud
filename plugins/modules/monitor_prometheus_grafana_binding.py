#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import,division,print_function
__metaclass__=type
DOCUMENTATION = r'''
---
module: monitor_prometheus_grafana_binding
short_description: Bind Managed Prometheus and Grafana instances
version_added: "0.14.0"
description: Binds or unbinds a Managed Grafana instance from a Prometheus instance.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: Prometheus instance ID.}
  grafana_id: {type: str, required: true, description: Grafana instance ID.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.monitor_prometheus_grafana_binding:
    instance_id: prom-xxxxxxxx
    grafana_id: grafana-xxxxxxxx
'''
RETURN = r'''binding: {description: Normalized instance binding., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
def _load():
    from tencentcloud.monitor.v20180724 import models,monitor_client
    return models,monitor_client
def build_describe(models,iid): request=models.DescribePrometheusInstancesRequest(); request.InstanceIds=[iid]; request.Offset,request.Limit=0,1; return request
def build_bind(models,iid,gid): request=models.BindPrometheusManagedGrafanaRequest(); request.InstanceId,request.GrafanaId=iid,gid; return request
def build_unbind(models,iid,gid): request=models.UnbindPrometheusManagedGrafanaRequest(); request.InstanceId,request.GrafanaId=iid,gid; return request
def find(module,client,models,p):
    response=module.sdk_call(client.DescribePrometheusInstances,build_describe(models,p["instance_id"])); items=list(response.InstanceSet or [])
    return {"InstanceId":p["instance_id"],"GrafanaId":p["grafana_id"]} if items and items[0].GrafanaInstanceId==p["grafana_id"] else None
def run_module():
    module=TencentCloudModule(argument_spec={"state":{"choices":["present","absent"],"default":"present"},"instance_id":{"required":True},"grafana_id":{"required":True}},supports_check_mode=True); p=module.params; module.require_sdk(); models,cm=_load(); client=module.create_client(cm.MonitorClient,"monitor.tencentcloudapi.com")
    try:
        current=find(module,client,models,p); target={"InstanceId":p["instance_id"],"GrafanaId":p["grafana_id"]}; present=p["state"]=="present"
        if (present and current) or (not present and not current): module.exit_json(changed=False,binding=current)
        diff=maybe_diff(module,current,target if present else None)
        if not module.check_mode: module.sdk_call(client.BindPrometheusManagedGrafana if present else client.UnbindPrometheusManagedGrafana,build_bind(models,p["instance_id"],p["grafana_id"]) if present else build_unbind(models,p["instance_id"],p["grafana_id"]))
        module.exit_json(changed=True,**(diff or {}),binding=target if present else None)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
