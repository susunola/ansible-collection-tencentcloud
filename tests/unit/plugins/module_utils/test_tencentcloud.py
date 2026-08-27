# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for the legacy sdk_call helper in module_utils.tencentcloud.

Every generated ``*_info`` module funnels its API calls through
``sdk_call``; this file pins the failure contract: SDK errors fail the
module with the error code and request id (never a traceback), unexpected
errors fail with a clean message, and success returns the response
untouched.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import tencentcloud as tc


class _Recorder(object):
    """Minimal module stand-in recording the fail_json payload."""

    def __init__(self):
        self.failed = None

    def fail_json(self, **kwargs):
        self.failed = kwargs


class _FakeSDKException(Exception):
    """Shape-compatible stand-in for TencentCloudSDKException.

    ``sdk_call`` references the exception class through the module-global
    ``TencentCloudSDKException`` name; tests patch that name with this
    class so the except branch is exercised without the SDK installed.
    """

    def __init__(self, code, message, request_id):
        super(_FakeSDKException, self).__init__(message)
        self._code = code
        self._request_id = request_id

    def get_code(self):
        return self._code

    def get_request_id(self):
        return self._request_id


@pytest.fixture
def sdk_exception(monkeypatch):
    monkeypatch.setattr(tc, "TencentCloudSDKException", _FakeSDKException)
    return _FakeSDKException("UnauthorizedOperation", "not allowed", "req-err")


def test_sdk_call_returns_response_on_success(monkeypatch):
    marker = object()

    def _operation(request):
        assert request is marker
        return {"RequestId": "req-ok"}

    recorder = _Recorder()
    result = tc.sdk_call(recorder, _operation, marker)
    assert result == {"RequestId": "req-ok"}
    assert recorder.failed is None


def test_sdk_call_sdk_error_fails_with_code_and_request_id(sdk_exception):
    def _operation(request):
        raise sdk_exception

    recorder = _Recorder()
    tc.sdk_call(recorder, _operation, object())
    payload = recorder.failed
    assert payload is not None
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "not allowed" in payload["error"]
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"


def test_sdk_call_unexpected_error_fails_cleanly(monkeypatch):
    def _operation(request):
        raise RuntimeError("boom")

    recorder = _Recorder()
    tc.sdk_call(recorder, _operation, object())
    payload = recorder.failed
    assert payload is not None
    assert payload["msg"] == "Unexpected Tencent Cloud API error"
    assert payload["error"] == "boom"
