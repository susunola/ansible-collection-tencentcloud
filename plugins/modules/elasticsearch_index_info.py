#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: elasticsearch_index_info
short_description: Gather Tencent Cloud Elasticsearch index metadata
version_added: "1.4.0"
description: Returns one exact Elasticsearch index through the managed index metadata API.
options:
  instance_id: {description: Elasticsearch instance ID., type: str, required: true}
  name: {description: Index name., type: str, required: true}
  index_type: {description: Index type accepted by the service., type: str, required: true}
  username: {description: Elasticsearch username., type: str, required: true}
  password: {description: Elasticsearch password., type: str, required: true, no_log: true}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.elasticsearch_index_info:
    region: ap-guangzhou
    instance_id: es-xxxxxxxx
    name: orders
    index_type: normal
    username: elastic
    password: '{{ elastic_password }}'
'''
RETURN = r'''
indices: {description: Matching index as an empty or single-element list., returned: always, type: list, elements: dict}
index: {description: Index metadata or null., returned: always, type: dict}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.modules.elasticsearch_index import find

def run_module():
    module = TencentCloudModule(argument_spec={
        "instance_id": {"required": True}, "name": {"required": True}, "index_type": {"required": True},
        "username": {"required": True}, "password": {"required": True, "no_log": True},
    }, supports_check_mode=True)
    module.require_sdk()
    try:
        from tencentcloud.es.v20180416 import es_client, models
        client = module.create_client(es_client.EsClient, "es.tencentcloudapi.com")
        value = find(module, client, models, module.params)
        module.exit_json(changed=False, indices=[value] if value else [], index=value)
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
