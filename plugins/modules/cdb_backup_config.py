#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import,division,print_function
__metaclass__=type
DOCUMENTATION = r'''
---
module: cdb_backup_config
short_description: Manage TencentDB for MySQL backup configuration
version_added: "0.14.0"
description: Reconciles automatic backup retention, method and time window for a MySQL instance.
options:
  instance_id: {type: str, required: true, description: TencentDB for MySQL instance ID.}
  expire_days: {type: int, required: true, description: Data backup retention days.}
  start_time: {type: str, required: true, description: Backup start time.}
  backup_method: {type: str, choices: [physical, logical], default: physical, description: Backup method.}
  binlog_expire_days: {type: int, description: Binlog retention days.}
  backup_time_window: {type: str, description: Backup time window.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.cdb_backup_config:
    instance_id: cdb-xxxxxxxx
    expire_days: 30
    start_time: 03:00
    backup_method: physical
'''
RETURN = r'''backup_config: {description: Effective backup configuration., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
def _load():
    from tencentcloud.cdb.v20170320 import cdb_client,models
    return models,cdb_client
def build_describe(models,iid): request=models.DescribeBackupConfigRequest(); request.InstanceId=iid; return request
def build_update(models,p):
    request=models.ModifyBackupConfigRequest(); request.InstanceId,request.ExpireDays,request.StartTime,request.BackupMethod=p["instance_id"],p["expire_days"],p["start_time"],p["backup_method"]
    request.BinlogExpireDays,request.BackupTimeWindow=p.get("binlog_expire_days"),p.get("backup_time_window"); return request
def target(p): return {"BackupExpireDays":p["expire_days"],"StartTimeMin":p["start_time"],"BackupMethod":p["backup_method"],"BinlogExpireDays":p.get("binlog_expire_days"),"BackupTimeWindow":p.get("backup_time_window")}
def run_module():
    module=TencentCloudModule(argument_spec={"instance_id":{"required":True},"expire_days":{"type":"int","required":True},"start_time":{"required":True},"backup_method":{"choices":["physical","logical"],"default":"physical"},"binlog_expire_days":{"type":"int"},"backup_time_window":{}},supports_check_mode=True); p=module.params; module.require_sdk(); models,cm=_load(); client=module.create_client(cm.CdbClient,"cdb.tencentcloudapi.com")
    try:
        response=module.sdk_call(client.DescribeBackupConfig,build_describe(models,p["instance_id"])); wanted=target(p); current={k:getattr(response,k) for k in wanted}
        if current==wanted: module.exit_json(changed=False,backup_config=current)
        diff=maybe_diff(module,current,wanted)
        if not module.check_mode: module.sdk_call(client.ModifyBackupConfig,build_update(models,p))
        module.exit_json(changed=True,**(diff or {}),backup_config=wanted)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
