# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for the module_utils.tencentcloud call wrappers.

Every generated ``*_info`` module funnels its API calls through
``read_sdk_call``; this file pins the failure contract both wrappers share:
SDK errors fail the module with the error code and request id (never a
traceback), unexpected errors fail with a clean message, and success returns
the response untouched.

``read_sdk_call`` adds the retry a read may take: throttling and transient
failures are retried, a permission problem is not, and an exhausted budget is
reported with the error class the retry policy acted on. ``sdk_call`` retries
nothing, because it also serves write modules.
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


# ---------------------------------------------------------------------------
# read_sdk_call: the same failure contract, plus the retry a read may take
# ---------------------------------------------------------------------------

class _Counter(object):
    """Sleep replacement that records the delays it was asked to wait."""

    def __init__(self):
        self.delays = []

    def __call__(self, seconds):
        self.delays.append(seconds)


def test_read_sdk_call_returns_response_on_success():
    marker = object()

    def _operation(request):
        assert request is marker
        return {"RequestId": "req-ok"}

    recorder = _Recorder()
    result = tc.read_sdk_call(recorder, _operation, marker)
    assert result == {"RequestId": "req-ok"}
    assert recorder.failed is None


def test_read_sdk_call_retries_a_throttled_call(sdk_exception, monkeypatch):
    """Throttling is the failure the read path exists to absorb."""
    throttled = _FakeSDKException("RequestLimitExceeded", "slow down", "req-throttle")
    calls = []
    sleeps = _Counter()

    def _operation(request):
        calls.append(request)
        if len(calls) == 1:
            raise throttled
        return {"RequestId": "req-ok"}

    recorder = _Recorder()
    result = tc.read_sdk_call(recorder, _operation, object(), sleep_fn=sleeps)
    assert result == {"RequestId": "req-ok"}
    assert len(calls) == 2
    assert len(sleeps.delays) == 1
    assert recorder.failed is None


def test_read_sdk_call_retries_a_transient_service_failure(sdk_exception):
    transient = _FakeSDKException("ServiceUnavailable", "try later", "req-5xx")
    calls = []

    def _operation(request):
        calls.append(request)
        if len(calls) == 1:
            raise transient
        return {"RequestId": "req-ok"}

    recorder = _Recorder()
    result = tc.read_sdk_call(recorder, _operation, object(), sleep_fn=_Counter())
    assert result == {"RequestId": "req-ok"}
    assert recorder.failed is None


def test_read_sdk_call_does_not_retry_an_unauthorized_error(sdk_exception):
    """A permission problem cannot be fixed by asking again."""
    sleeps = _Counter()
    calls = []

    def _operation(request):
        calls.append(request)
        raise sdk_exception

    recorder = _Recorder()
    tc.read_sdk_call(recorder, _operation, object(), sleep_fn=sleeps)
    assert len(calls) == 1
    assert sleeps.delays == []
    payload = recorder.failed
    assert payload["error_code"] == "UnauthorizedOperation"
    assert payload["request_id"] == "req-err"
    # The bucket the code belongs to, so a report does not have to parse the
    # message to tell throttling from a permissions problem.
    assert payload["error_class"] == "unauthorized"


def test_read_sdk_call_reports_exhaustion_as_rate_limited(sdk_exception):
    throttled = _FakeSDKException("RequestLimitExceeded", "slow down", "req-throttle")
    sleeps = _Counter()
    calls = []

    def _operation(request):
        calls.append(request)
        raise throttled

    recorder = _Recorder()
    tc.read_sdk_call(recorder, _operation, object(), retries=2, sleep_fn=sleeps)
    # The first call plus the two retries the budget allows.
    assert len(calls) == 3
    assert len(sleeps.delays) == 2
    assert recorder.failed["error_class"] == "rate_limited"
    assert recorder.failed["error_code"] == "RequestLimitExceeded"


def test_read_sdk_call_defaults_to_a_real_sleep(sdk_exception, monkeypatch):
    """``sleep_fn`` is resolved at call time, so the default is the real one."""
    seen = []
    monkeypatch.setattr(tc.time, "sleep", lambda seconds: seen.append(seconds))
    throttled = _FakeSDKException("RequestLimitExceeded", "slow down", "req-throttle")
    calls = []

    def _operation(request):
        calls.append(request)
        if len(calls) == 1:
            raise throttled
        return {"RequestId": "req-ok"}

    recorder = _Recorder()
    assert tc.read_sdk_call(recorder, _operation, object()) == {"RequestId": "req-ok"}
    assert len(seen) == 1


