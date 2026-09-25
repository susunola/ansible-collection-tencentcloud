#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_config_file
short_description: Manage a Tencent Cloud TSE configuration file
version_added: "0.14.0"
description: Creates, updates and deletes configuration file content and metadata. Publishing is managed separately from draft content.
options:
  state:
    description:
      - Desired state.
    type: str
    choices: [present, absent]
    default: present
  instance_id:
    description:
      - TSE engine instance ID.
    type: str
    required: true
  namespace:
    description:
      - Configuration namespace.
    type: str
    required: true
  group:
    description:
      - Configuration group.
    type: str
    required: true
  name:
    description:
      - Configuration file name.
    type: str
    required: true
  content:
    description:
      - Exact draft content.
    type: str
  format:
    description:
      - Configuration format.
    type: str
  comment:
    description:
      - Configuration description.
    type: str
  tags:
    description:
      - SDK configuration tag entries.
    type: list
    elements: dict
  supported_client:
    description:
      - Supported client type.
    type: int
  persistent:
    description:
      - SDK ConfigFilePersistent payload.
    type: dict
  encrypted:
    description:
      - Enable encryption.
    type: bool
  encrypt_algo:
    description:
      - Encryption algorithm.
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
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_config_file:
    instance_id: ins-xxxxxxxx
    namespace: production
    group: application
    name: orders.yaml
    format: YAML
    content: "server:\n  port: 8080\n"

- name: Delete the config file
  susunola.tencentcloud.tse_config_file:
    state: absent
    group: application
    instance_id: ins-xxxxxxxx
    name: orders.yaml
    namespace: production
"""
RETURN = r"""config_file:
  description:
    - Effective configuration file metadata and content.
  returned: always
  type: dict
  sample:
    # shape captured from this module's unit tests -- scripts/add_return_samples.py
    Name: orders.yaml
    Namespace: production
    Group: application
    Content: "server:\n  port: 8080\n"
    Format: YAML
    Comment: order config
    Id: cf-new
"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import fail_from_sdk_error


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def describe_request(models, p):
    r = models.DescribeConfigFileRequest()
    r.InstanceId, r.Namespace, r.Group, r.Name = p["instance_id"], p["namespace"], p["group"], p["name"]
    return r


def _model(models, value):
    x = models.ConfigFile()
    x.from_json_string(json.dumps(value))
    return x


def request(cls, models, p, value):
    r = cls()
    r.InstanceId = p["instance_id"]
    r.ConfigFile = _model(models, value)
    return r


def delete_request(models, p, current):
    r = models.DeleteConfigFilesRequest()
    r.InstanceId, r.Namespace, r.Group, r.Name, r.Id = p["instance_id"], p["namespace"], p["group"], p["name"], current.get("Id")
    return r


def find(module, client, models, p):
    value = module.sdk_call(client.DescribeConfigFile, describe_request(models, p)).ConfigFile
    return value._serialize(allow_none=True) if value else None


def desired(p):
    mapping = {
        "content": "Content",
        "format": "Format",
        "comment": "Comment",
        "tags": "Tags",
        "supported_client": "ConfigFileSupportedClient",
        "persistent": "ConfigFilePersistent",
        "encrypted": "Encrypted",
        "encrypt_algo": "EncryptAlgo",
    }
    value = {"Name": p["name"], "Namespace": p["namespace"], "Group": p["group"]}
    for source, target in mapping.items():
        if p.get(source) is not None:
            value[target] = p[source]
    return value


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and contains(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return actual == expected
    return actual == expected


def writable(value):
    keys = (
        "Name",
        "Namespace",
        "Group",
        "Content",
        "Format",
        "Comment",
        "Tags",
        "ConfigFileSupportedClient",
        "ConfigFilePersistent",
        "Encrypted",
        "EncryptAlgo",
    )
    return {key: value.get(key) for key in keys if key in value}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "instance_id": {"required": True},
            "namespace": {"required": True},
            "group": {"required": True},
            "name": {"required": True},
            "content": {},
            "format": {},
            "comment": {},
            "tags": {"type": "list", "elements": "dict"},
            "supported_client": {"type": "int"},
            "persistent": {"type": "dict"},
            "encrypted": {"type": "bool"},
            "encrypt_algo": {},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, config_file=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteConfigFiles, delete_request(models, p, current))
            module.exit_json(changed=True, **(diff or {}), config_file=None)
        target = desired(p)
        if not current:
            missing = [key for key in ("content", "format") if p.get(key) is None]
            if missing:
                module.fail_json(msg="content and format are required for a new TSE configuration file", missing=missing)
        if current and contains(current, target):
            module.exit_json(changed=False, config_file=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            payload = writable(dict(current or {}, **target))
            api = client.ModifyConfigFiles if current else client.CreateConfigFile
            cls = models.ModifyConfigFilesRequest if current else models.CreateConfigFileRequest
            module.sdk_call(api, request(cls, models, p, payload))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), config_file=current if not module.check_mode else target)
    except Exception as exc:
        fail_from_sdk_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
