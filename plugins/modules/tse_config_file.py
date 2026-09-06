#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_config_file
short_description: Manage a Tencent Cloud TSE configuration file
version_added: "0.14.0"
description: Creates, updates and deletes configuration file content and metadata. Publishing is managed separately from draft content.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: TSE engine instance ID.}
  namespace: {type: str, required: true, description: Configuration namespace.}
  group: {type: str, required: true, description: Configuration group.}
  name: {type: str, required: true, description: Configuration file name.}
  content: {type: str, description: Exact draft content.}
  format: {type: str, description: Configuration format.}
  comment: {type: str, description: Configuration description.}
  tags: {type: list, elements: dict, description: SDK configuration tag entries.}
  supported_client: {type: int, description: Supported client type.}
  persistent: {type: dict, description: SDK ConfigFilePersistent payload.}
  encrypted: {type: bool, description: Enable encryption.}
  encrypt_algo: {type: str, description: Encryption algorithm.}
  retries: {type: int, default: 5, description: Transient API retry count.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
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
"""
RETURN = r"""config_file: {description: Effective configuration file metadata and content., type: dict, returned: always}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


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
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
