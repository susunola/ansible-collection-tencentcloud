#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: cdwch_backup_config
short_description: Manage Tencent Cloud CDW ClickHouse backup configuration
version_added: "0.14.0"
description: Reconciles the backup service switch plus metadata and table-data schedules.
options:
  instance_id: {type: str, required: true, description: CDW ClickHouse instance ID.}
  enabled: {type: bool, required: true, description: Whether backup is enabled.}
  cos_bucket_name: {type: str, description: COS bucket used when enabling backup.}
  meta_strategy: {type: dict, description: Metadata schedule with retain_days, week_days and execute_hour.}
  data_strategy: {type: dict, description: Table-data schedule with retain_days, week_days and execute_hour.}
  backup_tables: {type: list, elements: dict, description: Exact SDK BackupTableContent list for the data schedule.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cdwch_backup_config:
    instance_id: cdwch-xxxxxxxx
    enabled: true
    cos_bucket_name: analytics-backup-1250000000
    meta_strategy: {retain_days: 30, week_days: '1,3,5', execute_hour: 2}
    data_strategy: {retain_days: 14, week_days: '0,6', execute_hour: 3}
    backup_tables: [{Database: analytics, Table: events}]
'''
RETURN = r'''backup_config: {description: Effective backup configuration., type: dict, returned: always}'''
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload

STRATEGY_FIELDS={"retain_days":"RetainDays","week_days":"WeekDays","execute_hour":"ExecuteHour"}
def _load():
    from tencentcloud.cdwch.v20200915 import models,cdwch_client
    return models,cdwch_client
def normalize_strategy(value): return {sdk:value[key] for key,sdk in STRATEGY_FIELDS.items() if value is not None and value.get(key) is not None}
def normalize_tables(values):
    result=[{"Database":x.get("Database",x.get("database")),"Table":x.get("Table",x.get("table"))} for x in values or []]
    return sorted(result,key=lambda x:(x.get("Database") or "",x.get("Table") or ""))
def describe(module,client,models,instance_id):
    request=models.DescribeBackUpScheduleRequest(); request.InstanceId=instance_id; response=module.sdk_call(client.DescribeBackUpSchedule,request)
    if response.ErrorMsg: module.fail_json(msg=response.ErrorMsg)
    return {"enabled":bool(response.BackUpOpened),"meta_strategy":response.MetaStrategy._serialize(allow_none=True) if response.MetaStrategy else None,"data_strategy":response.DataStrategy._serialize(allow_none=True) if response.DataStrategy else None,"backup_tables":normalize_tables([x._serialize(allow_none=True) for x in response.BackUpContents or []])}
def switch_request(models,p): r=models.OpenBackUpRequest(); r.InstanceId=p["instance_id"]; r.OperationType="OPEN" if p["enabled"] else "CLOSE"; r.CosBucketName=p.get("cos_bucket_name"); return r
def schedule_request(models,p,kind,target,current):
    r=models.CreateBackUpScheduleRequest(); r.InstanceId=p["instance_id"]; r.ScheduleType=kind; r.OperationType="update" if current else "create"
    r.ScheduleId=(current or {}).get("ScheduleId"); r.RetainDays=target.get("RetainDays"); r.WeekDays=target.get("WeekDays"); r.ExecuteHour=target.get("ExecuteHour")
    if kind=="data": r.BackUpTables=[_model(models.BackupTableContent,x) for x in p.get("backup_tables") or []]
    return r
def _model(cls,value): x=cls(); x.from_json_string(json.dumps(value)); return x
def comparable(current,target): return {key:current.get(key) for key in target} if current else None
def run_module():
    module=TencentCloudModule(argument_spec={"instance_id":{"required":True},"enabled":{"type":"bool","required":True},"cos_bucket_name":{},"meta_strategy":{"type":"dict"},"data_strategy":{"type":"dict"},"backup_tables":{"type":"list","elements":"dict"}},supports_check_mode=True)
    p=module.params; module.require_sdk(); models,cm=_load(); client=module.create_client(cm.CdwchClient,"cdwch.tencentcloudapi.com")
    try:
        current=describe(module,client,models,p["instance_id"]); target={"enabled":p["enabled"]}
        if p["enabled"] and p.get("meta_strategy") is not None: target["meta_strategy"]=normalize_strategy(p["meta_strategy"])
        if p["enabled"] and p.get("data_strategy") is not None: target["data_strategy"]=normalize_strategy(p["data_strategy"]); target["backup_tables"]=normalize_tables(p.get("backup_tables"))
        before={"enabled":current["enabled"]}
        for key in ("meta_strategy","data_strategy"):
            if key in target: before[key]=comparable(current.get(key),target[key])
        if "backup_tables" in target: before["backup_tables"]=current["backup_tables"]
        if before==target: module.exit_json(changed=False,backup_config=current)
        if p["enabled"] and not current["enabled"] and not p.get("cos_bucket_name"): module.fail_json(msg="cos_bucket_name is required when enabling ClickHouse backup")
        diff=maybe_diff(module,before,target)
        if not module.check_mode:
            if current["enabled"]!=p["enabled"]: module.sdk_call(client.OpenBackUp,switch_request(models,p))
            if p["enabled"]:
                for key,kind in (("meta_strategy","meta"),("data_strategy","data")):
                    if key in target and comparable(current.get(key),target[key])!=target[key]:
                        response=module.sdk_call(client.CreateBackUpSchedule,schedule_request(models,p,kind,target[key],current.get(key)))
                        if response.ErrorMsg: module.fail_json(msg=response.ErrorMsg)
            current=describe(module,client,models,p["instance_id"])
        module.exit_json(changed=True,**(diff or {}),backup_config=current if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
