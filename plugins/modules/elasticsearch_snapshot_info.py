#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: elasticsearch_snapshot_info
short_description: Gather a Tencent Cloud Elasticsearch snapshot
version_added: "1.4.0"
description: Returns an exact Elasticsearch cluster snapshot by instance, repository and name.
options:
  instance_id: {description: Elasticsearch instance ID., type: str, required: true}
  repository_name: {description: Snapshot repository name., type: str, required: true}
  name: {description: Snapshot name., type: str, required: true}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.elasticsearch_snapshot_info:
    region: ap-guangzhou
    instance_id: es-xxxxxxxx
    repository_name: backup-repository
    name: daily-2026-09-21
'''
RETURN = r'''
snapshots: {description: Matching snapshot as an empty or single-element list., returned: always, type: list, elements: dict}
snapshot: {description: Snapshot metadata or null., returned: always, type: dict}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.modules.elasticsearch_snapshot import find

def run_module():
    module = TencentCloudModule(argument_spec={
        "instance_id": {"required": True}, "repository_name": {"required": True}, "name": {"required": True},
    }, supports_check_mode=True)
    module.require_sdk()
    try:
        from tencentcloud.es.v20180416 import es_client, models
        client = module.create_client(es_client.EsClient, "es.tencentcloudapi.com")
        value = find(module, client, models, module.params)
        module.exit_json(changed=False, snapshots=[value] if value else [], snapshot=value)
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
