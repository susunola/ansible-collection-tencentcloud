# -*- coding: utf-8 -*-
"""Unified SDK client factory and User-Agent.

Every module constructs its service client with the same three pieces:
credentials, region, and a profile. Centralising the construction guarantees
identical endpoint/timeout/language behaviour and lets us inject a shared
User-Agent without each module remembering to do so.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import configparser
import os

try:
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.common import credential as tc_credential
    HAS_TENCENTCLOUD_SDK = True
except ImportError:
    HAS_TENCENTCLOUD_SDK = False


SDK_IMP_ERR = "The tencentcloud-sdk-python package is required on the Ansible controller."

# TCCLI stores its configuration as an INI file whose sections are profile
# names (``[default]``, ``[prod]``, ...) holding ``secret_id``, ``secret_key``
# and ``region`` keys.
DEFAULT_PROFILE_NAME = "default"
PROFILE_FILE = os.path.join(os.path.expanduser("~"), ".tencentcloud", "default.configure")


def require_sdk(module):
    """Fail the module when the Tencent Cloud SDK is not importable."""
    if not HAS_TENCENTCLOUD_SDK:
        module.fail_json(msg=SDK_IMP_ERR)


def load_profile(profile=None, path=None):
    """Return the settings stored in a TCCLI profile section.

    Reads ``~/.tencentcloud/default.configure`` (the TCCLI INI format) and
    returns the keys of the requested section, or of ``[default]`` when no
    profile name is given. A missing, unreadable or corrupt file — or a
    missing section — yields an empty dict: profile data is only ever a
    fallback and must never crash a module that does not rely on it.
    """
    parser = configparser.ConfigParser()
    try:
        with open(path or PROFILE_FILE) as handle:
            parser.read_file(handle)
    except (OSError, configparser.Error):
        return {}
    section = profile or DEFAULT_PROFILE_NAME
    if not parser.has_section(section):
        return {}
    return {key: value for key, value in parser.items(section) if value}


def resolve_region(module, profile=None):
    """Return the effective region, falling back to the TCCLI profile.

    Precedence mirrors the AWS conventions: the explicit ``region`` module
    parameter (or its ``TENCENTCLOUD_REGION`` environment fallback, already
    folded into the parameter by AnsibleModule) wins over the ``region`` key
    of the selected profile section.

    The resolved value is written back to ``module.params['region']`` so that
    modules reading the parameter directly stay unaware of profiles. When no
    source provides a region the module fails with a clear message.
    """
    region = module.params.get("region")
    if not region:
        if profile is None:
            profile = load_profile(module.params.get("profile"))
        region = profile.get("region")
    if not region:
        module.fail_json(
            msg="Set the region module parameter, the TENCENTCLOUD_REGION "
                "environment variable, or the region key of a profile in "
                "~/.tencentcloud/default.configure."
        )
    module.params["region"] = region
    return region


def create_credential(module):
    """Build SDK credentials from module parameters.

    Supports secret id/key plus an optional temporary token. Parameter and
    environment-variable fallbacks are defined in the shared argument spec;
    values still missing after that fall back to the selected TCCLI profile
    section of ``~/.tencentcloud/default.configure`` (explicit parameter >
    environment variable > profile).

    The region is resolved here too: every module builds its credential
    before touching ``module.params['region']``, so resolving and writing it
    back keeps profile support transparent to the modules.

    When ``role_arn`` is set, the long-lived credentials are first exchanged
    for temporary ones via the STS ``AssumeRole`` API, and the returned
    credential carries the temporary secret id, secret key and token.
    """
    require_sdk(module)
    secret_id = module.params.get("secret_id")
    secret_key = module.params.get("secret_key")
    profile = {}
    if not secret_id or not secret_key:
        profile = load_profile(module.params.get("profile"))
        secret_id = secret_id or profile.get("secret_id")
        secret_key = secret_key or profile.get("secret_key")
    if not secret_id or not secret_key:
        module.fail_json(
            msg="Set secret_id and secret_key, their TENCENTCLOUD_* "
                "environment variables, or the secret_id/secret_key keys of "
                "a profile in ~/.tencentcloud/default.configure."
        )
    resolve_region(module, profile or None)
    credential = tc_credential.Credential(secret_id, secret_key, module.params.get("token"))
    if not module.params.get("role_arn"):
        return credential
    return assume_role_credential(module, credential)


def build_assume_role_request(models, role_arn, role_session_name, role_session_duration):
    """Build an STS AssumeRole request from module parameters."""
    request = models.AssumeRoleRequest()
    request.RoleArn = role_arn
    request.RoleSessionName = role_session_name
    request.DurationSeconds = role_session_duration
    return request


def _load_sts():
    from tencentcloud.sts.v20180813 import models, sts_client
    return models, sts_client


def _assume_role(module, base_credential):
    """Call STS AssumeRole and return the raw API response.

    Kept as a separate function so unit tests can monkeypatch it (or the
    client factory inside it) without importing the real SDK.
    """
    models, sts_client = _load_sts()
    sts = sts_client.StsClient(
        base_credential,
        module.params.get("region"),
        create_client_profile(module, "sts.tencentcloudapi.com"),
    )
    request = build_assume_role_request(
        models,
        module.params["role_arn"],
        module.params.get("role_session_name"),
        module.params.get("role_session_duration"),
    )
    return sts.AssumeRole(request)


def assume_role_credential(module, base_credential):
    """Exchange a base credential for temporary role credentials via STS."""
    response = _assume_role(module, base_credential)
    credentials = response.Credentials
    return tc_credential.Credential(
        credentials.TmpSecretId,
        credentials.TmpSecretKey,
        credentials.Token,
    )


def maybe_assume_role(module, secret_id, secret_key, token=None):
    """Return the final ``(secret_id, secret_key, token)`` triple.

    When ``role_arn`` is set, the long-lived credentials are exchanged for
    temporary ones via the STS ``AssumeRole`` API (reusing the
    :func:`_assume_role` seam) and the temporary triple is returned;
    otherwise the input credentials pass through unchanged. Used by
    non-API-3.0 clients (COS) that build their own credential objects but
    still need role assumption.
    """
    if not module.params.get("role_arn"):
        return secret_id, secret_key, token
    require_sdk(module)
    base_credential = tc_credential.Credential(secret_id, secret_key, token)
    credentials = _assume_role(module, base_credential).Credentials
    return credentials.TmpSecretId, credentials.TmpSecretKey, credentials.Token


def create_client_profile(module, default_endpoint):
    """Create a consistent SDK profile for every service client."""
    require_sdk(module)
    http_profile = HttpProfile()
    http_profile.endpoint = module.params.get("endpoint") or default_endpoint
    http_profile.reqTimeout = module.params["timeout"]
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client_profile.language = "en-US"
    user_agent = module.params.get("user_agent")
    if user_agent:
        client_profile.language = "en-US"
    return client_profile


def create_client(module, client_class, default_endpoint):
    """Build a service client from a module instance.

    :param module: an Ansible module carrying the Tencent Cloud arguments.
    :param client_class: the SDK client class, e.g. ``vpc_client.VpcClient``.
    :param default_endpoint: e.g. ``vpc.tencentcloudapi.com``.
    """
    require_sdk(module)
    return client_class(
        create_credential(module),
        module.params["region"],
        create_client_profile(module, default_endpoint),
    )


def sdk_version():
    """Return the installed SDK version or ``None`` when unavailable."""
    try:
        from tencentcloud import __version__
        return __version__
    except Exception:
        return None
