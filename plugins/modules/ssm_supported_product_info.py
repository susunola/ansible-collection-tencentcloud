#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: ssm_supported_product_info
short_description: Gather cloud products supported by Tencent Cloud SSM
version_added: "0.14.0"
description:
  - Returns the region-specific product identifiers accepted by C(ssm_product_secret).
options:
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.ssm_supported_product_info:
  register: ssm_products
'''
RETURN = r'''
products: {description: Product identifiers supported in the selected region., type: list, elements: str, returned: always}
total_count: {description: Number of supported products., type: int, returned: always}
request_id: {description: Tencent Cloud request ID., type: str, returned: always}
'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.ssm.v20190923 import models, ssm_client
    return models, ssm_client


def request(models): return models.DescribeSupportedProductsRequest()


def run_module():
    module = TencentCloudModule(argument_spec={}, supports_check_mode=True)
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.SsmClient, "ssm.tencentcloudapi.com")
    try:
        response = module.sdk_call(client.DescribeSupportedProducts, request(models))
        products = sorted(response.Products or [])
        module.exit_json(changed=False, products=products, total_count=int(response.TotalCount or len(products)), request_id=response.RequestId)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
