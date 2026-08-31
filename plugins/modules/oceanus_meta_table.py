#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: oceanus_meta_table
short_description: Manage Tencent Cloud Oceanus metadata tables
version_added: "0.14.0"
description:
  - Creates an Oceanus metadata table and updates its DDL when it changes.
  - The Oceanus API does not expose metadata-table deletion, so this module manages the present lifecycle only.
options:
  table_name: {type: str, required: true, description: Metadata table name used as identity.}
  database_name: {type: str, required: true, description: Metadata database name used for lookup.}
  database_id: {type: int, required: true, description: Metadata database numeric ID used for creation.}
  catalog_name: {type: str, default: default_catalog, description: Catalog name used for lookup.}
  catalog_id: {type: int, default: 0, description: Catalog numeric ID used for creation.}
  workspace_id: {type: str, required: true, description: Owning Oceanus workspace ID.}
  cluster_id: {type: str, required: true, description: Oceanus cluster used to validate and apply the DDL.}
  flink_version: {type: str, required: true, description: Flink version used to validate and apply the DDL.}
  ddl: {type: str, required: true, description: Plain-text CREATE TABLE DDL; the module performs required Base64 encoding.}
  comment: {type: str, description: Table remark passed during creation and DDL updates; the read API does not expose it independently.}
  resource_refs: {type: list, elements: dict, description: SDK ResourceRef dependencies used during creation; the update API does not accept this field.}
  async_task_id: {type: str, description: Existing Oceanus asynchronous validation task ID.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.oceanus_meta_table:
    table_name: orders
    database_name: production
    database_id: 12
    workspace_id: space-xxxxxxxx
    cluster_id: cluster-xxxxxxxx
    flink_version: Flink-1.17
    ddl: |
      CREATE TABLE orders (id BIGINT, amount DECIMAL(18, 2))
      WITH ('connector' = 'kafka')
'''
RETURN = r'''meta_table: {description: Effective metadata table identity and encoded DDL., type: dict, returned: always}
table_id: {description: Oceanus metadata table ID., type: str, returned: when available}'''
import base64
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
def _load():
    from tencentcloud.oceanus.v20190422 import models,oceanus_client
    return models,oceanus_client
def encode_ddl(value): return base64.b64encode(value.encode("utf-8")).decode("ascii")
def get_request(models,p): r=models.GetMetaTableRequest(); r.Catalog,r.Database,r.Table,r.WorkSpaceId=p["catalog_name"],p["database_name"],p["table_name"],p["workspace_id"]; return r
def find(module,client,models,p):
    try: return module.sdk_call(client.GetMetaTable,get_request(models,p))._serialize(allow_none=True)
    except Exception as exc:
        if is_not_found(exc): return None
        raise
def create_request(models,p,encoded):
    payload={"CatalogId":p["catalog_id"],"DatabaseId":p["database_id"],"SqlCode":encoded,"Comment":p.get("comment"),"ClusterId":p["cluster_id"],"ResourceRefs":p.get("resource_refs"),"FlinkVersion":p["flink_version"],"WorkSpaceId":p["workspace_id"],"AsyncTaskId":p.get("async_task_id")}; r=models.CreateMetaTableRequest(); r.from_json_string(json.dumps(payload)); return r
def modify_request(models,p,current,encoded): r=models.ModifyMetaTableRequest(); r.ClusterId,r.TableId,r.SqlCode,r.FlinkVersion,r.WorkSpaceId,r.Remark=p["cluster_id"],current["SerialId"],encoded,p["flink_version"],p["workspace_id"],p.get("comment"); return r
def run_module():
    spec={"table_name":{"required":True},"database_name":{"required":True},"database_id":{"type":"int","required":True},"catalog_name":{"default":"default_catalog"},"catalog_id":{"type":"int","default":0},"workspace_id":{"required":True},"cluster_id":{"required":True},"flink_version":{"required":True},"ddl":{"required":True},"comment":{},"resource_refs":{"type":"list","elements":"dict"},"async_task_id":{}}
    module=TencentCloudModule(argument_spec=spec,supports_check_mode=True); p=module.params; module.require_sdk(); models,cm=_load(); client=module.create_client(cm.OceanusClient,"oceanus.tencentcloudapi.com")
    try:
        encoded=encode_ddl(p["ddl"]); current=find(module,client,models,p); target={"Catalog":p["catalog_name"],"Database":p["database_name"],"Table":p["table_name"],"DDL":encoded}
        before={key:current.get(key) for key in target} if current else None
        if before==target: module.exit_json(changed=False,meta_table=current,table_id=current.get("SerialId"))
        diff=maybe_diff(module,before,target); table_id=(current or {}).get("SerialId")
        if not module.check_mode:
            response=module.sdk_call(client.ModifyMetaTable,modify_request(models,p,current,encoded)) if current else module.sdk_call(client.CreateMetaTable,create_request(models,p,encoded)); table_id=table_id or str(response.TableId); current=find(module,client,models,p)
        module.exit_json(changed=True,**(diff or {}),meta_table=current if not module.check_mode else target,table_id=table_id)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))
def main(): run_module()
if __name__=="__main__": main()
