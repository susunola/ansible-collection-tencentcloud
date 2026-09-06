#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tem_application_deployment
short_description: Deploy Tencent Cloud TEM application versions
version_added: "0.14.0"
description: Declaratively deploys a named application version and skips deployment when the active configuration already contains the requested values.
options:
  application_id: {type: str, required: true, description: TEM application ID.}
  environment_id: {type: str, required: true, description: TEM environment ID.}
  deploy_version: {type: str, required: true, description: Desired deployment version name.}
  configuration: {type: dict, required: true, description: SDK DeployApplicationRequest fields using their original field names.}
  source_channel: {type: int, default: 0, description: TEM source channel.}
  force_redeploy: {type: bool, default: false, description: Redeploy even when the active version and configuration already match.}
  wait: {type: bool, default: true, description: Wait until the requested version is active and no deployment remains in progress.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 1800, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tem_application_deployment:
    application_id: app-xxxxxxxx
    environment_id: en-xxxxxxxx
    deploy_version: v2026.08.30
    configuration:
      InitPodNum: 2
      CpuSpec: 1
      MemorySpec: 2
      DeployMode: IMAGE
      ImgRepo: ccr.ccs.tencentyun.com/example/order:v2026.08.30
      SecurityGroupIds: [sg-xxxxxxxx]
"""
RETURN = r"""
deployment:
  description: Effective TEM service version metadata.
  type: dict
  returned: always
version_id:
  description: Version ID returned by deployment.
  type: str
  returned: changed
"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_task


def _load():
    from tencentcloud.tem.v20210701 import models, tem_client

    return models, tem_client


def describe_request(models, p):
    r = models.DescribeApplicationInfoRequest()
    r.ApplicationId, r.EnvironmentId, r.SourceChannel = p["application_id"], p["environment_id"], p["source_channel"]
    return r


def deploy_request(models, p):
    value = dict(p["configuration"])
    value["ApplicationId"], value["EnvironmentId"], value["DeployVersion"], value["SourceChannel"] = (
        p["application_id"],
        p["environment_id"],
        p["deploy_version"],
        p["source_channel"],
    )
    r = models.DeployApplicationRequest()
    r.from_json_string(json.dumps(value))
    return r


def describe(module, client, models, p):
    result = module.sdk_call(client.DescribeApplicationInfo, describe_request(models, p)).Result
    return result._serialize(allow_none=True) if result else None


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and contains(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(contains(a, e) for a, e in zip(actual, expected))
    return actual == expected


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "application_id": {"required": True},
            "environment_id": {"required": True},
            "deploy_version": {"required": True},
            "configuration": {"type": "dict", "required": True},
            "source_channel": {"type": "int", "default": 0},
            "force_redeploy": {"type": "bool", "default": False},
            "wait": {"type": "bool", "default": True},
            "waiter_timeout": {"type": "int", "default": 1800},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TemClient, "tem.tencentcloudapi.com")
    try:
        reserved = set(p["configuration"]) & {"ApplicationId", "EnvironmentId", "DeployVersion", "SourceChannel"}
        if reserved:
            module.fail_json(msg="configuration must not override deployment identity fields", fields=sorted(reserved))
        current = describe(module, client, models, p)
        target = dict(p["configuration"])
        target["DeployVersion"] = p["deploy_version"]
        version = (current or {}).get("DeployVersion") or (current or {}).get("VersionName")
        config_match = contains(current or {}, p["configuration"])
        if not p["force_redeploy"] and version == p["deploy_version"] and config_match:
            module.exit_json(changed=False, deployment=current, version_id=(current or {}).get("VersionId"))
        diff = maybe_diff(module, current, target)
        version_id = None
        if not module.check_mode:
            version_id = module.sdk_call(client.DeployApplication, deploy_request(models, p)).Result
            if p["wait"]:

                def poll():
                    value = describe(module, client, models, p) or {}
                    active = value.get("DeployVersion") or value.get("VersionName")
                    return ("SUCCESS" if active == p["deploy_version"] and not value.get("UnderDeploying") else "RUNNING", None, value)

                current = wait_for_task(module, poll, timeout=p["waiter_timeout"], delay=p["waiter_delay"], success_statuses=("SUCCESS",), failure_statuses=())
            else:
                current = describe(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), deployment=current if not module.check_mode else target, version_id=version_id)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
