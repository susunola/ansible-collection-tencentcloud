# -*- coding: utf-8 -*-
"""Error classification and idempotent-exception helpers.

Tencent Cloud SDK errors are raised as
:class:`tencentcloud.common.exception.tencent_cloud_sdk_exception.TencentCloudSDKException`,
carrying an error code. This module classifies those codes into the buckets a
resource module needs:

- ``not_found``: the resource does not exist. For a delete or absent-idempotent
  operation this is success, not a failure.
- ``rate_limited``: the API asked us to slow down (``RequestLimitExceeded.*``
  and ``LimitExceeded.*``). Callers should back off and retry.
- ``retryable``: transient failures that may succeed on retry (5xx, timeouts,
  ``InternalError``, ``RequestTimeout``, ``ServiceUnavailable``).
- ``unauthorized``: credential or permission problems.
- ``other``: anything else. Most of these are permanent and should not be
  retried.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type


# SDK is imported lazily so module_utils stays importable on controllers that
# only run ``ansible-test units`` or ``ansible-doc`` without the SDK.
def _exception_code(exc):
    get_code = getattr(exc, "get_code", None)
    if callable(get_code):
        return get_code()
    return None


def is_not_found(exc):
    """True when the SDK exception means the resource does not exist."""
    code = _exception_code(exc)
    if not code:
        return False
    if code.startswith("ResourceNotFound"):
        return True
    # Describe requests on absent resources commonly surface these variants.
    return code in (
        "InvalidInstanceId.NotFound",
        "InvalidSecurityGroupId.NotFound",
        "InvalidVpcId.NotFound",
        "InvalidSubnetId.NotFound",
        "InvalidParameterValue.NotFound",
    )


def is_rate_limited(exc):
    """True when the API reports throttling and the call should be retried."""
    code = _exception_code(exc)
    if not code:
        return False
    return code.startswith("RequestLimitExceeded") or code.startswith("LimitExceeded")


def is_retryable(exc):
    """True when the failure is transient and worth retrying."""
    code = _exception_code(exc)
    if not code:
        return False
    if is_rate_limited(exc):
        return True
    return code in (
        "InternalError",
        "InternalError.AuthFailure",
        "InternalError.RequestTimeout",
        "RequestTimeout",
        "ServiceUnavailable",
        "ResourceBusy",
    ) or code.startswith("InternalError.")


def is_unauthorized(exc):
    """True when credentials or CAM permissions caused the failure."""
    code = _exception_code(exc)
    if not code:
        return False
    return code.startswith("AuthFailure") or code.startswith("UnauthorizedOperation")


def classify(exc):
    """Return the bucket name for a raised SDK exception.

    Buckets: ``not_found``, ``rate_limited``, ``retryable``, ``unauthorized``,
    ``other``.
    """
    if is_not_found(exc):
        return "not_found"
    if is_rate_limited(exc):
        return "rate_limited"
    if is_retryable(exc):
        return "retryable"
    if is_unauthorized(exc):
        return "unauthorized"
    return "other"


def is_idempotent_success(exc):
    """True when a failure should be treated as success for idempotency.

    Deleting or asserting the absence of an already-absent resource must
    report ``changed=false`` instead of failing.
    """
    return classify(exc) == "not_found"