def test_serialize_sdk_object_returns_plain_dict():
    class _Model(object):
        def _serialize(self, allow_none=True):
            assert allow_none is True
            return {"InstanceId": "ins-1"}

    assert tc.serialize_sdk_object(_Model()) == {"InstanceId": "ins-1"}


def test_create_credential_delegates_to_client(monkeypatch):
    from ansible_collections.susunola.tencentcloud.plugins.module_utils import client as client_mod

    sentinel = object()
    monkeypatch.setattr(client_mod, "create_credential", lambda module: sentinel)
    assert tc.create_credential(object()) is sentinel


def test_create_client_profile_delegates_to_client(monkeypatch):
    from ansible_collections.susunola.tencentcloud.plugins.module_utils import client as client_mod

    sentinel = object()
    monkeypatch.setattr(client_mod, "create_client_profile", lambda module, endpoint: sentinel)
    assert tc.create_client_profile(object(), "vpc.tencentcloudapi.com") is sentinel


def _error_pages_operation(request):
    """A client method that always serves the same page under a larger total."""
    from types import SimpleNamespace

    return SimpleNamespace(Items=[1, 2], TotalCount=9, RequestId="req-loop")


def test_paginate_read_returns_items_total_and_request_id():
    from types import SimpleNamespace

    def _operation(request):
        return SimpleNamespace(Items=[1, 2], TotalCount=2, RequestId="req-p")

    items, total, request_id = tc.paginate_read(
        _Recorder(),
        2,
        lambda offset, limit: {"offset": offset},
        _operation,
        lambda r: r.Items,
        lambda r: r.TotalCount,
    )
    assert items == [1, 2]
    assert total == 2
    assert request_id == "req-p"


def test_paginate_read_reports_a_repeated_page_as_a_module_failure():
    recorder = _Recorder()
    tc.paginate_read(
        recorder,
        2,
        lambda offset, limit: {"offset": offset},
        _error_pages_operation,
        lambda r: r.Items,
        lambda r: r.TotalCount,
    )
    payload = recorder.failed
    assert payload["msg"] == "Tencent Cloud list API returned an unusable page sequence"
    assert "ignoring Offset" in payload["error"]
    assert payload["request_id"] == "req-loop"


def test_paginate_read_retries_a_throttled_page(sdk_exception):
    """The retry lives inside the page loop, so a throttled page is re-read."""
    from types import SimpleNamespace

    throttled = _FakeSDKException("RequestLimitExceeded", "slow down", "req-t")
    calls = []

    def _operation(request):
        calls.append(request)
        if len(calls) == 1:
            raise throttled
        return SimpleNamespace(Items=[1, 2], TotalCount=2, RequestId="req-p")

    items, total, _request_id = tc.paginate_read(
        _Recorder(),
        2,
        lambda offset, limit: {"offset": offset},
        _operation,
        lambda r: r.Items,
        lambda r: r.TotalCount,
        sleep_fn=_Counter(),
    )
    assert items == [1, 2]
    assert total == 2
    assert len(calls) == 2


# ---------------------------------------------------------------------------
# loading without the SDK
# ---------------------------------------------------------------------------

def test_the_placeholder_exception_loads_without_the_sdk(monkeypatch):
    """The module is importable where the SDK is not, which is how the unit
    suite itself runs. The placeholder keeps the name resolvable so
    ``read_sdk_call``'s except clause stays valid and a test can patch it.

    Executed under a private name rather than by reloading the shared module:
    ``importlib.reload`` rebinds every function in
    ``module_utils.tencentcloud`` while modules that did
    ``from ... import <name>`` keep the objects they were given, so the suite
    would start depending on which test ran first. Nothing here needs the
    shared object -- only a fresh execution of the file with the SDK blocked.
    """
    import importlib.util
    import sys

    blocked = "tencentcloud.common.exception.tencent_cloud_sdk_exception"
    monkeypatch.setitem(sys.modules, blocked, None)
    spec = importlib.util.spec_from_file_location("tc_placeholder_probe", tc.__file__)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)

    assert probe.HAS_TENCENTCLOUD_SDK is False
    placeholder = probe.TencentCloudSDKException
    assert issubclass(placeholder, Exception)
    assert placeholder("boom").get_code() is None
    assert placeholder("boom").get_request_id() is None
