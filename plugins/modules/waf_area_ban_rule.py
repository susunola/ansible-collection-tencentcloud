#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: waf_area_ban_rule
short_description: Manage Tencent Cloud WAF geographic blocking
version_added: "0.14.0"
description:
  - Reconciles the singleton geographic-blocking rule for a protected WAF domain.
  - C(state=absent) disables the rule because the WAF API does not delete this singleton configuration.
options:
  state: {type: str, choices: [present, absent], default: present, description: Whether geographic blocking is configured and enabled.}
  domain: {type: str, required: true, description: Protected domain.}
  areas: {type: list, elements: dict, default: [], description: SDK-compatible Area entries to block.}
  job_type: {type: str, choices: [TimedJob, CronJob], default: TimedJob, description: Scheduling mode.}
  job_datetime: {type: dict, default: {}, description: SDK-compatible JobDateTime schedule.}
  language: {type: str, choices: [cn, en], default: cn, description: Language used by area names.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.waf_area_ban_rule:
    domain: api.example.com
    areas:
      - {Country: 中国, Region: 广东, City: 深圳}
    job_type: TimedJob
    job_datetime:
      Timed: [{StartDateTime: 1788134400, EndDateTime: 1788220800}]
      TimeTZone: Asia/Shanghai
"""
RETURN = r"""rule: {description: Effective geographic-blocking configuration., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.waf.v20180125 import models, waf_client

    return models, waf_client


def _areas(models, values):
    result = []
    for value in values:
        item = models.Area()
        item._deserialize(value)
        result.append(item)
    return result


def _schedule(models, value):
    item = models.JobDateTime()
    item._deserialize(value)
    return item


def describe_request(models, p):
    request = models.DescribeAreaBanRuleRequest()
    request.Domain = p["domain"]
    return request


def _apply(request, models, p):
    request.Domain, request.Areas = p["domain"], _areas(models, p["areas"])
    request.JobType, request.JobDateTime, request.Lang = p["job_type"], _schedule(models, p["job_datetime"]), p["language"]
    return request


def create_request(models, p):
    return _apply(models.CreateAreaBanRuleRequest(), models, p)


def update_request(models, p):
    return _apply(models.ModifyAreaBanRuleRequest(), models, p)


def status_request(models, p, enabled):
    request = models.ModifyAreaBanStatusRequest()
    request.Domain, request.Status = p["domain"], 1 if enabled else 0
    return request


def _sorted_areas(values):
    return sorted(values or [], key=lambda x: (x.get("Country") or "", x.get("Region") or "", x.get("City") or ""))


def comparable(value):
    return {
        "Status": int(value.get("Status") or 0),
        "Areas": _sorted_areas(value.get("Areas")),
        "JobType": value.get("JobType"),
        "JobDateTime": value.get("JobDateTime") or {},
        "Lang": value.get("Lang") or "cn",
    }


def desired(p):
    return {"Status": 1, "Areas": _sorted_areas(p["areas"]), "JobType": p["job_type"], "JobDateTime": p["job_datetime"], "Lang": p["language"]}


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeAreaBanRule, describe_request(models, p))
    item = response.Data
    return item._serialize(allow_none=True) if item else None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "domain": {"required": True},
            "areas": {"type": "list", "elements": "dict", "default": []},
            "job_type": {"choices": ["TimedJob", "CronJob"], "default": "TimedJob"},
            "job_datetime": {"type": "dict", "default": {}},
            "language": {"choices": ["cn", "en"], "default": "cn"},
        },
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p["areas"]:
        module.fail_json(msg="areas must not be empty when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.WafClient, "waf.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        before = comparable(current) if current else None
        if p["state"] == "absent":
            if not current or before["Status"] == 0:
                module.exit_json(changed=False, rule=current)
            target = dict(before)
            target["Status"] = 0
            diff = maybe_diff(module, before, target)
            if not module.check_mode:
                module.sdk_call(client.ModifyAreaBanStatus, status_request(models, p, False))
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), rule=current)
        target = desired(p)
        if before == target:
            module.exit_json(changed=False, rule=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if current and current.get("Areas"):
                module.sdk_call(client.ModifyAreaBanRule, update_request(models, p))
            else:
                module.sdk_call(client.CreateAreaBanRule, create_request(models, p))
            module.sdk_call(client.ModifyAreaBanStatus, status_request(models, p, True))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), rule=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
