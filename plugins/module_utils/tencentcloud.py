# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.module_utils.basic import env_fallback

try:
    from tencentcloud.common import credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
    HAS_TENCENTCLOUD_SDK = True
except ImportError:
    HAS_TENCENTCLOUD_SDK = False


SDK_IMP_ERR = "The tencentcloud-sdk-python package is required on the Ansible controller."


def tencentcloud_argument_spec():
    return {
        "secret_id": {"type": "str", "no_log": True, "fallback": (env_fallback, ["TENCENTCLOUD_SECRET_ID"])},
        "secret_key": {"type": "str", "no_log": True, "fallback": (env_fallback, ["TENCENTCLOUD_SECRET_KEY"])},
        "token": {"type": "str", "no_log": True, "fallback": (env_fallback, ["TENCENTCLOUD_TOKEN"])},
        "region": {"type": "str", "required": True, "fallback": (env_fallback, ["TENCENTCLOUD_REGION"])},
        "endpoint": {"type": "str"},
        "timeout": {"type": "int", "default": 60},
    }


def create_credential(module):
    if not HAS_TENCENTCLOUD_SDK:
        module.fail_json(msg=SDK_IMP_ERR)
    secret_id = module.params.get("secret_id")
    secret_key = module.params.get("secret_key")
    if not secret_id or not secret_key:
        module.fail_json(msg="Set secret_id and secret_key, or their TENCENTCLOUD_* environment variables.")
    return credential.Credential(secret_id, secret_key, module.params.get("token"))


def create_client_profile(module, default_endpoint):
    """Create a consistent SDK profile for every service client."""
    if not HAS_TENCENTCLOUD_SDK:
        module.fail_json(msg=SDK_IMP_ERR)
    http_profile = HttpProfile()
    http_profile.endpoint = module.params.get("endpoint") or default_endpoint
    http_profile.reqTimeout = module.params["timeout"]
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client_profile.language = "en-US"
    return client_profile


def serialize_sdk_object(value):
    """Convert an SDK model to the plain dictionaries Ansible returns."""
    return value._serialize(allow_none=True)


def sdk_call(module, function, request):
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
