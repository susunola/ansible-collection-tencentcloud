#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tse_governance_service_contract_info
short_description: Gather Tencent Cloud TSE governance service contracts
version_added: "0.14.0"
description: Returns paginated service contracts and the available contract versions for a governance service.
options:
  instance_id: {type: str, required: true, description: TSE engine instance ID.}
  namespace: {type: str, required: true, description: Governance namespace.}
  service: {type: str, required: true, description: Governance service name.}
  name: {type: str, description: Contract name filter.}
  contract_version: {type: str, description: Contract version filter.}
  protocol: {type: str, description: Contract protocol filter.}
  brief: {type: bool, default: false, description: Return basic contract information only.}
  page_size: {type: int, default: 100, description: Number of contracts requested per API call.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tse_governance_service_contract_info:
    instance_id: ins-xxxxxxxx
    namespace: production
    service: orders
  register: service_contracts
'''
RETURN = r'''
contracts: {description: Matching service contract definitions., type: list, elements: dict, returned: always}
versions: {description: Contract versions available for the service., type: list, elements: dict, returned: always}
total_count: {description: Contract count reported by the API., type: int, returned: always}
request_ids: {description: Request IDs for contract and version queries., type: dict, returned: always}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client
    return models, tse_client


def contract_request(models, params, offset):
    value = models.DescribeGovernanceServiceContractsRequest()
    value.InstanceId, value.Namespace, value.Service = params["instance_id"], params["namespace"], params["service"]
    value.Name, value.ContractVersion = params.get("name"), params.get("contract_version")
    value.Protocol, value.Brief = params.get("protocol"), params["brief"]
    value.Offset, value.Limit = offset, params["page_size"]
    return value


def version_request(models, params):
    value = models.DescribeGovernanceServiceContractVersionsRequest()
    value.InstanceId, value.Namespace, value.Service = params["instance_id"], params["namespace"], params["service"]
    return value


def fetch_contracts(module, client, models, params):
    contracts, offset, total, request_id = [], 0, None, None
    while total is None or offset < total:
        response = module.sdk_call(
            client.DescribeGovernanceServiceContracts, contract_request(models, params, offset)
        )
        page = response.ServiceContracts or []
        contracts.extend(item._serialize(allow_none=True) for item in page)
        total, request_id = response.TotalCount, response.RequestId
        offset += len(page)
        if not page:
            break
    return contracts, total if total is not None else len(contracts), request_id


def run_module():
    module = TencentCloudModule(argument_spec={
        "instance_id": {"required": True}, "namespace": {"required": True},
        "service": {"required": True}, "name": {}, "contract_version": {}, "protocol": {},
        "brief": {"type": "bool", "default": False},
        "page_size": {"type": "int", "default": 100},
    }, supports_check_mode=True)
    params = module.params
    if params["page_size"] < 1 or params["page_size"] > 100:
        module.fail_json(msg="page_size must be between 1 and 100")
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.TseClient, "tse.tencentcloudapi.com")
    try:
        contracts, total_count, contract_request_id = fetch_contracts(module, client, models, params)
        response = module.sdk_call(
            client.DescribeGovernanceServiceContractVersions, version_request(models, params)
        )
        versions = [item._serialize(allow_none=True) for item in (response.GovernanceServiceContractVersions or [])]
        module.exit_json(
            changed=False, contracts=contracts, versions=versions, total_count=total_count,
            request_ids={"contracts": contract_request_id, "versions": response.RequestId},
        )
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
