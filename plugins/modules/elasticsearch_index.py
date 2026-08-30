#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: elasticsearch_index
short_description: Manage indexes in Tencent Cloud Elasticsearch Service
version_added: "0.14.0"
description:
  - Creates, updates and deletes normal or autonomous Elasticsearch indexes through the Tencent Cloud API.
  - Metadata comparison tolerates service-added settings while enforcing every requested mapping and setting.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: Elasticsearch cluster ID.}
  name: {type: str, required: true, description: Index name.}
  index_type: {type: str, choices: [normal, auto], default: normal, description: Normal or autonomous index type.}
  metadata: {type: dict, description: Index mappings and settings. Required when C(state=present).}
  username: {type: str, required: true, description: Cluster access username.}
  password: {type: str, required: true, description: Cluster access password.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.elasticsearch_index:
    instance_id: es-xxxxxxxx
    name: orders
    username: elastic
    password: '{{ vault_elasticsearch_password }}'
    metadata:
      settings:
        number_of_shards: 3
        number_of_replicas: 1
      mappings:
        properties:
          order_id: {type: keyword}
'''
RETURN = r'''index: {description: Elasticsearch index metadata., type: dict, returned: always}'''

import json

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.es.v20180416 import es_client, models
    return models, es_client


def _base(request, p):
    request.InstanceId, request.IndexType, request.IndexName = p["instance_id"], p["index_type"], p["name"]
    request.Username, request.Password = p["username"], p["password"]; return request


def describe_request(models, p): return _base(models.DescribeIndexMetaRequest(), p)


def create_request(models, p):
    request = _base(models.CreateIndexRequest(), p); request.IndexMetaJson = json.dumps(p["metadata"], sort_keys=True, separators=(",", ":")); return request


def update_request(models, p):
    request = _base(models.UpdateIndexRequest(), p); request.UpdateMetaJson = json.dumps(p["metadata"], sort_keys=True, separators=(",", ":")); return request


def delete_request(models, p): return _base(models.DeleteIndexRequest(), p)


def _contains(actual, wanted):
    if isinstance(wanted, dict): return isinstance(actual, dict) and all(key in actual and _contains(actual[key], value) for key, value in wanted.items())
    if isinstance(wanted, list): return actual == wanted
    return actual == wanted or str(actual) == str(wanted)


def find(module, client, models, p):
    try:
        response = module.sdk_call(client.DescribeIndexMeta, describe_request(models, p)); item = response.IndexMetaField
    except Exception as exc:
        code = str(getattr(exc, "get_code", lambda: "")() or exc).lower()
        if "notfound" in code or "not found" in code: return None
        raise
    if not item or item.IndexName != p["name"]: return None
    value = item._serialize(allow_none=True)
    try: value["Metadata"] = json.loads(value.get("IndexMetaJson") or "{}")
    except (TypeError, ValueError): value["Metadata"] = value.get("IndexMetaJson")
    return value


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True}, "name": {"required": True}, "index_type": {"choices": ["normal", "auto"], "default": "normal"}, "metadata": {"type": "dict"}, "username": {"required": True}, "password": {"required": True, "no_log": True}}, required_if=[("state", "present", ("metadata",))], supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.EsClient, "es.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, index=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeleteIndex, delete_request(models, p))
            module.exit_json(changed=True, **(diff or {}), index=current if module.check_mode else None)
        if current and _contains(current.get("Metadata"), p["metadata"]): module.exit_json(changed=False, index=current)
        before = current.get("Metadata") if current else None; diff = maybe_diff(module, before, p["metadata"])
        if not module.check_mode:
            module.sdk_call(client.UpdateIndex if current else client.CreateIndex, update_request(models, p) if current else create_request(models, p)); current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), index=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
