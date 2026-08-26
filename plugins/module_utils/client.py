# -*- coding: utf-8 -*-
"""Unified SDK client factory and User-Agent.

Every module constructs its service client with the same three pieces:
credentials, region, and a profile. Centralising the construction guarantees
identical endpoint/timeout/language behaviour and lets us inject a shared
User-Agent without each module remembering to do so.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

try:
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.common import credential as tc_credential
    HAS_TENCENTCLOUD_SDK = True
except ImportError:
    HAS_TENCENTCLOUD_SDK = False


SDK_IMP_ERR = "The tencentcloud-sdk-python package is required on the Ansible controller."


def require_sdk(module):
    """Fail the module when the Tencent Cloud SDK is not importable."""
    if not HAS_TENCENTCLOUD_SDK:
        module.fail_json(msg=SDK_IMP_ERR)


def create_credential(module):
    """Build SDK credentials from module parameters.

    Supports secret id/key plus an optional temporary token. Parameter and
    environment-variable fallbacks are defined in the shared argument spec.
    """
    require_sdk(module)
    secret_id = module.params.get("secret_id")
    secret_key = module.params.get("secret_key")
    if not secret_id or not secret_key:
        module.fail_json(
            msg="Set secret_id and secret_key, or their TENCENTCLOUD_* environment variables."
        )
    return tc_credential.Credential(secret_id, secret_key, module.params.get("token"))


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
