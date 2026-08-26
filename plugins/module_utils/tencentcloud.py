# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.module_utils.basic import env_fallback

try:
    from tencentcloud.common import credential
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
    }


def create_credential(module):
    if not HAS_TENCENTCLOUD_SDK:
        module.fail_json(msg=SDK_IMP_ERR)
    secret_id = module.params.get("secret_id")
    secret_key = module.params.get("secret_key")
    if not secret_id or not secret_key:
        module.fail_json(msg="Set secret_id and secret_key, or their TENCENTCLOUD_* environment variables.")
    return credential.Credential(secret_id, secret_key, module.params.get("token"))


def sdk_call(module, function, request):
    try:
        return function(request)
    except TencentCloudSDKException as exc:
        module.fail_json(msg="Tencent Cloud API request failed", error=str(exc))
    except Exception as exc:
        module.fail_json(msg="Unexpected Tencent Cloud API error", error=str(exc))
