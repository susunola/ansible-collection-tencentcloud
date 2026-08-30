#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: emr_cluster
short_description: Manage Tencent Cloud EMR clusters
version_added: "0.14.0"
description:
  - Creates, renames, waits for and terminates EMR clusters through the current C(CreateCluster) API.
  - Complex scene and node topology objects retain the Tencent Cloud SDK field names so new EMR shapes remain usable.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  cluster_id: {type: str, description: Existing EMR cluster ID.}
  name: {type: str, description: Cluster name used for lookup and updates.}
  product_version: {type: str, description: Creation-time EMR product version.}
  enable_ha: {type: bool, description: Creation-time high-availability setting.}
  charge_type: {type: str, choices: [PREPAID, POSTPAID_BY_HOUR], description: Creation-time charge type.}
  login_settings: {type: dict, description: SDK LoginSettings payload containing a password or public key ID.}
  scene_software_config: {type: dict, description: SDK SceneSoftwareConfig payload.}
  prepaid: {type: dict, description: SDK InstanceChargePrepaid payload for prepaid clusters.}
  security_group_ids: {type: list, elements: str, description: Security group IDs.}
  bootstrap_actions: {type: list, elements: dict, description: SDK ScriptBootstrapActionConfig payloads.}
  client_token: {type: str, description: Caller-provided creation idempotency token.}
  need_master_wan: {type: str, choices: [NEED_MASTER_WAN, NOT_NEED_MASTER_WAN], description: Master public-network setting.}
  enable_remote_login: {type: bool, description: Whether remote login is enabled.}
  enable_kerberos: {type: bool, description: Whether Kerberos authentication is enabled.}
  custom_conf: {type: str, description: Custom software configuration JSON.}
  tags: {type: dict, description: Creation-time tags.}
  disaster_recover_group_ids: {type: list, elements: str, description: Placement group IDs.}
  enable_cbs_encrypt: {type: bool, description: Whether data disks use CBS encryption.}
  enable_cbs_system_encrypt: {type: bool, description: Whether system disks use CBS encryption.}
  meta_db_info: {type: dict, description: SDK CustomMetaDBInfo payload.}
  depend_services: {type: list, elements: dict, description: SDK DependService payloads.}
  zone_resource_configurations: {type: list, elements: dict, description: SDK ZoneResourceConfiguration payloads describing the complete node topology.}
  cos_bucket: {type: str, description: COS path for supported separated-storage scenes.}
  node_marks: {type: list, elements: dict, description: SDK NodeMark payloads.}
  load_balancer_id: {type: str, description: Creation-time load balancer ID.}
  default_meta_version: {type: str, description: Default metadata database version.}
  need_cdb_audit: {type: int, description: Whether database audit is enabled.}
  source_ip: {type: str, description: Security source IP.}
  partition_number: {type: int, description: Placement-group partition number.}
  web_ui_version: {type: int, choices: [0, 1], description: Web UI response mode.}
  retain_tke_cluster: {type: bool, default: false, description: Retain the associated TKE cluster during termination.}
  wait: {type: bool, default: true, description: Wait for running or absent convergence.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 10, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 1800, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- name: Create an EMR cluster
  susunola.tencentcloud.emr_cluster:
    name: analytics-emr
    product_version: EMR-V3.5.0
    enable_ha: true
    charge_type: POSTPAID_BY_HOUR
    login_settings: {Password: "{{ vault_emr_password }}"}
    scene_software_config: {SceneName: Hadoop, Software: [HDFS, YARN]}
    security_group_ids: [sg-xxxxxxxx]
    zone_resource_configurations:
      - VirtualPrivateCloud: {VpcId: vpc-xxxxxxxx, SubnetId: subnet-xxxxxxxx}
        Placement: {Zone: ap-guangzhou-3}
        AllNodeResourceSpec: {}
'''
RETURN = r'''cluster: {description: Effective EMR cluster metadata., type: dict, returned: always}'''
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state,wait_for_task

def _load():
    from tencentcloud.emr.v20190103 import models,emr_client
    return models,emr_client
def _model(cls,value):
    if value is None: return None
    item=cls(); item.from_json_string(json.dumps(value)); return item
def _models(models,name,values): return [_model(getattr(models,name),x) for x in values] if values is not None else None
def _tags(models,values):
    result=[]
    for key,value in sorted((values or {}).items()): item=models.Tag(); item.TagKey,item.TagValue=str(key),str(value); result.append(item)
    return result
def describe_request(models,cluster_id=None,offset=0):
    r=models.DescribeInstancesRequest(); r.DisplayStrategy="clusterList"; r.InstanceIds=[cluster_id] if cluster_id else None; r.Offset,r.Limit,r.ProjectId=offset,100,-1; return r
def create_request(models,p):
    r=models.CreateClusterRequest(); r.ProductVersion,r.EnableSupportHAFlag,r.InstanceName,r.InstanceChargeType=p["product_version"],p.get("enable_ha"),p["name"],p["charge_type"]
    r.LoginSettings=_model(models.LoginSettings,p.get("login_settings")); r.SceneSoftwareConfig=_model(models.SceneSoftwareConfig,p.get("scene_software_config")); r.InstanceChargePrepaid=_model(models.InstanceChargePrepaid,p.get("prepaid")); r.SecurityGroupIds=p.get("security_group_ids"); r.ScriptBootstrapActionConfig=_models(models,"ScriptBootstrapActionConfig",p.get("bootstrap_actions")); r.ClientToken=p.get("client_token")
    r.NeedMasterWan,r.EnableRemoteLoginFlag,r.EnableKerberosFlag,r.CustomConf=p.get("need_master_wan"),p.get("enable_remote_login"),p.get("enable_kerberos"),p.get("custom_conf"); r.Tags=_tags(models,p.get("tags")); r.DisasterRecoverGroupIds=p.get("disaster_recover_group_ids"); r.EnableCbsEncryptFlag=p.get("enable_cbs_encrypt"); r.EnableCbsSysEncryptFlag=p.get("enable_cbs_system_encrypt")
    r.MetaDBInfo=_model(models.CustomMetaDBInfo,p.get("meta_db_info")); r.DependService=_models(models,"DependService",p.get("depend_services")); r.ZoneResourceConfiguration=_models(models,"ZoneResourceConfiguration",p.get("zone_resource_configurations")); r.CosBucket=p.get("cos_bucket"); r.NodeMarks=_models(models,"NodeMark",p.get("node_marks")); r.LoadBalancerId=p.get("load_balancer_id"); r.DefaultMetaVersion=p.get("default_meta_version"); r.NeedCdbAudit=p.get("need_cdb_audit"); r.SgIP=p.get("source_ip"); r.PartitionNumber=p.get("partition_number"); r.WebUiVersion=p.get("web_ui_version"); return r
def update_request(models,cluster_id,name): r=models.ModifyInstanceBasicRequest(); r.InstanceId,r.ClusterName=cluster_id,name; return r
def delete_request(models,cluster_id,retain_tke_cluster=False): r=models.TerminateInstanceRequest(); r.InstanceId,r.RetainTkeCluster=cluster_id,retain_tke_cluster; return r
def find(module,client,models,p):
    offset=0; matches=[]
    while True:
        response=module.sdk_call(client.DescribeInstances,describe_request(models,p.get("cluster_id"),offset)); page=response.ClusterList or []
        for item in page:
            value=item._serialize(allow_none=True)
            if (p.get("cluster_id") and value.get("ClusterId")==p["cluster_id"]) or (not p.get("cluster_id") and value.get("ClusterName")==p.get("name")): matches.append(value)
        offset+=len(page)
        if not page or offset>=int(response.TotalCnt or 0): break
    if len(matches)>1: module.fail_json(msg="Multiple EMR clusters matched; specify cluster_id")
    return matches[0] if matches else None
def _wait(module,client,models,p,absent=False,desired_name=None):
    if absent:
        wait_for_state(module,lambda: "absent" if find(module,client,models,p) is None else "present",{"absent"},timeout=p["waiter_timeout"],delay=p["waiter_delay"])
        return None
    def poll():
        current=find(module,client,models,p); status=(current or {}).get("Status")
        if status in (301,302): return "FAILED",(current or {}).get("AlarmInfo"),current
        if status==2 and (desired_name is None or current.get("ClusterName")==desired_name): return "SUCCESS",None,current
        return "RUNNING",None,current
    return wait_for_task(module,poll,timeout=p["waiter_timeout"],delay=p["waiter_delay"],success_statuses=("SUCCESS",),failure_statuses=("FAILED",))
def run_module():
    spec={"state":{"choices":["present","absent"],"default":"present"},"cluster_id":{},"name":{},"product_version":{},"enable_ha":{"type":"bool"},"charge_type":{"choices":["PREPAID","POSTPAID_BY_HOUR"]},"login_settings":{"type":"dict","no_log":True},"scene_software_config":{"type":"dict"},"prepaid":{"type":"dict"},"security_group_ids":{"type":"list","elements":"str"},"bootstrap_actions":{"type":"list","elements":"dict"},"client_token":{"no_log":False},"need_master_wan":{"choices":["NEED_MASTER_WAN","NOT_NEED_MASTER_WAN"]},"enable_remote_login":{"type":"bool"},"enable_kerberos":{"type":"bool"},"custom_conf":{},"tags":{"type":"dict"},"disaster_recover_group_ids":{"type":"list","elements":"str"},"enable_cbs_encrypt":{"type":"bool"},"enable_cbs_system_encrypt":{"type":"bool"},"meta_db_info":{"type":"dict","no_log":True},"depend_services":{"type":"list","elements":"dict"},"zone_resource_configurations":{"type":"list","elements":"dict"},"cos_bucket":{},"node_marks":{"type":"list","elements":"dict"},"load_balancer_id":{},"default_meta_version":{},"need_cdb_audit":{"type":"int"},"source_ip":{},"partition_number":{"type":"int"},"web_ui_version":{"type":"int","choices":[0,1]},"retain_tke_cluster":{"type":"bool","default":False},"wait":{"type":"bool","default":True},"waiter_delay":{"type":"int","default":10},"waiter_timeout":{"type":"int","default":1800}}
    module=TencentCloudModule(argument_spec=spec,required_one_of=[("cluster_id","name")],supports_check_mode=True); p=module.params; module.require_sdk(); models,cm=_load(); client=module.create_client(cm.EmrClient,"emr.tencentcloudapi.com")
    try:
        current=find(module,client,models,p)
        if p["state"]=="absent":
            if not current: module.exit_json(changed=False,cluster=None)
            diff=maybe_diff(module,current,None)
            if not module.check_mode:
                p["cluster_id"]=current["ClusterId"]; module.sdk_call(client.TerminateInstance,delete_request(models,p["cluster_id"],p["retain_tke_cluster"])); current=_wait(module,client,models,p,True) if p["wait"] else None
            module.exit_json(changed=True,**(diff or {}),cluster=current)
        if not current:
            missing=[k for k in ("name","product_version","charge_type","login_settings","scene_software_config","zone_resource_configurations") if not p.get(k)]
            if missing: module.fail_json(msg="creation parameters are required for an EMR cluster",missing=missing)
            target={"ClusterName":p["name"],"ProductVersion":p["product_version"],"ChargeType":p["charge_type"]}; diff=maybe_diff(module,None,target)
            if not module.check_mode:
                p["cluster_id"]=module.sdk_call(client.CreateCluster,create_request(models,p)).InstanceId; current=_wait(module,client,models,p,desired_name=p["name"]) if p["wait"] else find(module,client,models,p)
            module.exit_json(changed=True,**(diff or {}),cluster=current if not module.check_mode else target)
        desired_name=p.get("name") or current.get("ClusterName")
        if desired_name==current.get("ClusterName"): module.exit_json(changed=False,cluster=current)
        before={"ClusterName":current.get("ClusterName")}; target={"ClusterName":desired_name}; diff=maybe_diff(module,before,target)
        if not module.check_mode:
            p["cluster_id"]=current["ClusterId"]; module.sdk_call(client.ModifyInstanceBasic,update_request(models,p["cluster_id"],desired_name)); current=_wait(module,client,models,p,desired_name=desired_name) if p["wait"] else find(module,client,models,p)
        module.exit_json(changed=True,**(diff or {}),cluster=current if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
