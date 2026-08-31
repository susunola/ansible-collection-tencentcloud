#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: ckafka_datahub_connection
short_description: Manage Tencent Cloud CKafka Datahub connection resources
version_added: "0.14.0"
description:
  - Creates, updates and deletes CKafka Datahub connection resources.
  - Credential-like fields are accepted with no-log protection and removed recursively from output and drift comparison.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  resource_id: {type: str, description: Existing connection resource ID; preferred for rename and deletion.}
  name: {type: str, required: true, description: Connection resource name.}
  connection_type:
    type: str
    required: true
    choices: [DTS, MONGODB, ES, CLICKHOUSE, MYSQL, TDSQL_C_MYSQL, POSTGRESQL, TDSQL_C_POSTGRESQL, MARIADB, SQLSERVER, DORIS, KAFKA, MQTT]
    description: Immutable connection type.
  description: {type: str, default: '', description: Connection description.}
  config: {type: dict, required: true, description: SDK-compatible connection parameter object for the selected type.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.ckafka_datahub_connection:
    name: analytics-kafka
    connection_type: KAFKA
    description: Analytics destination
    config:
      Resource: ckafka-xxxxxxxx
      SelfBuilt: false
"""
RETURN = r"""connection: {description: CKafka Datahub connection metadata with credential fields removed., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload

TYPE_MODELS = {
    "DTS": ("DtsConnectParam", "DtsModifyConnectParam"),
    "MONGODB": ("MongoDBConnectParam", "MongoDBModifyConnectParam"),
    "ES": ("EsConnectParam", "EsModifyConnectParam"),
    "CLICKHOUSE": ("ClickHouseConnectParam", "ClickHouseModifyConnectParam"),
    "MYSQL": ("MySQLConnectParam", "MySQLModifyConnectParam"),
    "TDSQL_C_MYSQL": ("MySQLConnectParam", "MySQLModifyConnectParam"),
    "POSTGRESQL": ("PostgreSQLConnectParam", "PostgreSQLModifyConnectParam"),
    "TDSQL_C_POSTGRESQL": ("PostgreSQLConnectParam", "PostgreSQLModifyConnectParam"),
    "MARIADB": ("MariaDBConnectParam", "MariaDBModifyConnectParam"),
    "SQLSERVER": ("SQLServerConnectParam", "SQLServerModifyConnectParam"),
    "DORIS": ("DorisConnectParam", "DorisModifyConnectParam"),
    "KAFKA": ("KafkaConnectParam", "KafkaConnectParam"),
    "MQTT": ("MqttConnectParam", "MqttConnectParam"),
}
TYPE_FIELDS = {
    "DTS": "DtsConnectParam",
    "MONGODB": "MongoDBConnectParam",
    "ES": "EsConnectParam",
    "CLICKHOUSE": "ClickHouseConnectParam",
    "MYSQL": "MySQLConnectParam",
    "TDSQL_C_MYSQL": "MySQLConnectParam",
    "POSTGRESQL": "PostgreSQLConnectParam",
    "TDSQL_C_POSTGRESQL": "PostgreSQLConnectParam",
    "MARIADB": "MariaDBConnectParam",
    "SQLSERVER": "SQLServerConnectParam",
    "DORIS": "DorisConnectParam",
    "KAFKA": "KafkaConnectParam",
    "MQTT": "MqttConnectParam",
}
SENSITIVE = ("password", "secret", "token", "credential", "privatekey", "accesskey")


def _load():
    from tencentcloud.ckafka.v20190819 import ckafka_client, models

    return models, ckafka_client


def _model(models, name, value):
    item = getattr(models, name)()
    item._deserialize(value)
    return item


def describe_request(models, resource_id):
    request = models.DescribeConnectResourceRequest()
    request.ResourceId = resource_id
    return request


def list_request(models, p, offset=0):
    request = models.DescribeConnectResourcesRequest()
    request.Type, request.SearchWord, request.Offset, request.Limit = p["connection_type"], p["name"], offset, 1000
    return request


def create_request(models, p):
    request = models.CreateConnectResourceRequest()
    request.ResourceName, request.Type, request.Description = p["name"], p["connection_type"], p["description"]
    setattr(request, TYPE_FIELDS[p["connection_type"]], _model(models, TYPE_MODELS[p["connection_type"]][0], p["config"]))
    return request


def update_request(models, p, resource_id):
    request = models.ModifyConnectResourceRequest()
    request.ResourceId, request.ResourceName, request.Description, request.Type = resource_id, p["name"], p["description"], p["connection_type"]
    setattr(request, TYPE_FIELDS[p["connection_type"]], _model(models, TYPE_MODELS[p["connection_type"]][1], p["config"]))
    return request


def delete_request(models, resource_id):
    request = models.DeleteConnectResourceRequest()
    request.ResourceId = resource_id
    return request


def scrub(value):
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if not any(part in k.lower() for part in SENSITIVE)}
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value


def project(value, shape):
    if isinstance(shape, dict):
        return {key: project((value or {}).get(key), sub) for key, sub in shape.items()}
    if isinstance(shape, list):
        return value or []
    return value


def detail(module, client, models, resource_id):
    try:
        response = module.sdk_call(client.DescribeConnectResource, describe_request(models, resource_id))
        return scrub(response.Result._serialize(allow_none=True)) if response.Result else None
    except Exception as exc:
        if is_not_found(exc):
            return None
        raise


def find(module, client, models, p):
    if p.get("resource_id"):
        return detail(module, client, models, p["resource_id"])
    offset = 0
    while True:
        response = module.sdk_call(client.DescribeConnectResources, list_request(models, p, offset))
        result = response.Result
        items = list(result.ConnectResourceList or []) if result else []
        matches = [item for item in items if item.ResourceName == p["name"] and item.Type == p["connection_type"]]
        if matches:
            if len(matches) > 1:
                module.fail_json(msg="multiple CKafka Datahub connections matched name and type; specify resource_id")
            return detail(module, client, models, matches[0].ResourceId)
        offset += len(items)
        if not items or offset >= int(result.TotalCount or 0):
            return None


def comparable(value, p):
    field = TYPE_FIELDS[p["connection_type"]]
    shape = scrub(p["config"])
    return {
        "ResourceName": value.get("ResourceName"),
        "Type": value.get("Type"),
        "Description": value.get("Description") or "",
        "Config": project(value.get(field) or {}, shape),
    }


def desired(p):
    return {"ResourceName": p["name"], "Type": p["connection_type"], "Description": p["description"], "Config": scrub(p["config"])}


def run_module():
    types = sorted(TYPE_MODELS)
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "resource_id": {},
            "name": {"required": True},
            "connection_type": {"required": True, "choices": types},
            "description": {"default": ""},
            "config": {"type": "dict", "required": True, "no_log": True},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.CkafkaClient, "ckafka.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, connection=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteConnectResource, delete_request(models, current["ResourceId"]))
            module.exit_json(changed=True, **(diff or {}), connection=current if module.check_mode else None)
        target, before = desired(p), comparable(current, p) if current else None
        if before == target:
            module.exit_json(changed=False, connection=current)
        diff = maybe_diff(module, before, target)
        if current:
            require_immutable_unchanged(module, before, target, ("Type",), "CKafka Datahub connection")
        if not current and p.get("resource_id"):
            module.fail_json(msg="CKafka resource_id was not found; omit it to create a new connection")
        if not module.check_mode:
            if current:
                module.sdk_call(client.ModifyConnectResource, update_request(models, p, current["ResourceId"]))
            else:
                response = module.sdk_call(client.CreateConnectResource, create_request(models, p))
                p["resource_id"] = response.Result.ResourceId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), connection=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
