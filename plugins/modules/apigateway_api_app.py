#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: apigateway_api_app
short_description: Create or delete a Tencent Cloud API Gateway application
version_added: "1.1.0"
description:
  - Creates or deletes a Tencent Cloud API Gateway application (API app / app
    key), identified by its application name. The module is idempotent; it
    reads the current API apps before changing anything.
  - An API app is the credential object that consumers use to call published
    APIs (bind it to a service or API with the dedicated bind modules).
options:
  state:
    description: Desired state of the API app.
    type: str
    choices: [present, absent]
    default: present
  api_app_name:
    description: Name of the API Gateway application.
    type: str
    required: true
  api_app_desc:
    description: Description of the API Gateway application.
    type: str
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create an API Gateway application
  susunola.tencentcloud.apigateway_api_app:
    api_app_name: mobile-client
    api_app_desc: Mobile client credentials

- name: Delete an API Gateway application
  susunola.tencentcloud.apigateway_api_app:
    api_app_name: mobile-client
    state: absent
'''

RETURN = r'''
api_app_name:
  description: Name of the API Gateway application the operation targeted.
  returned: always
  type: str
api_app_id:
  description: Application ID of the API app after the operation (empty when absent).
  returned: always
  type: str
exists:
  description: Whether the API app exists after the operation.
  returned: always
  type: bool
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def _load_apigateway():
    from tencentcloud.apigateway.v20180808 import models, apigateway_client
    return models, apigateway_client


def find_app(module, client, models, api_app_name):
    request = models.DescribeApiAppsStatusRequest()
    flt = models.Filter()
    flt.Name = "ApiAppName"
    flt.Values = [api_app_name]
    request.Filters = [flt]
    request.Limit = 100
    request.Offset = 0
    response = module.sdk_call(client.DescribeApiAppsStatus, request)
    result = getattr(response, "Result", None)
    apps = list(getattr(result, "ApiAppSet", None) or []) if result else []
    for item in apps:
        if getattr(item, "ApiAppName", None) == api_app_name:
            return item
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "api_app_name": {"type": "str", "required": True},
            "api_app_desc": {"type": "str"},
        },
        supports_check_mode=True,
    )
    p = module.params
    name = p["api_app_name"]
    desired_present = p["state"] == "present"
    module.require_sdk()
    models, apigateway_client = _load_apigateway()
    client = module.create_client(apigateway_client.ApigatewayClient, "apigateway.tencentcloudapi.com")
    try:
        current = find_app(module, client, models, name)
        if bool(current) == desired_present:
            module.exit_json(
                changed=False,
                api_app_name=name,
                api_app_id=getattr(current, "ApiAppId", "") if current else "",
                exists=bool(current),
                msg="API app %s already %s" % (name, "present" if desired_present else "absent"),
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                api_app_name=name,
                api_app_id="" if desired_present else (getattr(current, "ApiAppId", "") if current else ""),
                exists=desired_present,
                msg="Would %s API app %s" % ("create" if desired_present else "delete", name),
            )
        if desired_present:
            request = models.CreateApiAppRequest()
            request.ApiAppName = name
            if p["api_app_desc"] is not None:
                request.ApiAppDesc = p["api_app_desc"]
            module.sdk_call(client.CreateApiApp, request)
        else:
            request = models.DeleteApiAppRequest()
            request.ApiAppId = getattr(current, "ApiAppId", "")
            module.sdk_call(client.DeleteApiApp, request)
        final = find_app(module, client, models, name)
        module.exit_json(
            changed=True,
            api_app_name=name,
            api_app_id=getattr(final, "ApiAppId", "") if final else "",
            exists=bool(final),
            msg="API app %s %s" % (name, "created" if desired_present else "deleted"),
        )
    except Exception as exc:
        module.fail_sdk_error(exc, "Tencent Cloud API Gateway application request failed")


def main():
    run_module()


if __name__ == "__main__":
    main()
