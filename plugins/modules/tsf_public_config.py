#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tsf_public_config
short_description: Manage a versioned Tencent Cloud TSF public configuration
version_added: "0.15.0"
description: Creates and deletes an exact TSF public configuration version. Existing version content is immutable and drift is rejected.
options:
  state:
    description:
      - Desired resource state.
    type: str
    choices: [present, absent]
    default: present
  config_id:
    description:
      - Existing configuration ID; exact name and version are used when omitted.
    type: str
  name:
    description:
      - Configuration name.
    type: str
    required: true
  version:
    description:
      - Configuration version.
    type: str
    required: true
  value:
    description:
      - Configuration YAML value, required when creating.
    type: str
  version_description:
    description:
      - Configuration version description.
    type: str
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
attributes:
  check_mode:
    description:
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  diff_mode:
    description:
      - Returns the difference between the observed and the requested state
        when the task runs with C(--diff).
    support: full
  idempotent:
    description:
      - Reconciles the resource against its live state, so running again
        with the same arguments leaves it unchanged and reports C(changed=false).
    support: full
seealso:
  - module: susunola.tencentcloud.tsf_public_config_info
    description: Gather information about Tencent Cloud TSF public configs.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tsf_public_config:
    name: shared-observability
    version: v1
    value: 'logging: {level: INFO}'
"""
RETURN = r"""config:
  description:
    - Effective TSF public configuration version.
  returned: always
  type: dict"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, fail_from_sdk_error


def _load():
    from tencentcloud.tsf.v20180326 import models, tsf_client

    return models, tsf_client


def desired(params):
    mapping = {"name": "ConfigName", "version": "ConfigVersion", "value": "ConfigValue", "version_description": "ConfigVersionDesc"}
    target = {dest: params[source] for source, dest in mapping.items() if params.get(source) is not None}
    target["ConfigType"] = "public"
    return target


def detail(module, client, models, config_id):
    request = models.DescribePublicConfigRequest()
    request.ConfigId = config_id
    value = module.sdk_call(client.DescribePublicConfig, request).Result
    return value._serialize(allow_none=True) if value else None


def find(module, client, models, params):
    if params.get("config_id"):
        return detail(module, client, models, params["config_id"])
    request = models.DescribePublicConfigsRequest()
    request.ConfigName, request.ConfigVersion = params["name"], params["version"]
    request.Offset, request.Limit = 0, 100
    result = module.sdk_call(client.DescribePublicConfigs, request).Result
    values = (result.Content if result else None) or []
    matches = [item for item in values if item.ConfigName == params["name"] and item.ConfigVersion == params["version"]]
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSF public configuration versions matched", name=params["name"], version=params["version"])
    return detail(module, client, models, matches[0].ConfigId) if matches else None


def checked(module, response, action):
    if response.Result is False:
        module.fail_json(msg="Tencent Cloud rejected the TSF public configuration %s" % action, request_id=response.RequestId)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "config_id": {},
            "name": {"required": True},
            "version": {"required": True},
            "value": {},
            "version_description": {},
        },
        supports_check_mode=True,
    )
    params = module.params
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.TsfClient, "tsf.tencentcloudapi.com")
    try:
        current = find(module, client, models, params)
        if params["state"] == "absent":
            if not current:
                module.exit_json(changed=False, config=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.DeletePublicConfigRequest()
                request.ConfigId = current["ConfigId"]
                checked(module, module.sdk_call(client.DeletePublicConfig, request), "deletion")
            module.exit_json(changed=True, **(diff or {}), config=None)
        target = desired(params)
        if current:
            require_immutable_unchanged(module, current, target, list(target), "TSF public configuration version")
            module.exit_json(changed=False, config=current)
        if params.get("value") is None:
            module.fail_json(msg="value is required when creating a TSF public configuration")
        diff = maybe_diff(module, None, target)
        if not module.check_mode:
            request = models.CreatePublicConfigRequest()
            for key, value in target.items():
                setattr(request, key, value)
            request.EncodeWithBase64 = False
            checked(module, module.sdk_call(client.CreatePublicConfig, request), "creation")
            current = find(module, client, models, params)
        module.exit_json(changed=True, **(diff or {}), config=current if not module.check_mode else target)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
