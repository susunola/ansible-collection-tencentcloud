# -*- coding: utf-8 -*-
"""Helpers for COS modules built on the ``qcloud_cos`` SDK.

Tencent Cloud Object Storage (COS) is not part of the API 3.0 family: it has
its own SDK (the ``cos-python-sdk-v5`` distribution, importable as
``qcloud_cos``) with a ``CosConfig`` + ``CosS3Client`` client model and its
own exception types (``CosServiceError`` / ``CosClientError``). This module
centralises client construction, AppId resolution and error classification so
every ``cos_*`` module shares them, mirroring what ``client.py`` and
``errors.py`` do for API 3.0 services.

COS bucket names are addressed as ``<name>-<appid>``; use
:func:`bucket_full_name` to derive the API form from the short name.

COS exceptions expose ``get_error_code``/``get_status_code``/
``get_request_id`` instead of the API 3.0 ``get_code`` accessors, so the
classification helpers in ``errors.py`` do not apply here; use the
COS-specific ones below.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

# SDK is imported lazily so module_utils stays importable on controllers that
# only run ``ansible-test units`` or ``ansible-doc`` without the SDK.
try:
    from qcloud_cos import CosConfig, CosS3Client
    HAS_COS_SDK = True
except ImportError:
    HAS_COS_SDK = False

from ansible_collections.susunola.tencentcloud.plugins.module_utils import client as api3_client

COS_SDK_IMP_ERR = (
    "The cos-python-sdk-v5 package is required on the Ansible controller "
    "for cos_* modules."
)

# COS error codes meaning the addressed resource does not exist. For a
# delete, or for reading optional sub-resources such as the tag set, these
# are expected and must not fail the module.
NOT_FOUND_CODES = (
    "NoSuchBucket",
    "NoSuchTagSet",
    "NoSuchTagSetError",
)


def require_cos_sdk(module):
    """Fail the module when the qcloud_cos SDK is not importable."""
    if not HAS_COS_SDK:
        module.fail_json(msg=COS_SDK_IMP_ERR)


def create_cos_client(module):
    """Build a ``CosS3Client`` from the module's standard parameters.

    Supports secret id/key plus an optional temporary token. When
    ``role_arn`` is set, the long-lived credentials are first exchanged for
    temporary ones via the STS ``AssumeRole`` API (through
    :func:`client.maybe_assume_role`), which additionally requires the
    ``tencentcloud-sdk-python-sts`` package.
    """
    require_cos_sdk(module)
    secret_id = module.params.get("secret_id")
    secret_key = module.params.get("secret_key")
    if not secret_id or not secret_key:
        module.fail_json(
            msg="Set secret_id and secret_key, or their TENCENTCLOUD_* environment variables."
        )
    token = module.params.get("token")
    if module.params.get("role_arn"):
        secret_id, secret_key, token = api3_client.maybe_assume_role(
            module, secret_id, secret_key, token
        )
    config = CosConfig(
        Region=module.params["region"],
        SecretId=secret_id,
        SecretKey=secret_key,
        Token=token,
        Timeout=module.params.get("timeout") or 60,
        Endpoint=module.params.get("endpoint"),
        UA=module.params.get("user_agent"),
    )
    return CosS3Client(config)


def _accessor(exc, name):
    getter = getattr(exc, name, None)
    if callable(getter):
        try:
            return getter()
        except Exception:
            return None
    return None


def error_code(exc):
    """Return the COS error code of an exception, e.g. ``NoSuchBucket``."""
    return _accessor(exc, "get_error_code")


def status_code(exc):
    """Return the HTTP status code of a COS exception, e.g. ``404``."""
    return _accessor(exc, "get_status_code")


def request_id(exc):
    """Return the request id of a COS exception, or ``None``."""
    return _accessor(exc, "get_request_id")


def is_not_found(exc):
    """True when a COS exception means the addressed resource is absent."""
    if error_code(exc) in NOT_FOUND_CODES:
        return True
    return status_code(exc) == 404


def is_idempotent_success(exc):
    """True when a COS failure should be treated as success for idempotency.

    COS counterpart of ``errors.is_idempotent_success``: deleting or
    asserting the absence of an already-absent resource reports
    ``changed=false`` instead of failing.
    """
    return is_not_found(exc)


def fail_on_cos_error(module, exc, msg="Tencent Cloud COS request failed"):
    """Map a COS SDK exception to ``fail_json``."""
    module.fail_json(
        msg=msg,
        error=str(exc),
        error_code=error_code(exc),
        request_id=request_id(exc),
    )


def bucket_full_name(name, appid):
    """Return the ``<name>-<appid>`` form COS uses for bucket addressing.

    Accepting an already-suffixed name keeps the function idempotent when a
    full name (e.g. from ``cos_bucket_info``) is passed back in.
    """
    suffix = "-{0}".format(appid)
    if name.endswith(suffix):
        return name
    return "{0}{1}".format(name, suffix)


def _load_sts():
    from tencentcloud.sts.v20180813 import models, sts_client
    return models, sts_client


def fetch_appid(module):
    """Resolve the account AppId via the STS ``GetCallerIdentity`` API.

    The ``AccountId`` returned by GetCallerIdentity is the root account's
    AppId, which COS uses as the bucket name suffix.
    """
    models, sts_client = _load_sts()
    sts = module.create_client(sts_client.StsClient, "sts.tencentcloudapi.com")
    response = module.sdk_call(sts.GetCallerIdentity, models.GetCallerIdentityRequest())
    return str(response.AccountId)


def resolve_appid(module):
    """Return the account AppId used in COS bucket names.

    Prefers the module's ``appid`` parameter; when it is not set the AppId is
    resolved via STS, which additionally requires the
    ``tencentcloud-sdk-python-sts`` package.
    """
    appid = module.params.get("appid")
    if appid:
        return str(appid)
    return fetch_appid(module)


def get_bucket_tags(client, full_name):
    """Return the bucket's tags as a plain dict.

    COS returns ``404 NoSuchTagSet`` when a bucket has no tags; that maps to
    an empty dict rather than an error.
    """
    try:
        result = client.get_bucket_tagging(Bucket=full_name)
    except Exception as exc:
        if is_not_found(exc):
            return {}
        raise
    tags = {}
    tag_set = (result or {}).get("TagSet") or {}
    for item in tag_set.get("Tag") or []:
        tags[item["Key"]] = item["Value"]
    return tags


def describe_bucket(client, full_name, short_name=None):
    """Return a dict describing a bucket, or ``None`` when it does not exist.

    Combines ``head_bucket`` (existence), ``get_bucket_location``,
    ``get_bucket_acl`` (whose response carries the parsed ``CannedACL``),
    ``get_bucket_versioning`` and ``get_bucket_tagging``.
    """
    try:
        client.head_bucket(Bucket=full_name)
    except Exception as exc:
        if is_not_found(exc):
            return None
        raise
    location = client.get_bucket_location(Bucket=full_name) or {}
    acl = client.get_bucket_acl(Bucket=full_name) or {}
    versioning = client.get_bucket_versioning(Bucket=full_name) or {}
    return {
        "name": short_name or full_name,
        "full_name": full_name,
        "location": location.get("LocationConstraint"),
        "acl": acl.get("CannedACL", "private"),
        "versioning": versioning.get("Status") == "Enabled",
        "tags": get_bucket_tags(client, full_name),
    }


def list_buckets(client, region=None):
    """Return all buckets owned by the account as plain dicts."""
    kwargs = {}
    if region:
        kwargs["Region"] = region
    result = client.list_buckets(**kwargs) or {}
    bucket_list = (result.get("Buckets") or {}).get("Bucket") or []
    return [
        {
            "name": item.get("Name"),
            "location": item.get("Location"),
            "creation_date": item.get("CreationDate"),
        }
        for item in bucket_list
    ]
