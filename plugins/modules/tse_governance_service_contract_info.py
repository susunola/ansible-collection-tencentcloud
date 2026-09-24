#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tse_governance_service_contract_info
short_description: Gather Tencent Cloud TSE governance service contracts
version_added: "0.14.0"
description: Returns paginated service contracts and the available contract versions for a governance service.
options:
  instance_id:
    description:
      - TSE engine instance ID.
    type: str
    required: true
  namespace:
    description:
      - Governance namespace.
    type: str
    required: true
  service:
    description:
      - Governance service name.
    type: str
    required: true
  name:
    description:
      - Contract name filter.
    type: str
  contract_version:
    description:
      - Contract version filter.
    type: str
  protocol:
    description:
      - Contract protocol filter.
    type: str
  brief:
    description:
      - Return basic contract information only.
    type: bool
    default: false
  page_size:
    description:
      - Number of contracts requested per API call.
    type: int
    default: 100
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
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
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


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
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
