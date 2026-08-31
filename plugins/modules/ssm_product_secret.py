#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: ssm_product_secret
short_description: Manage Tencent Cloud SSM managed-product secrets
version_added: "0.14.0"
description:
  - Creates and governs database credentials whose account lifecycle and rotation are managed by SSM.
  - Creation is asynchronous and is not reported complete until the SSM task succeeds.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  secret_name: {type: str, required: true, description: SSM secret name.}
  product_name: {type: str, description: Product identifier returned by the SSM supported-products API; required for creation.}
  instance_id: {type: str, description: Bound cloud product instance ID; required for creation.}
  username_prefix: {type: str, description: Generated database account prefix of at most eight characters; required for creation.}
  domains: {type: list, elements: str, default: ['%'], description: Account host domains.}
  privileges: {type: list, elements: dict, default: [], description: Product privilege units accepted by SSM.}
  description: {type: str, default: managed by Ansible, description: Secret description.}
  kms_key_id: {type: str, description: Customer KMS key ID.}
  kms_hsm_cluster_id: {type: str, description: Dedicated KMS HSM cluster ID.}
  encrypt_type: {type: int, choices: [0, 1], default: 0, description: KMS or software-key encryption.}
  tags: {type: dict, default: {}, description: Creation tags.}
  enabled: {type: bool, default: true, description: Whether the secret is enabled.}
  rotation_enabled: {type: bool, default: false, description: Whether automatic rotation is enabled.}
  rotation_frequency: {type: int, default: 30, description: Rotation frequency in days.}
  rotation_begin_time: {type: str, description: First rotation time in C(YYYY-MM-DD HH:MM:SS) format.}
  account_remark: {type: str, description: Database account remark.}
  account_type: {type: str, choices: [L3], description: SQL Server account type.}
  recovery_window_days: {type: int, default: 7, description: Deletion recovery window from 0 through 30 days.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  waiter_delay: {type: int, default: 5, description: Async polling interval.}
  waiter_timeout: {type: int, default: 600, description: Async polling timeout.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.ssm_product_secret:
    secret_name: orders-db-managed
    product_name: Mysql
    instance_id: cdb-xxxxxxxx
    username_prefix: ssmapp
    privileges:
      - privilege_name: GlobalPrivileges
        privileges: [SELECT, INSERT, UPDATE]
    rotation_enabled: true
    rotation_begin_time: '2026-09-02 02:00:00'
    rotation_frequency: 30
'''
RETURN = r'''secret: {description: Effective metadata without credential values., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_task


def _load():
    from tencentcloud.ssm.v20190923 import models, ssm_client
    return models, ssm_client


def _request(models, name, **values):
    request = getattr(models, name)()
    for key, value in values.items():
        if value is not None: setattr(request, key, value)
    return request


def _objects(models, class_name, values):
    result = []
    field_map = {"privilege_name": "PrivilegeName", "privileges": "Privileges", "database": "Database", "table_name": "TableName", "column_name": "ColumnName", "schema_name": "SchemaName", "sequence_name": "SequenceName", "procedure_name": "ProcedureName", "type_name": "TypeName", "function_name": "FunctionName", "view_name": "ViewName", "matview_name": "MatviewName", "key": "TagKey", "value": "TagValue"}
    for value in values:
        item = getattr(models, class_name)()
        for key, field_value in value.items():
            if field_value is not None: setattr(item, field_map[key], field_value)
        result.append(item)
    return result


def find(module, client, models, name):
    try:
        response = module.sdk_call(client.DescribeSecret, _request(models, "DescribeSecretRequest", SecretName=name))
        return response._serialize(allow_none=True)
    except Exception as exc:
        if is_not_found(exc): return None
        raise


def create_request(models, p):
    tags = [{"key": key, "value": value} for key, value in sorted(p["tags"].items())]
    return _request(models, "CreateProductSecretRequest", SecretName=p["secret_name"], UserNamePrefix=p["username_prefix"], ProductName=p["product_name"], InstanceID=p["instance_id"], Domains=p["domains"], PrivilegesList=_objects(models, "ProductPrivilegeUnit", p["privileges"]), Description=p["description"], KmsKeyId=p.get("kms_key_id"), Tags=_objects(models, "Tag", tags), RotationBeginTime=p.get("rotation_begin_time"), EnableRotation=p["rotation_enabled"], RotationFrequency=p["rotation_frequency"], KmsHsmClusterId=p.get("kms_hsm_cluster_id"), AccountRemark=p.get("account_remark"), AccountType=p.get("account_type"), EncryptType=p["encrypt_type"])


def wait_task(module, client, models, flow_id):
    if flow_id is None: module.fail_json(msg="SSM mutation returned no FlowID; asynchronous completion cannot be verified")
    def poll():
        response = module.sdk_call(client.DescribeAsyncRequestInfo, _request(models, "DescribeAsyncRequestInfoRequest", FlowID=flow_id))
        return response.TaskStatus, response.Description, response
    return wait_for_task(module, poll, timeout=module.params["waiter_timeout"], delay=module.params["waiter_delay"], success_statuses=(1,), failure_statuses=(2,))


def comparable(value):
    return {"SecretName": value.get("SecretName"), "Description": value.get("Description") or "", "ProductName": value.get("ProductName"), "ResourceID": value.get("ResourceID"), "Enabled": value.get("Status") == "Enabled", "RotationStatus": int(value.get("RotationStatus") or 0), "RotationFrequency": int(value.get("RotationFrequency") or 0)}


def run_module():
    privilege = {key: {"type": "list", "elements": "str"} if key == "privileges" else {"type": "str"} for key in ("privilege_name", "privileges", "database", "table_name", "column_name", "schema_name", "sequence_name", "procedure_name", "type_name", "function_name", "view_name", "matview_name")}
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "secret_name": {"required": True}, "product_name": {}, "instance_id": {}, "username_prefix": {}, "domains": {"type": "list", "elements": "str", "default": ["%"]}, "privileges": {"type": "list", "elements": "dict", "options": privilege, "default": []}, "description": {"default": "managed by Ansible"}, "kms_key_id": {}, "kms_hsm_cluster_id": {}, "encrypt_type": {"type": "int", "choices": [0, 1], "default": 0}, "tags": {"type": "dict", "default": {}}, "enabled": {"type": "bool", "default": True}, "rotation_enabled": {"type": "bool", "default": False}, "rotation_frequency": {"type": "int", "default": 30}, "rotation_begin_time": {}, "account_remark": {}, "account_type": {"choices": ["L3"]}, "recovery_window_days": {"type": "int", "default": 7}}, supports_check_mode=True)
    p = module.params
    if p["state"] == "present" and any(not p.get(key) for key in ("product_name", "instance_id", "username_prefix")): module.fail_json(msg="product_name, instance_id and username_prefix are required when state=present")
    if p.get("username_prefix") and len(p["username_prefix"]) > 8: module.fail_json(msg="username_prefix must be at most eight characters")
    if not 0 <= p["recovery_window_days"] <= 30: module.fail_json(msg="recovery_window_days must be between 0 and 30")
    if p["rotation_enabled"] and not p.get("rotation_begin_time"): module.fail_json(msg="rotation_begin_time is required when rotation_enabled=true")
    if p["rotation_enabled"] and not 30 <= p["rotation_frequency"] <= 365: module.fail_json(msg="rotation_frequency must be between 30 and 365 days")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.SsmClient, "ssm.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["secret_name"])
        if p["state"] == "absent":
            if not current or current.get("Status") == "PendingDelete": module.exit_json(changed=False, secret=current)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode: module.sdk_call(client.DeleteSecret, _request(models, "DeleteSecretRequest", SecretName=p["secret_name"], RecoveryWindowInDays=p["recovery_window_days"])); current = find(module, client, models, p["secret_name"])
            module.exit_json(changed=True, **(diff or {}), secret=current)
        restored = bool(current and current.get("Status") == "PendingDelete")
        if restored and not module.check_mode: module.sdk_call(client.RestoreSecret, _request(models, "RestoreSecretRequest", SecretName=p["secret_name"])); current = find(module, client, models, p["secret_name"])
        if current:
            before = comparable(current)
            if before["ProductName"] != p["product_name"] or before["ResourceID"] != p["instance_id"]: module.fail_json(msg="product_name and instance_id are immutable after creation", current=before)
            target = dict(before); target.update({"Description": p["description"], "Enabled": p["enabled"], "RotationStatus": int(p["rotation_enabled"]), "RotationFrequency": p["rotation_frequency"]})
            if before == target and not restored: module.exit_json(changed=False, secret=current)
            diff = maybe_diff(module, before, target)
            if not module.check_mode:
                if before["Description"] != target["Description"]: module.sdk_call(client.UpdateDescription, _request(models, "UpdateDescriptionRequest", SecretName=p["secret_name"], Description=p["description"]))
                if before["Enabled"] != target["Enabled"]: module.sdk_call(client.EnableSecret if p["enabled"] else client.DisableSecret, _request(models, "EnableSecretRequest" if p["enabled"] else "DisableSecretRequest", SecretName=p["secret_name"]))
                if before["RotationStatus"] != target["RotationStatus"] or before["RotationFrequency"] != target["RotationFrequency"]: module.sdk_call(client.UpdateRotationStatus, _request(models, "UpdateRotationStatusRequest", SecretName=p["secret_name"], EnableRotation=p["rotation_enabled"], Frequency=p["rotation_frequency"], RotationBeginTime=p.get("rotation_begin_time")))
                current = find(module, client, models, p["secret_name"])
            module.exit_json(changed=True, **(diff or {}), secret=current if not module.check_mode else target)
        target = {"SecretName": p["secret_name"], "Description": p["description"], "ProductName": p["product_name"], "ResourceID": p["instance_id"], "Enabled": p["enabled"], "RotationStatus": int(p["rotation_enabled"]), "RotationFrequency": p["rotation_frequency"]}; diff = maybe_diff(module, None, target)
        if not module.check_mode:
            response = module.sdk_call(client.CreateProductSecret, create_request(models, p)); wait_task(module, client, models, response.FlowID); current = find(module, client, models, p["secret_name"])
            if not p["enabled"]: module.sdk_call(client.DisableSecret, _request(models, "DisableSecretRequest", SecretName=p["secret_name"])); current = find(module, client, models, p["secret_name"])
        module.exit_json(changed=True, **(diff or {}), secret=current if not module.check_mode else target)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
