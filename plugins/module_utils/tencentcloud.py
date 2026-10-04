# -*- coding: utf-8 -*-
"""Backward-compatible shim for the original single-file module_utils.

The original helpers live here so the existing discovery modules keep
working unchanged. New code should import from the dedicated modules:

- :mod:`errors` - error classification and idempotent-exception helpers
- :mod:`retries` - throttling, exponential backoff and jitter
- :mod:`paging` - unified offset/limit pagination
- :mod:`tagging` - tag conversion and comparison
- :mod:`comparison` - resource diff computation
- :mod:`waiters` - async state polling
- :mod:`client` - unified SDK client factory
- :mod:`base` - ``TencentCloudModule`` base class

Two call wrappers live here, and the difference is deliberate:

- :func:`sdk_call` never retries. Write modules use it, and a retried write is
  not obviously a single write, so the decision belongs to the caller.
- :func:`read_sdk_call` retries throttling and transient errors. Re-issuing a
  read cannot change state, so the read-only ``_info`` modules use this one.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import time

from ansible.module_utils.basic import env_fallback

from ansible_collections.susunola.tencentcloud.plugins.module_utils import client as _client
from ansible_collections.susunola.tencentcloud.plugins.module_utils import errors as _errors
from ansible_collections.susunola.tencentcloud.plugins.module_utils.paging import PaginationError, Paginator
from ansible_collections.susunola.tencentcloud.plugins.module_utils.retries import retry_on

try:
    from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
    HAS_TENCENTCLOUD_SDK = True
except ImportError:
    HAS_TENCENTCLOUD_SDK = False

    class TencentCloudSDKException(Exception):
        """Placeholder for SDK-less environments.

        The SDK is required at runtime, so a real SDK exception can never be
        raised when it is missing. The placeholder keeps the name resolvable
        so ``sdk_call``'s except clause stays valid and unit tests can patch
        the name without the SDK installed.
        """

        def get_code(self):
            return None

        def get_request_id(self):
            return None


SDK_IMP_ERR = "The tencentcloud-sdk-python package is required on the Ansible controller."


def tencentcloud_argument_spec():
    """Legacy shared argument spec.

    Kept for compatibility with the discovery modules. New write modules
    should use ``base_argument_spec`` from :mod:`base`, which adds the retry
    and waiter parameters.
    """
    return {
        "secret_id": {"type": "str", "no_log": True, "fallback": (env_fallback, ["TENCENTCLOUD_SECRET_ID"])},
        "secret_key": {"type": "str", "no_log": True, "fallback": (env_fallback, ["TENCENTCLOUD_SECRET_KEY"])},
        "token": {"type": "str", "no_log": True, "fallback": (env_fallback, ["TENCENTCLOUD_TOKEN"])},
        "role_arn": {"type": "str", "fallback": (env_fallback, ["TENCENTCLOUD_ROLE_ARN"])},
        "role_session_name": {"type": "str", "default": "ansible-tencentcloud"},
        "role_session_duration": {"type": "int", "default": 7200},
        "profile": {"type": "str", "fallback": (env_fallback, ["TENCENTCLOUD_PROFILE"])},
        "region": {"type": "str", "fallback": (env_fallback, ["TENCENTCLOUD_REGION"])},
        "endpoint": {"type": "str"},
        "timeout": {"type": "int", "default": 60},
    }


def create_credential(module):
    """Legacy credential helper, delegated to :mod:`client`."""
    return _client.create_credential(module)


def create_client_profile(module, default_endpoint):
    """Legacy profile helper, delegated to :mod:`client`."""
    return _client.create_client_profile(module, default_endpoint)


def serialize_sdk_object(value):
    """Convert an SDK model to the plain dictionaries Ansible returns."""
    return value._serialize(allow_none=True)


def sdk_call(module, function, request):
    """Legacy SDK call wrapper preserving original failure semantics.

    On failure the module fails with the request id and error code. Unlike
    ``TencentCloudModule.sdk_call`` this version does not retry; existing
    modules keep their current behaviour until they migrate.
    """
    try:
        return function(request)
    except TencentCloudSDKException as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=exc.get_code(),
            request_id=exc.get_request_id(),
        )
    except Exception as exc:
        module.fail_json(msg="Unexpected Tencent Cloud API error", error=str(exc))


#: Retries for a read-only call. Matches ``base_argument_spec``'s ``retries``
#: default so a generated ``_info`` module and a hand-written module that reads
#: the same resource give up at the same point.
READ_RETRIES = 5


def read_sdk_call(module, function, request, retries=READ_RETRIES, sleep_fn=None):
    """Run a read-only SDK call, retrying failures that may not recur.

    ``sdk_call`` deliberately does not retry, because it also serves write
    modules and a retried write is not obviously a single write. A read cannot
    have that consequence: re-issuing ``Describe*``/``List*`` either returns
    the current state or fails again, so throttling and transient errors are
    retried here with the same policy ``TencentCloudModule`` applies.

    The failure payload matches ``sdk_call``'s and adds ``error_class``, the
    ``module_utils.errors`` bucket for the code, so a report distinguishes
    throttling from a permission problem without parsing the message.

    :param retries: retry attempts after the first call.
    :param sleep_fn: backoff sleep, resolved at call time so tests can
        replace it; defaults to :func:`time.sleep`.
    """
    sleep_fn = sleep_fn or time.sleep

    def invoke():
        return function(request)

    try:
        return retry_on(invoke, retries=retries, sleep_fn=sleep_fn)
    except TencentCloudSDKException as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=exc.get_code(),
            request_id=exc.get_request_id(),
            error_class=_errors.classify(exc),
        )
    except Exception as exc:
        module.fail_json(msg="Unexpected Tencent Cloud API error", error=str(exc))


def paginate_read(module, page_size, build_request, operation, items_of, total_of,
                  retries=READ_RETRIES, sleep_fn=None):
    """Walk every page of a read-only list API.

    The generated ``_info`` modules need three things from a paged read and
    would otherwise repeat all three 500 times: each page call retries the
    failures a read may retry, an unusable page sequence becomes a module
    failure rather than a traceback, and the last response's ``RequestId`` is
    returned so the result can be cross-referenced in cloud audit logs.

    :param operation: SDK client method, e.g. ``client.DescribeVpcs``.
    :returns: ``(items, total_count, request_id)``.
    """
    paginator = Paginator(
        page_size,
        build_request,
        lambda request: read_sdk_call(module, operation, request, retries, sleep_fn),
        items_of,
        total_of,
    )
    items, total_count = [], None
    try:
        items, total_count = paginator.fetch_all()
    except PaginationError as exc:
        module.fail_json(
            msg="Tencent Cloud list API returned an unusable page sequence",
            error=str(exc),
            request_id=paginator.request_id,
        )
    return items, total_count, paginator.request_id


# Re-exported helpers for modules that prefer the short names.
is_not_found = _errors.is_not_found
is_idempotent_success = _errors.is_idempotent_success
classify = _errors.classify
