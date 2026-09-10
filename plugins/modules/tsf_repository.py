#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: tsf_repository
short_description: Manage a Tencent Cloud TSF package repository
version_added: "0.15.0"
description: Creates, updates and deletes a TSF package repository with immutable storage placement protection.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired resource state.}
  repository_id: {type: str, description: Existing repository ID; exact name and type are used when omitted.}
  name: {type: str, required: true, description: Repository name.}
  repository_type: {type: str, choices: [default, private], required: true, description: Repository type.}
  description: {type: str, description: Repository description.}
  bucket_name: {type: str, description: 'COS bucket name, required for a private repository.'}
  bucket_region: {type: str, description: 'COS bucket region, required for a private repository.'}
  directory: {type: str, description: Repository directory in the COS bucket.}
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tsf_repository:
    name: production-packages
    repository_type: private
    bucket_name: tsf-packages-1250000000
    bucket_region: ap-guangzhou
    directory: releases
"""
RETURN = r"""repository: {description: Effective TSF repository metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.tsf.v20180326 import models, tsf_client

    return models, tsf_client


def desired(params):
    mapping = {
        "name": "RepositoryName",
        "repository_type": "RepositoryType",
        "description": "RepositoryDesc",
        "bucket_name": "BucketName",
        "bucket_region": "BucketRegion",
        "directory": "Directory",
    }
    return {target: params[source] for source, target in mapping.items() if params.get(source) is not None}


def find(module, client, models, params):
    if params.get("repository_id"):
        request = models.DescribeRepositoryRequest()
        request.RepositoryId = params["repository_id"]
        value = module.sdk_call(client.DescribeRepository, request).Result
        return value._serialize(allow_none=True) if value else None
    request = models.DescribeRepositoriesRequest()
    request.SearchWord = params["name"]
    request.RepositoryType, request.Offset, request.Limit = params["repository_type"], 0, 100
    result = module.sdk_call(client.DescribeRepositories, request).Result
    values = (result.Content if result else None) or []
    matches = [item for item in values if item.RepositoryName == params["name"] and item.RepositoryType == params["repository_type"]]
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSF repositories matched", name=params["name"], repository_type=params["repository_type"])
    return matches[0]._serialize(allow_none=True) if matches else None


def checked(module, response, action):
    if response.Result is False:
        module.fail_json(msg="Tencent Cloud rejected the TSF repository %s" % action, request_id=response.RequestId)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "repository_id": {},
            "name": {"required": True},
            "repository_type": {"choices": ["default", "private"], "required": True},
            "description": {},
            "bucket_name": {},
            "bucket_region": {},
            "directory": {},
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
                module.exit_json(changed=False, repository=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.DeleteRepositoryRequest()
                request.RepositoryId = current["RepositoryId"]
                checked(module, module.sdk_call(client.DeleteRepository, request), "deletion")
            module.exit_json(changed=True, **(diff or {}), repository=None)
        target = desired(params)
        if current:
            require_immutable_unchanged(
                module, current, target, ["RepositoryName", "RepositoryType", "BucketName", "BucketRegion", "Directory"], "TSF repository"
            )
        elif params["repository_type"] == "private" and (not params.get("bucket_name") or not params.get("bucket_region")):
            module.fail_json(msg="bucket_name and bucket_region are required when creating a private TSF repository")
        comparable = {key: current.get(key) for key in target} if current else None
        if current and comparable == target:
            module.exit_json(changed=False, repository=current)
        diff = maybe_diff(module, comparable, target)
        if not module.check_mode:
            if current:
                request = models.UpdateRepositoryRequest()
                request.RepositoryId = current["RepositoryId"]
                request.RepositoryDesc = target.get("RepositoryDesc")
                checked(module, module.sdk_call(client.UpdateRepository, request), "update")
                params["repository_id"] = current["RepositoryId"]
            else:
                request = models.CreateRepositoryRequest()
                for key, value in target.items():
                    setattr(request, key, value)
                checked(module, module.sdk_call(client.CreateRepository, request), "creation")
            current = find(module, client, models, params)
        module.exit_json(changed=True, **(diff or {}), repository=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
