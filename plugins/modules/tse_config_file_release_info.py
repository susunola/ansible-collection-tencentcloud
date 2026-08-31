#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tse_config_file_release_info
short_description: Gather Tencent Cloud TSE configuration release audit data
version_added: "0.14.0"
description: Returns current releases, immutable release versions and publication history for one configuration file.
options:
  instance_id: {type: str, required: true, description: TSE engine instance ID.}
  namespace: {type: str, required: true, description: Configuration namespace.}
  group: {type: str, required: true, description: Configuration group.}
  name: {type: str, required: true, description: Configuration file name.}
  config_file_id: {type: str, description: Configuration file ID used to narrow version and history queries.}
  release_name: {type: str, description: Release name filter.}
  only_in_use: {type: bool, default: false, description: Return only releases currently in use.}
  page_size: {type: int, default: 100, description: Number of releases or history entries requested per call.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.tse_config_file_release_info:
    instance_id: ins-xxxxxxxx
    namespace: production
    group: application
    name: orders.yaml
  register: release_audit
'''
RETURN = r'''
releases: {description: Matching current configuration releases., type: list, elements: dict, returned: always}
versions: {description: Available immutable release versions., type: list, elements: dict, returned: always}
histories: {description: Publication and rollback history entries., type: list, elements: dict, returned: always}
release_count: {description: Release count reported by the API., type: int, returned: always}
history_count: {description: History count reported by the API., type: int, returned: always}
request_ids: {description: Request IDs keyed by query type., type: dict, returned: always}
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client
    return models, tse_client


def release_request(models, params, offset):
    value = models.DescribeConfigFileReleasesRequest()
    value.InstanceId, value.Namespace = params["instance_id"], params["namespace"]
    value.Group, value.FileName = params["group"], params["name"]
    value.ReleaseName, value.OnlyUse = params.get("release_name"), params["only_in_use"]
    value.Offset, value.Limit = offset, params["page_size"]
    return value


def history_request(models, params, offset):
    value = models.DescribeConfigFileReleaseHistoriesRequest()
    value.InstanceId, value.Namespace = params["instance_id"], params["namespace"]
    value.Group, value.Name = params["group"], params["name"]
    value.ConfigFileId = params.get("config_file_id")
    value.Offset, value.Limit = offset, params["page_size"]
    return value


def version_request(models, params):
    value = models.DescribeConfigFileReleaseVersionsRequest()
    value.InstanceId, value.Namespace = params["instance_id"], params["namespace"]
    value.Group, value.FileName = params["group"], params["name"]
    value.ConfigFileId = params.get("config_file_id")
    return value


def fetch_pages(module, operation, request_factory, item_field):
    values, offset, total, request_id = [], 0, None, None
    while total is None or offset < total:
        response = module.sdk_call(operation, request_factory(offset))
        page = getattr(response, item_field, None) or []
        values.extend(item._serialize(allow_none=True) for item in page)
        total, request_id = getattr(response, "TotalCount", None), response.RequestId
        offset += len(page)
        if not page or total is None:
            break
    return values, total if total is not None else len(values), request_id


def run_module():
    module = TencentCloudModule(argument_spec={
        "instance_id": {"required": True}, "namespace": {"required": True},
        "group": {"required": True}, "name": {"required": True},
        "config_file_id": {}, "release_name": {},
        "only_in_use": {"type": "bool", "default": False},
        "page_size": {"type": "int", "default": 100},
    }, supports_check_mode=True)
    params = module.params
    if params["page_size"] < 1 or params["page_size"] > 100:
        module.fail_json(msg="page_size must be between 1 and 100")
    module.require_sdk()
    models, client_module = _load()
    client = module.create_client(client_module.TseClient, "tse.tencentcloudapi.com")
    try:
        releases, release_count, release_request_id = fetch_pages(
            module, client.DescribeConfigFileReleases,
            lambda offset: release_request(models, params, offset), "Releases"
        )
        histories, history_count, history_request_id = fetch_pages(
            module, client.DescribeConfigFileReleaseHistories,
            lambda offset: history_request(models, params, offset), "ConfigFileReleaseHistories"
        )
        version_response = module.sdk_call(
            client.DescribeConfigFileReleaseVersions, version_request(models, params)
        )
        versions = [item._serialize(allow_none=True) for item in (version_response.ReleaseVersions or [])]
        module.exit_json(
            changed=False, releases=releases, versions=versions, histories=histories,
            release_count=release_count, history_count=history_count,
            request_ids={"releases": release_request_id, "versions": version_response.RequestId,
                         "histories": history_request_id},
        )
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
