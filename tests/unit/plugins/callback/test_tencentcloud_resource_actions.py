# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for the tencentcloud_resource_actions aggregate callback."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json

import pytest

from ansible_collections.susunola.tencentcloud.plugins.callback.tencentcloud_resource_actions import (
    CallbackModule,
)


class _Result(object):
    def __init__(self, payload):
        self._result = payload


class _Display(object):
    def __init__(self):
        self.lines = []

    def banner(self, text):
        self.lines.append(("banner", text))

    def display(self, text):
        self.lines.append(("display", text))


@pytest.fixture()
def callback():
    cb = CallbackModule()
    cb._display = _Display()
    return cb


def _sample_call(operation, count=1, errors=0, duration=12):
    return {
        "operation": operation,
        "request_id": "req-1",
        "duration_ms": duration,
        "status": "error" if errors else "ok",
        "error": "x" if errors else None,
    }


def test_collects_trails_from_ok_and_failed_tasks(callback):
    callback.v2_runner_on_ok(_Result({"tc_api_calls": [_sample_call("DescribeVpcs")]}))
    callback.v2_runner_on_failed(_Result({"tc_api_calls": [_sample_call("CreateVpc", errors=1)]}))
    assert len(callback._calls) == 2
    assert [c["operation"] for c in callback._calls] == ["DescribeVpcs", "CreateVpc"]


def test_ignores_results_without_trail(callback):
    callback.v2_runner_on_ok(_Result({"changed": True}))
    assert callback._calls == []


def test_stats_prints_summary_and_json(callback):
    callback._calls = [
        _sample_call("DescribeVpcs"),
        _sample_call("DescribeVpcs"),
        _sample_call("CreateVpc", duration=200),
        _sample_call("CreateVpc", errors=1, duration=50),
    ]
    callback.v2_playbook_on_stats(None)
    text = "\n".join(line for kind, line in callback._display.lines)
    assert "DescribeVpcs" in text
    assert "CreateVpc" in text
    assert "4 API call(s) across 2 operation(s), 1 error(s)" in text
    # JSON trail line must parse and carry every recorded call.
    json_line = [line for kind, line in callback._display.lines
                 if line.startswith("TENCENT_CLOUD_API_CALLS_JSON=")]
    assert len(json_line) == 1
    parsed = json.loads(json_line[0].split("=", 1)[1])
    assert len(parsed) == 4


def test_stats_noop_without_calls(callback):
    callback.v2_playbook_on_stats(None)
    assert callback._display.lines == []
