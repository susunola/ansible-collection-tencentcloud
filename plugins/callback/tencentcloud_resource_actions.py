# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Aggregate callback that audits Tencent Cloud API calls made by a play.

Every module in this collection runs its SDK calls through
``TencentCloudModule.sdk_call``, which records each operation (name, request
id, duration, success/failure) and attaches the trail to the module result
as ``tc_api_calls``. This callback collects those trails task by task and
prints a summary table plus a machine-readable JSON list at the end of the
play, giving operators a cost/audit view of what the play actually did
against Tencent Cloud — the same value proposition as the
``amazon.aws.aws_resource_actions`` callback.

Enable it with::

    [defaults]
    callback_plugins = ~/.ansible/plugins/callback
    callbacks_enabled = susunola.tencentcloud.tencentcloud_resource_actions
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
name: tencentcloud_resource_actions
type: aggregate
short_description: summarise Tencent Cloud API calls made during a play
version_added: "0.12.0"
description:
  - Aggregates the C(tc_api_calls) audit trail that every module of this
    collection attaches to its result and prints a per-operation summary
    plus a JSON list at the end of the play.
  - Enabling this callback never changes module behaviour; it only reads
    the C(tc_api_calls) key of task results.
options: {}
extends_documentation_fragment:
  - default_callback
'''

EXAMPLES = r'''
- name: Enable the resource-actions callback for a play
  hosts: all
  gather_facts: false
  tasks:
    - ansible.builtin.debug:
        msg: >-
          Enable the callback by setting callbacks_enabled =
          susunola.tencentcloud.tencentcloud_resource_actions in ansible.cfg
'''

import json

from ansible.plugins.callback import CallbackBase


class CallbackModule(CallbackBase):
    """Aggregate Tencent Cloud API call audit callback."""

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "aggregate"
    CALLBACK_NAME = "susunola.tencentcloud.tencentcloud_resource_actions"

    def __init__(self):
        super(CallbackModule, self).__init__()
        self._calls = []

    def _collect(self, result):
        if result is None:
            return
        calls = result._result.get("tc_api_calls")
        if not calls:
            return
        self._calls.extend(calls)

    def v2_runner_on_ok(self, result):
        self._collect(result)

    def v2_runner_on_failed(self, result, ignore_errors=False):
        self._collect(result)

    def v2_playbook_on_stats(self, stats):
        if not self._calls:
            return
        by_operation = {}
        for call in self._calls:
            entry = by_operation.setdefault(call["operation"], {"count": 0, "duration_ms": 0, "errors": 0})
            entry["count"] += 1
            entry["duration_ms"] += call.get("duration_ms") or 0
            if call.get("status") == "error":
                entry["errors"] += 1
        self._display.banner("TENCENT CLOUD RESOURCE ACTIONS")
        header = ["operation", "calls", "errors", "total ms"]
        rows = []
        for operation, entry in sorted(by_operation.items()):
            rows.append([
                operation,
                str(entry["count"]),
                str(entry["errors"]),
                str(entry["duration_ms"]),
            ])
        widths = [len(h) for h in header]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(cell))
        line = "  " + "  ".join(h.ljust(widths[i]) for i, h in enumerate(header))
        self._display.display(line)
        for row in rows:
            self._display.display(
                "  " + "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
            )
        self._display.display("  " + "-" * (sum(widths) + 6))
        self._display.display(
            "  %d API call(s) across %d operation(s), %d error(s)"
            % (len(self._calls), len(by_operation), sum(e["errors"] for e in by_operation.values()))
        )
        # Machine-readable trail for post-processing.
        self._display.display("TENCENT_CLOUD_API_CALLS_JSON=%s" % json.dumps(self._calls))
