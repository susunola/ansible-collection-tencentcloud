#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tsf_application_config_release
short_description: Manage a Tencent Cloud TSF application configuration release
version_added: "0.15.0"
description: Publishes or revokes an exact TSF application configuration version for a deployment group. Release metadata is immutable after publication.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired release state.}
  config_id: {type: str, required: true, description: Configuration version ID.}
  group_id: {type: str, required: true, description: Target deployment group ID.}
  release_description: {type: str, description: Release description.}
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tsf_application_config_release:
    config_id: config-xxxxxxxx
    group_id: group-xxxxxxxx
    release_description: Production settings
"""
RETURN = r"""release: {description: Effective TSF configuration release metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.tsf.v20180326 import models, tsf_client

    return models, tsf_client


def desired(params):
    target = {"ConfigId": params["config_id"], "GroupId": params["group_id"]}
    if params.get("release_description") is not None:
        target["ReleaseDesc"] = params["release_description"]
    return target


def find(module, client, models, params):
    request = models.DescribeConfigReleasesRequest()
    request.ConfigId, request.GroupId = params["config_id"], params["group_id"]
    request.Offset, request.Limit = 0, 100
    result = module.sdk_call(client.DescribeConfigReleases, request).Result
    values = (result.Content if result else None) or []
    matches = [item for item in values if item.ConfigId == params["config_id"] and item.GroupId == params["group_id"]]
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSF configuration releases matched", config_id=params["config_id"], group_id=params["group_id"])
    return matches[0]._serialize(allow_none=True) if matches else None


def checked(module, response, action):
    if response.Result is False:
        module.fail_json(msg="Tencent Cloud rejected the TSF configuration %s" % action, request_id=response.RequestId)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "config_id": {"required": True},
            "group_id": {"required": True},
            "release_description": {},
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
                module.exit_json(changed=False, release=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.RevocationConfigRequest()
                request.ConfigReleaseId = current["ConfigReleaseId"]
                checked(module, module.sdk_call(client.RevocationConfig, request), "release revocation")
            module.exit_json(changed=True, **(diff or {}), release=None)
        target = desired(params)
        if current:
            require_immutable_unchanged(module, current, target, list(target), "TSF application configuration release")
            module.exit_json(changed=False, release=current)
        diff = maybe_diff(module, None, target)
        if not module.check_mode:
            request = models.ReleaseConfigRequest()
            request.ConfigId, request.GroupId = params["config_id"], params["group_id"]
            request.ReleaseDesc = params.get("release_description")
            checked(module, module.sdk_call(client.ReleaseConfig, request), "release")
            current = find(module, client, models, params)
        module.exit_json(changed=True, **(diff or {}), release=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
