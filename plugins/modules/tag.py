#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tag
short_description: Manage tags on arbitrary Tencent Cloud resources
version_added: "0.12.0"
description:
  - Attach, update and detach a single tag key on any QCS resource through
    the C(tag.v20180813) API.
  - This module is idempotent. Running it twice leaves the resource tags
    unchanged and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
  - Unlike the per-resource C(tags) option of modules such as
    M(susunola.tencentcloud.cvm_instance), this module addresses resources
    of any service type through the generic tag service, so it can manage
    tags on resources that have no dedicated module.
options:
  state:
    description:
      - C(present) attaches O(tag_key)=O(tag_value) to every resource in
        O(resource_ids); resources carrying the key with a different value
        are updated in place.
      - C(absent) detaches O(tag_key) from every resource in O(resource_ids).
    type: str
    choices: [present, absent]
    default: present
  tag_key:
    description:
      - Tag key to manage, written to V(AttachResourcesTagRequest.TagKey).
    type: str
    required: true
  tag_value:
    description:
      - Tag value to assign, written to V(AttachResourcesTagRequest.TagValue).
      - Required when O(state=present).
    type: str
  service_type:
    description:
      - Business type of the resources, e.g. C(cvm), C(clb), C(ckafka);
        the third segment of the resource qcs identifier, written to
        V(AttachResourcesTagRequest.ServiceType).
    type: str
    required: true
  resource_prefix:
    description:
      - Resource prefix of the resources, e.g. C(instance) for CVM; the
        sixth segment of the resource qcs identifier, written to
        V(AttachResourcesTagRequest.ResourcePrefix).
    type: str
    required: true
  resource_ids:
    description:
      - IDs of the resources to tag, e.g. C(ins-xxxxxxxx), written to
        V(AttachResourcesTagRequest.ResourceIds).
    type: list
    elements: str
    required: true
  resource_region:
    description:
      - Region of the resources, e.g. C(ap-guangzhou), written to
        V(AttachResourcesTagRequest.ResourceRegion).
      - Defaults to the module O(region) when not given.
    type: str
  retries:
    description: Number of retries for transient SDK failures.
    type: int
    default: 5
  waiter_delay:
    description: Seconds to wait between state-polling attempts.
    type: int
    default: 5
  waiter_timeout:
    description: Overall timeout in seconds for state polling.
    type: int
    default: 120
  user_agent:
    description:
      - Value appended to the SDK User-Agent header so API usage can be
        attributed to this collection.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-tag) package on the controller.
  - Tag changes on some services propagate asynchronously; the module does
    not wait for downstream resource APIs to reflect the change.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Tag two CVM instances with env=prod
  susunola.tencentcloud.tag:
    region: ap-guangzhou
    state: present
    tag_key: env
    tag_value: prod
    service_type: cvm
    resource_prefix: instance
    resource_ids:
      - ins-aaaaaaaa
      - ins-bbbbbbbb

- name: Update the value on one of them
  susunola.tencentcloud.tag:
    region: ap-guangzhou
    state: present
    tag_key: env
    tag_value: staging
    service_type: cvm
    resource_prefix: instance
    resource_ids:
      - ins-aaaaaaaa

- name: Remove the tag
  susunola.tencentcloud.tag:
    region: ap-guangzhou
    state: absent
    tag_key: env
    service_type: cvm
    resource_prefix: instance
    resource_ids:
      - ins-aaaaaaaa
      - ins-bbbbbbbb
'''

RETURN = r'''
resource_ids:
  description: Resources the module acted on, as a dict of
    resource_id to action taken (attached, updated, detached, ok).
  returned: success
  type: dict
  sample:
    ins-aaaaaaaa: attached
    ins-bbbbbbbb: ok
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tagging import tags_from_sdk


def _load_tag():
    from tencentcloud.tag.v20180813 import models, tag_client
    return models, tag_client


def build_describe_request(models, tag_key, tag_value, service_type, resource_prefix, resource_region):
    request = models.DescribeResourcesByTagsRequest()
    tag_filter = models.TagFilter()
    tag_filter.TagKey = tag_key
    if tag_value is not None:
        tag_filter.TagValue = [tag_value]
    request.TagFilters = [tag_filter]
    request.ServiceType = service_type
    request.ResourcePrefix = resource_prefix
    if resource_region:
        request.ResourceRegion = resource_region
    request.Limit = 100
    return request


