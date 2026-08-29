#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r'''
---
module: monitor_alarm_policy_notice
short_description: Manage notification bindings for a Cloud Monitor alarm policy
version_added: "0.13.0"
description: Reconciles notification rules, hierarchical notices and content templates independently from alarm conditions.
options:
  policy_id: {description: Alarm policy ID., type: str, required: true}
  module: {description: API module selector., type: str, default: monitor}
  notice_ids: {description: Exact notification rule ID set., type: list, elements: str, default: []}
  hierarchical_notices: {description: Hierarchical notification bindings in Tencent Cloud API shape., type: list, elements: raw, default: []}
  notice_content_template_bindings: {description: Notification content-template bindings in Tencent Cloud API shape., type: list, elements: raw, default: []}
  retries: {description: Number of retries for transient SDK failures., type: int, default: 5}
  waiter_delay: {description: Seconds between state-polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall timeout in seconds for state polling., type: int, default: 120}
  user_agent: {description: User-Agent value appended to SDK requests., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.monitor_alarm_policy_notice:
    policy_id: policy-abc123
    notice_ids: [notice-abc123]
'''
RETURN = r'''
notice:
  description: Effective notification binding configuration.
  type: dict
  returned: always
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.monitor import (
    _contains,
    _load_monitor,
    build_notice_request,
    find_policy,
)


def _view(policy):
    return {
        "notice_ids": sorted(policy.get("NoticeIds") or []),
        "hierarchical_notices": policy.get("HierarchicalNotices") or [],
        "notice_content_template_bindings": policy.get("NoticeContentTmplBindInfos") or [],
    }


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "policy_id": {"type": "str", "required": True},
            "module": {"type": "str", "default": "monitor"},
            "notice_ids": {"type": "list", "elements": "str", "default": []},
            "hierarchical_notices": {"type": "list", "elements": "raw", "default": []},
            "notice_content_template_bindings": {"type": "list", "elements": "raw", "default": []},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, monitor_client = _load_monitor()
    client = module.create_client(monitor_client.MonitorClient, "monitor.tencentcloudapi.com")
    try:
        policy = find_policy(module, client, models, p["policy_id"], None, p["module"])
        if policy is None:
            module.fail_json(msg="Alarm policy was not found", policy_id=p["policy_id"])
        current = _view(policy)
        desired = {
            "notice_ids": sorted(p["notice_ids"]),
            "hierarchical_notices": p["hierarchical_notices"],
            "notice_content_template_bindings": p["notice_content_template_bindings"],
        }
        changed = (
            current["notice_ids"] != desired["notice_ids"]
            or not _contains(current["hierarchical_notices"], desired["hierarchical_notices"])
            or not _contains(current["notice_content_template_bindings"], desired["notice_content_template_bindings"])
        )
        if not changed:
            module.exit_json(changed=False, notice=current, msg="Alarm policy notices are up to date")
        diff = maybe_diff(module, current, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), notice=current, msg="Would update alarm policy notices")
        module.sdk_call(client.ModifyAlarmPolicyNotice, build_notice_request(models, p, p["policy_id"]))
        policy = find_policy(module, client, models, p["policy_id"], None, p["module"])
        module.exit_json(changed=True, **(diff or {}), notice=_view(policy), msg="Alarm policy notices updated")
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )


def main():
    run_module()


if __name__ == "__main__":
    main()
