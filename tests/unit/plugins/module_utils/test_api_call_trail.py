# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for the API-call audit trail wired into TencentCloudModule.

The trail (``tc_api_calls``) powers the
``tencentcloud_resource_actions`` callback; these tests pin the recording
behaviour at the module_utils layer without the SDK.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule

from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    module_args,
    AnsibleExitJson,
    AnsibleFailJson,
)


class _FakeResponse(object):
    def __init__(self, request_id="req-123"):
        self.RequestId = request_id


class _FakeError(Exception):
    def get_request_id(self):
        return "req-err"


def _make_module(**extra):
    module_args(**extra)
    return TencentCloudModule(argument_spec={"probe": {"type": "str"}}, supports_check_mode=True)


def _ok_response():
    return _FakeResponse()


def test_sdk_call_records_success():
    module = _make_module()
    calls = []
    module.sdk_call(
        lambda req: calls.append(req) or _FakeResponse(),
        request="payload",
    )
    assert len(module._tc_calls) == 1
    record = module._tc_calls[0]
    assert record["operation"].endswith("<lambda>") or record["operation"] == "<lambda>"
    assert record["request_id"] == "req-123"
    assert record["status"] == "ok"
    assert record["error"] is None
    assert record["duration_ms"] >= 0
    assert calls == ["payload"]


def test_sdk_call_records_error_then_reraises():
    module = _make_module()

    def boom(request):
        raise _FakeError("nope")

    with pytest.raises(_FakeError):
        module.sdk_call(boom, request="payload", retry=False)
    assert len(module._tc_calls) == 1
    record = module._tc_calls[0]
    assert record["status"] == "error"
    assert record["request_id"] == "req-err"
    assert "nope" in record["error"]


def test_exit_json_attaches_trail():
    module = _make_module()
    module.sdk_call(_ok_response, retry=False)
    module.sdk_call(lambda: _FakeResponse(request_id="req-2"), retry=False)
    # Directly exercise exit_json through the harness style.
    from unittest.mock import patch
    from ansible.module_utils import basic
    result = {}

    def _exit(self, **kwargs):
        result.update(kwargs)
        raise AnsibleExitJson(kwargs)

    with patch.object(basic.AnsibleModule, "exit_json", _exit):
        try:
            module.exit_json(changed=False)
        except AnsibleExitJson:
            pass
    assert "tc_api_calls" in result
    assert len(result["tc_api_calls"]) == 2


def test_fail_json_attaches_trail():
    module = _make_module()
    module.sdk_call(_ok_response, retry=False)
    from unittest.mock import patch
    from ansible.module_utils import basic

    def _fail(self, *args, **kwargs):
        raise AnsibleFailJson(kwargs)

    with patch.object(basic.AnsibleModule, "fail_json", _fail):
        with pytest.raises(AnsibleFailJson) as exc_info:
            module.fail_json(msg="boom")
    payload = exc_info.value.args[0]
    assert payload["tc_api_calls"][0]["status"] == "ok"


def test_no_calls_means_no_trail_key():
    module = _make_module()
    from unittest.mock import patch
    from ansible.module_utils import basic
    result = {}

    def _exit(self, **kwargs):
        result.update(kwargs)
        raise AnsibleExitJson(kwargs)

    with patch.object(basic.AnsibleModule, "exit_json", _exit):
        try:
            module.exit_json(changed=False)
        except AnsibleExitJson:
            pass
    assert "tc_api_calls" not in result
