#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tke_cls_log_config
short_description: Create or delete a TKE cluster CLS log configuration
version_added: "1.1.0"
description:
  - Creates or deletes a CLS log collection configuration for a Tencent Cloud
    TKE cluster. The configuration is the raw TKE log-config object, passed
    through as JSON to the API.
  - The module is idempotent on I(log_config_name) within a cluster; it reads
    the existing configurations via DescribeLogConfigs before changing anything.
    When a configuration with the same name already exists and I(state=present),
    the module is a no-op (the collection does not reconcile the raw JSON
    payload in place - delete and recreate to change it).
options:
  state:
    description: Desired state of the log configuration.
    type: str
    choices: [present, absent]
    default: present
  cluster_id:
    description: ID of the TKE cluster the log configuration targets.
    type: str
    required: true
  cluster_type:
    description: Type of the cluster the log configuration targets.
    type: str
    default: tke
  log_config_name:
    description: Name of the log configuration, used for idempotency and deletion.
    type: str
    required: true
  log_config:
    description: >-
      Raw TKE log configuration object, passed through as JSON to the API.
      Required when I(state=present).
    type: dict
  logset_id:
    description: CLS logset ID the configuration is bound to. Required when I(state=present).
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
- name: Configure CLS log collection for a cluster
  susunola.tencentcloud.tke_cls_log_config:
    cluster_id: cls-xxxxxxxx
    log_config_name: container-stdout
    logset_id: xxxxxx-xx-xx-xx-xxxxxxxx
    log_config:
      name: container-stdout
      logType: container_stdout
      clsDetail:
        region: ap-guangzhou

- name: Remove a log configuration
  susunola.tencentcloud.tke_cls_log_config:
    cluster_id: cls-xxxxxxxx
    log_config_name: container-stdout
    state: absent
'''

RETURN = r'''
cluster_id:
  description: Cluster ID the operation targeted.
  returned: always
  type: str
log_config_name:
  description: Log configuration name the operation targeted.
  returned: always
  type: str
exists:
  description: Whether the log configuration exists after the operation.
  returned: always
  type: bool
'''

import json

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def _load_tke():
    from tencentcloud.tke.v20180525 import tke_client, models
    return models, tke_client


def _find_config(log_configs, name):
    """Return the parsed config dict whose ``name`` matches, or None.

    ``log_configs`` is the raw JSON string returned by DescribeLogConfigs; it is
    parsed defensively so a malformed or empty payload is treated as absent.
    """
    if not log_configs:
        return None
    try:
        data = json.loads(log_configs)
    except (ValueError, TypeError):
        return None
    items = data if isinstance(data, list) else [data]
    for item in items:
        if isinstance(item, dict) and item.get("name") == name:
            return item
    return None


def describe_state(module, client, models, cluster_id, cluster_type, name):
    request = models.DescribeLogConfigsRequest()
    request.ClusterId = cluster_id
    request.ClusterType = cluster_type
    response = module.sdk_call(client.DescribeLogConfigs, request)
    return _find_config(getattr(response, "LogConfigs", None), name)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "cluster_id": {"type": "str", "required": True},
            "cluster_type": {"type": "str", "default": "tke"},
            "log_config_name": {"type": "str", "required": True},
            "log_config": {"type": "dict"},
            "logset_id": {"type": "str"},
        },
        required_if=[
            ("state", "present", ("log_config", "logset_id")),
        ],
        supports_check_mode=True,
    )
    p = module.params
    cluster_id = p["cluster_id"]
    cluster_type = p["cluster_type"]
    name = p["log_config_name"]
    desired_present = p["state"] == "present"
    module.require_sdk()
    models, client_module = _load_tke()
    client = module.create_client(client_module.TkeClient, "tke.tencentcloudapi.com")
    try:
        current = describe_state(module, client, models, cluster_id, cluster_type, name)
        if bool(current) == desired_present:
            module.exit_json(
                changed=False,
                cluster_id=cluster_id,
                log_config_name=name,
                exists=bool(current),
                msg="Log configuration %s/%s already %s" % (cluster_id, name, "present" if desired_present else "absent"),
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                cluster_id=cluster_id,
                log_config_name=name,
                exists=desired_present,
                msg="Would %s log configuration %s/%s" % ("create" if desired_present else "delete", cluster_id, name),
            )
        if desired_present:
            request = models.CreateCLSLogConfigRequest()
            request.ClusterId = cluster_id
            request.ClusterType = cluster_type
            request.LogsetId = p["logset_id"]
            request.LogConfig = json.dumps(p["log_config"])
            module.sdk_call(client.CreateCLSLogConfig, request)
        else:
            request = models.DeleteLogConfigsRequest()
            request.ClusterId = cluster_id
            request.ClusterType = cluster_type
            request.LogConfigNames = [name]
            module.sdk_call(client.DeleteLogConfigs, request)
        final = describe_state(module, client, models, cluster_id, cluster_type, name)
        module.exit_json(
            changed=True,
            cluster_id=cluster_id,
            log_config_name=name,
            exists=bool(final),
            msg="Log configuration %s/%s %s" % (cluster_id, name, "created" if desired_present else "deleted"),
        )
    except Exception as exc:
        module.fail_sdk_error(exc, "Tencent Cloud TKE CLS log config request failed")


def main():
    run_module()


if __name__ == "__main__":
    main()
