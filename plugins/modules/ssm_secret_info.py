#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: ssm_secret_info
short_description: Gather Tencent Cloud Secrets Manager metadata
version_added: "0.14.0"
description:
  - Returns exact Secret metadata or a bounded, filtered inventory.
  - Never retrieves Secret values.
options:
  secret_name: {type: str, description: Exact Secret name.}
  state_filter: {type: int, choices: [0, 1, 2, 3, 4, 5], default: 0, description: API state filter in list mode.}
  search_name: {type: str, description: Name search expression in list mode.}
  tag_filters: {type: dict, default: {}, description: Tag keys mapped to value lists in list mode.}
  secret_type: {type: int, choices: [0, 1, 2, 3, 4], description: Secret type filter.}
  product_name: {type: str, description: Cloud product name filter.}
  encrypt_type: {type: int, choices: [0, 1], description: Encryption type filter.}
  instance_id: {type: str, description: Cloud product instance filter.}
  order: {type: str, choices: [ascending, descending], default: descending, description: Creation-time ordering.}
  page_size: {type: int, default: 100, description: Results requested per page, from 1 to 100.}
  max_pages: {type: int, default: 1000, description: Maximum pages fetched.}
  retries: {type: int, default: 5, description: Retries for transient API failures.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.ssm_secret_info:
    secret_name: prod/database
- susunola.tencentcloud.ssm_secret_info:
    state_filter: 1
    tag_filters: {environment: [production]}
'''
RETURN = r'''
secret: {description: Exact Secret metadata., type: dict, returned: in exact mode}
secrets: {description: Matching Secret metadata., type: list, elements: dict, returned: in list mode}
total_count: {description: Matching count., type: int, returned: in list mode}
truncated: {description: Whether max_pages stopped pagination., type: bool, returned: in list mode}
request_id: {description: Tencent Cloud request ID., type: str, returned: always}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.ssm.v20190923 import models, ssm_client
    return models, ssm_client


def exact_request(models, name): request = models.DescribeSecretRequest(); request.SecretName = name; return request


def list_request(models, p, offset):
    request = models.ListSecretsRequest(); request.Offset, request.Limit = offset, p["page_size"]; request.OrderType, request.State = (1 if p["order"] == "ascending" else 0), p["state_filter"]
    for source, target in (("search_name", "SearchSecretName"), ("secret_type", "SecretType"), ("product_name", "ProductName"), ("encrypt_type", "EncryptType"), ("instance_id", "InstanceID")):
        if p.get(source) is not None: setattr(request, target, p[source])
    if p["tag_filters"]:
        request.TagFilters = []
        for key, values in sorted(p["tag_filters"].items()):
            item = models.TagFilter(); item.TagKey, item.TagValue = key, values if isinstance(values, list) else [values]; request.TagFilters.append(item)
    return request


def read_list(module, client, models, p):
    values, total, offset, request_id, truncated = [], 0, 0, None, False
    for _ in range(p["max_pages"]):
        response = module.sdk_call(client.ListSecrets, list_request(models, p, offset)); items = response.SecretMetadatas or []
        values.extend(item._serialize(allow_none=True) for item in items); total, request_id = int(response.TotalCount or 0), response.RequestId; offset += len(items)
        if not items or offset >= total: break
    else: truncated = True
    return values, total, truncated, request_id


def run_module():
    spec = {"secret_name": {}, "state_filter": {"type": "int", "choices": [0, 1, 2, 3, 4, 5], "default": 0}, "search_name": {}, "tag_filters": {"type": "dict", "default": {}}, "secret_type": {"type": "int", "choices": [0, 1, 2, 3, 4]}, "product_name": {}, "encrypt_type": {"type": "int", "choices": [0, 1]}, "instance_id": {}, "order": {"choices": ["ascending", "descending"], "default": "descending"}, "page_size": {"type": "int", "default": 100}, "max_pages": {"type": "int", "default": 1000}}
    list_options = ("search_name", "tag_filters", "secret_type", "product_name", "encrypt_type", "instance_id")
    module = TencentCloudModule(argument_spec=spec, supports_check_mode=True, mutually_exclusive=[("secret_name", value) for value in list_options]); p = module.params
    if not 1 <= p["page_size"] <= 100 or not 1 <= p["max_pages"] <= 1000: module.fail_json(msg="page_size and max_pages are outside supported bounds")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.SsmClient, "ssm.tencentcloudapi.com")
    try:
        if p.get("secret_name"):
            response = module.sdk_call(client.DescribeSecret, exact_request(models, p["secret_name"])); value = response._serialize(allow_none=True); request_id = value.pop("RequestId", response.RequestId)
            module.exit_json(changed=False, secret=value, request_id=request_id)
        values, total, truncated, request_id = read_list(module, client, models, p); module.exit_json(changed=False, secrets=values, total_count=total, truncated=truncated, request_id=request_id)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
