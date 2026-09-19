#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: ckafka_datahub_connection_info
short_description: Gather Tencent Cloud CKafka Datahub connections
version_added: "1.4.0"
description:
  - Reads a Datahub connection by ID or lists connections with optional server-side filters.
  - Credential-like fields are recursively removed from returned data.
options:
  resource_id: {description: Connection resource ID. When set, returns the detailed resource., type: str}
  name: {description: Search text applied by the service., type: str}
  connection_type:
    description: Connection type used to filter listed resources.
    type: str
    choices: [DTS, MONGODB, ES, CLICKHOUSE, MYSQL, TDSQL_C_MYSQL, POSTGRESQL, TDSQL_C_POSTGRESQL, MARIADB, SQLSERVER, DORIS, KAFKA, MQTT]
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Read a Datahub connection by ID
  susunola.tencentcloud.ckafka_datahub_connection_info:
    region: ap-guangzhou
    resource_id: resource-xxxxxxxx

- name: List Kafka connections
  susunola.tencentcloud.ckafka_datahub_connection_info:
    region: ap-guangzhou
    connection_type: KAFKA
'''

RETURN = r'''
connections: {description: Matching connections with credentials removed., returned: always, type: list, elements: dict}
connection: {description: The single matching connection when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.errors import is_not_found
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile, create_credential, sdk_call, serialize_sdk_object, tencentcloud_argument_spec,
)

CONNECTION_TYPES = ["DTS", "MONGODB", "ES", "CLICKHOUSE", "MYSQL", "TDSQL_C_MYSQL", "POSTGRESQL", "TDSQL_C_POSTGRESQL", "MARIADB", "SQLSERVER", "DORIS", "KAFKA", "MQTT"]
SENSITIVE = ("password", "secret", "token", "credential", "privatekey", "accesskey")


def scrub(value):
    if isinstance(value, dict):
        return {key: scrub(item) for key, item in value.items() if not any(part in key.lower() for part in SENSITIVE)}
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value


def detail_request(models, resource_id):
    request = models.DescribeConnectResourceRequest()
    request.ResourceId = resource_id
    return request


def list_request(models, connection_type=None, name=None, offset=0, limit=100):
    request = models.DescribeConnectResourcesRequest()
    request.Type, request.SearchWord = connection_type, name
    request.Offset, request.Limit = offset, limit
    return request


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({
        "resource_id": {"type": "str"},
        "name": {"type": "str"},
        "connection_type": {"type": "str", "choices": CONNECTION_TYPES},
    })
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    try:
        from tencentcloud.ckafka.v20190819 import ckafka_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-ckafka package is required.")
    p = module.params
    client = ckafka_client.CkafkaClient(create_credential(module), p["region"], create_client_profile(module, "ckafka.tencentcloudapi.com"))
    if p.get("resource_id"):
        try:
            response = sdk_call(module, client.DescribeConnectResource, detail_request(models, p["resource_id"]))
        except Exception as exc:
            if is_not_found(exc):
                module.exit_json(changed=False, connections=[], connection=None, request_id=getattr(exc, "request_id", None))
            raise
        connection = scrub(serialize_sdk_object(response.Result)) if getattr(response, "Result", None) else None
        module.exit_json(changed=False, connections=[connection] if connection else [], connection=connection, request_id=getattr(response, "RequestId", None))

    offset, connections, request_id = 0, [], None
    while True:
        response = sdk_call(module, client.DescribeConnectResources, list_request(models, p.get("connection_type"), p.get("name"), offset))
        request_id = getattr(response, "RequestId", None)
        result = getattr(response, "Result", None)
        page = list(getattr(result, "ConnectResourceList", None) or [])
        connections.extend(scrub(serialize_sdk_object(item)) for item in page)
        total = int(getattr(result, "TotalCount", 0) or 0)
        offset += len(page)
        if not page or offset >= total:
            break
    module.exit_json(changed=False, connections=connections, connection=connections[0] if len(connections) == 1 else None, request_id=request_id)


def main():
    run_module()


if __name__ == "__main__":
    main()