def find_resources(module, client, models, tag_key, tag_value, service_type, resource_prefix, resource_region):
    """Return {resource_id: value} for resources carrying tag_key.

    When tag_value is given only exact matches are returned; otherwise any
    resource carrying the key is returned. Failures (e.g. an unsupported
    key-only filter) surface as an empty dict so callers degrade to attach.
    """
    request = build_describe_request(models, tag_key, tag_value, service_type, resource_prefix, resource_region)
    try:
        response = module.sdk_call(client.DescribeResourcesByTags, request)
    except Exception:
        return {}
    result = {}
    for item in response.ResourceTags or []:
        tags = tags_from_sdk(item.Tags or [])
        if tag_key in tags:
            result[item.ResourceId] = tags[tag_key]
    return result


def _attach(module, client, models, tag_key, tag_value, service_type, resource_prefix, resource_region, resource_ids):
    request = models.AttachResourcesTagRequest()
    request.ServiceType = service_type
    request.ResourcePrefix = resource_prefix
    request.ResourceIds = resource_ids
    request.TagKey = tag_key
    request.TagValue = tag_value
    if resource_region:
        request.ResourceRegion = resource_region
    module.sdk_call(client.AttachResourcesTag, request)


def _update_value(module, client, models, tag_key, tag_value, service_type, resource_prefix, resource_region, resource_ids):
    request = models.ModifyResourcesTagValueRequest()
    request.ServiceType = service_type
    request.ResourcePrefix = resource_prefix
    request.ResourceIds = resource_ids
    request.TagKey = tag_key
    request.TagValue = tag_value
    if resource_region:
        request.ResourceRegion = resource_region
    module.sdk_call(client.ModifyResourcesTagValue, request)


def _detach(module, client, models, tag_key, service_type, resource_prefix, resource_region, resource_ids):
    request = models.DetachResourcesTagRequest()
    request.ServiceType = service_type
    request.ResourcePrefix = resource_prefix
    request.ResourceIds = resource_ids
    request.TagKey = tag_key
    if resource_region:
        request.ResourceRegion = resource_region
    module.sdk_call(client.DetachResourcesTag, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "tag_key": {"type": "str", "required": True, "no_log": False},
            "tag_value": {"type": "str"},
            "service_type": {"type": "str", "required": True},
            "resource_prefix": {"type": "str", "required": True},
            "resource_ids": {"type": "list", "elements": "str", "required": True},
            "resource_region": {"type": "str"},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    tag_key = module.params["tag_key"]
    tag_value = module.params["tag_value"]
    service_type = module.params["service_type"]
    resource_prefix = module.params["resource_prefix"]
    resource_ids = list(module.params["resource_ids"])
    resource_region = module.params["resource_region"] or module.params.get("region")

    models, tag_client = _load_tag()
    client = module.create_client(tag_client.TagClient, "tag.tencentcloudapi.com")

    if state == "present" and tag_value is None:
        module.fail_json(msg="tag_value is required when state=present")

    exact = find_resources(
        module, client, models, tag_key, tag_value,
        service_type, resource_prefix, resource_region,
    )
    key_only = find_resources(
        module, client, models, tag_key, None,
        service_type, resource_prefix, resource_region,
    )

    if state == "absent":
        to_detach = [rid for rid in resource_ids if rid in key_only]
        if not to_detach:
            module.exit_json(changed=False, resource_ids={rid: "ok" for rid in resource_ids}, msg="Tag already absent")
        if module.check_mode:
            module.exit_json(changed=True, resource_ids={rid: "would_detach" for rid in to_detach}, msg="Would detach tag")
        _detach(module, client, models, tag_key, service_type, resource_prefix, resource_region, to_detach)
        result = {rid: ("detached" if rid in to_detach else "ok") for rid in resource_ids}
        module.exit_json(changed=True, resource_ids=result, msg="Tag detached")

    # state == present
    to_attach = [rid for rid in resource_ids if rid not in exact and rid not in key_only]
    to_update = [rid for rid in resource_ids if rid in key_only and rid not in exact]

    if not to_attach and not to_update:
        module.exit_json(changed=False, resource_ids={rid: "ok" for rid in resource_ids}, msg="Tag is up to date")

    if module.check_mode:
        result = {rid: "would_attach" for rid in to_attach}
        result.update({rid: "would_update" for rid in to_update})
        result.update({rid: "ok" for rid in resource_ids if rid not in result})
        module.exit_json(changed=True, resource_ids=result, msg="Would tag resources")

    if to_attach:
        _attach(module, client, models, tag_key, tag_value, service_type, resource_prefix, resource_region, to_attach)
    if to_update:
        _update_value(module, client, models, tag_key, tag_value, service_type, resource_prefix, resource_region, to_update)

    result = {rid: "ok" for rid in resource_ids}
    for rid in to_attach:
        result[rid] = "attached"
    for rid in to_update:
        result[rid] = "updated"
    module.exit_json(changed=True, resource_ids=result, msg="Tag reconciled")


def main():
    run_module()


if __name__ == "__main__":
    main()
