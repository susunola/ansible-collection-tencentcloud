#!/usr/bin/python
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: goosefs_fileset_info
short_description: Gather Tencent Cloud GooseFS filesets
version_added: "1.4.0"
description: Lists observable filesets for a GooseFS file system with optional ID, directory or exact-name filtering.
options:
  file_system_id: {description: GooseFS file system ID., type: str, required: true}
  fileset_id: {description: Fileset ID., type: str}
  name: {description: Exact fileset name., type: str}
  directory: {description: Exact fileset directory., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.goosefs_fileset_info:
    region: ap-guangzhou
    file_system_id: x-c60-xxxxxxxx
    directory: /analytics
'''
RETURN = r'''
filesets: {description: Matching filesets., returned: always, type: list, elements: dict}
fileset: {description: The single matching fileset when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the API., returned: always, type: str}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error
from ansible_collections.susunola.tencentcloud.plugins.modules.goosefs_fileset import describe_request

def matches(value, p):
    return all((
        p.get("fileset_id") is None or value.get("FsetId") == p["fileset_id"],
        p.get("name") is None or value.get("FsetName") == p["name"],
        p.get("directory") is None or value.get("FsetDir") == p["directory"],
    ))

def run_module():
    module = TencentCloudModule(
        argument_spec={"file_system_id": {"required": True}, "fileset_id": {}, "name": {}, "directory": {}},
        mutually_exclusive=[("fileset_id", "name", "directory")], supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    try:
        from tencentcloud.goosefs.v20220519 import goosefs_client, models
        client = module.create_client(goosefs_client.GoosefsClient, "goosefs.tencentcloudapi.com")
        response = module.sdk_call(client.DescribeFilesets, describe_request(models, p))
        values = [item._serialize(allow_none=True) for item in (response.FilesetList or [])]
        values = [item for item in values if matches(item, p)]
        module.exit_json(changed=False, filesets=values, fileset=values[0] if len(values) == 1 else None, request_id=getattr(response, "RequestId", None))
    except Exception as exc:
        fail_from_sdk_error(module, exc)

def main():
    run_module()

if __name__ == "__main__":
    main()
