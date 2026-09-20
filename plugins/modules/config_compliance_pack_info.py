#!/usr/bin/python
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: config_compliance_pack_info
short_description: Gather Tencent Cloud Config compliance packs
version_added: "1.4.0"
description: Lists compliance packs and resolves matches to their complete rule configuration.
options:
  compliance_pack_id: {description: Compliance pack ID., type: str}
  name: {description: Exact compliance pack name., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.config_compliance_pack_info:
    region: ap-guangzhou
    name: production-security
'''
RETURN = r'''
compliance_packs: {description: Matching complete compliance packs., returned: always, type: list, elements: dict}
compliance_pack: {description: The single matching pack when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import create_client_profile, create_credential, sdk_call, serialize_sdk_object, tencentcloud_argument_spec


def list_request(models, name=None, offset=0, limit=100):
    request = models.ListCompliancePacksRequest()
    request.CompliancePackName, request.Offset, request.Limit = name, offset, limit
    return request


def detail_request(models, pack_id):
    request = models.DescribeCompliancePackRequest()
    request.CompliancePackId = pack_id
    return request


def run_module():
    spec = tencentcloud_argument_spec()
    spec.update({"compliance_pack_id": {"type": "str"}, "name": {"type": "str"}})
    module = AnsibleModule(argument_spec=spec, mutually_exclusive=[("compliance_pack_id", "name")], supports_check_mode=True)
    try:
        from tencentcloud.config.v20220802 import config_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-config package is required.")
    p = module.params
    client = config_client.ConfigClient(create_credential(module), p["region"], create_client_profile(module, "config.tencentcloudapi.com"))
    offset, summaries, request_id = 0, [], None
    while True:
        response = sdk_call(module, client.ListCompliancePacks, list_request(models, p.get("name"), offset))
        request_id = getattr(response, "RequestId", None)
        page = list(getattr(response, "Items", None) or [])
        for item in page:
            if (p.get("compliance_pack_id") is None or item.CompliancePackId == p["compliance_pack_id"]) and (p.get("name") is None or item.CompliancePackName == p["name"]):
                summaries.append(item)
        offset += len(page)
        if not page or offset >= int(getattr(response, "Total", 0) or 0):
            break
    packs = []
    for summary in summaries:
        response = sdk_call(module, client.DescribeCompliancePack, detail_request(models, summary.CompliancePackId))
        request_id = getattr(response, "RequestId", None)
        value = serialize_sdk_object(response)
        value.pop("RequestId", None)
        packs.append(value)
    module.exit_json(changed=False, compliance_packs=packs, compliance_pack=packs[0] if len(packs) == 1 else None, request_id=request_id)


def main():
    run_module()


if __name__ == "__main__":
    main()
