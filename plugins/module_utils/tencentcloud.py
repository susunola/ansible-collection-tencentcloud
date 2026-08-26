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
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.module_utils.basic import env_fallback

from ansible_collections.tencentcloud.cloud.plugins.module_utils import client as _client
from ansible_collections.tencentcloud.cloud.plugins.module_utils import errors as _errors
from ansible_collections.tencentcloud.cloud.plugins.module_utils.paging import Paginator

try:
    from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
    HAS_TENCENTCLOUD_SDK = True
except ImportError:
    HAS_TENCENTCLOUD_SDK = False


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
        "region": {"type": "str", "required": True, "fallback": (env_fallback, ["TENCENTCLOUD_REGION"])},
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


def paginate(module, page_size, build_request, call_api, items_of, total_of):
    """Pagination helper that works with legacy modules.

    ``call_api`` is expected to be a bound client method; failures are
    surfaced through ``module.fail_json`` by the legacy ``sdk_call`` pattern.
    """
    return Paginator(page_size, build_request, call_api, items_of, total_of).fetch_all()


# Re-exported helpers for modules that prefer the short names.
is_not_found = _errors.is_not_found
is_idempotent_success = _errors.is_idempotent_success
classify = _errors.classify
