#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: monitor_prometheus_scrape_job
short_description: Manage Tencent Cloud Managed Prometheus scrape jobs
version_added: "0.14.0"
description: Creates, updates and deletes a scrape job attached to a Prometheus agent.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, required: true, description: Prometheus instance ID.}
  agent_id: {type: str, required: true, description: Prometheus agent ID.}
  job_id: {type: str, description: Existing scrape-job ID.}
  name: {type: str, description: Scrape job name used for discovery.}
  config: {type: str, description: Complete Prometheus scrape configuration.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.monitor_prometheus_scrape_job:
    instance_id: prom-xxxxxxxx
    agent_id: agent-xxxxxxxx
    name: application
    config: |-
      job_name: application
      static_configs:
        - targets: ['10.0.0.8:9100']
'''
RETURN = r'''scrape_job: {description: Prometheus scrape-job metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.monitor.v20180724 import models, monitor_client
    return models, monitor_client
def build_describe(models, p): request = models.DescribePrometheusScrapeJobsRequest(); request.InstanceId, request.AgentId, request.Name, request.JobIds, request.Offset, request.Limit = p["instance_id"], p["agent_id"], p.get("name"), [p["job_id"]] if p.get("job_id") else None, 0, 100; return request
def build_create(models, p): request = models.CreatePrometheusScrapeJobRequest(); request.InstanceId, request.AgentId, request.Config = p["instance_id"], p["agent_id"], p["config"]; return request
def build_update(models, p, job_id): request = models.UpdatePrometheusScrapeJobRequest(); request.InstanceId, request.AgentId, request.JobId, request.Config = p["instance_id"], p["agent_id"], job_id, p["config"]; return request
def build_delete(models, p, job_id): request = models.DeletePrometheusScrapeJobsRequest(); request.InstanceId, request.AgentId, request.JobIds = p["instance_id"], p["agent_id"], [job_id]; return request


def find(module, client, models, p):
    response = module.sdk_call(client.DescribePrometheusScrapeJobs, build_describe(models, p)); matches = []
    for item in list(response.ScrapeJobSet or []):
        value = item._serialize(allow_none=True)
        if (p.get("job_id") and value.get("JobId") == p["job_id"]) or (not p.get("job_id") and value.get("Name") == p.get("name")): matches.append(value)
    if len(matches) > 1: module.fail_json(msg="Multiple Prometheus scrape jobs have the requested name", name=p.get("name"))
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "instance_id": {"required": True}, "agent_id": {"required": True}, "job_id": {}, "name": {}, "config": {}}, required_one_of=[("job_id", "name")], required_if=[("state", "present", ["config"])], supports_check_mode=True)
    p = module.params; module.require_sdk(); models, cm = _load(); client = module.create_client(cm.MonitorClient, "monitor.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, scrape_job=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode: module.sdk_call(client.DeletePrometheusScrapeJobs, build_delete(models, p, current["JobId"]))
            module.exit_json(changed=True, **(diff or {}), scrape_job=current if module.check_mode else None)
        target = {"Name": p.get("name"), "Config": p["config"]}; before = {"Name": current.get("Name"), "Config": current.get("Config")} if current else None
        if before == target: module.exit_json(changed=False, scrape_job=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current: module.sdk_call(client.UpdatePrometheusScrapeJob, build_update(models, p, current["JobId"])); p["job_id"] = current["JobId"]
            else: p["job_id"] = module.sdk_call(client.CreatePrometheusScrapeJob, build_create(models, p)).JobId
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), scrape_job=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
