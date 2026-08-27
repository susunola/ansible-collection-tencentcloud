# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
name: sts_caller_identity
short_description: Get information about the Tencent Cloud credentials in use
version_added: "0.5.0"
description:
  - Calls the Tencent Cloud STS C(GetCallerIdentity) API and returns the
    account and identity the current credentials belong to.
  - Lookup terms only carry keyword arguments, for example
    C(secret_id=... region=...).
options:
  secret_id:
    description: Tencent Cloud API secret ID. Falls back to C(TENCENTCLOUD_SECRET_ID).
    type: str
    env:
      - name: TENCENTCLOUD_SECRET_ID
  secret_key:
    description: Tencent Cloud API secret key. Falls back to C(TENCENTCLOUD_SECRET_KEY).
    type: str
    env:
      - name: TENCENTCLOUD_SECRET_KEY
  token:
    description: Temporary credential token. Falls back to C(TENCENTCLOUD_TOKEN).
    type: str
    env:
      - name: TENCENTCLOUD_TOKEN
  profile:
    description:
      - TCCLI credential profile section of C(~/.tencentcloud/default.configure)
        used as a fallback for O(secret_id) and O(secret_key).
      - Explicit terms and their environment variables take precedence over
        the profile.
      - Falls back to C(TENCENTCLOUD_PROFILE).
    type: str
    env:
      - name: TENCENTCLOUD_PROFILE
  region:
    description:
      - Region used for the STS endpoint. Falls back to C(TENCENTCLOUD_REGION).
      - STS is a global service; the region only selects the access point.
    type: str
    env:
      - name: TENCENTCLOUD_REGION
  role_arn:
    description:
      - When set, assume this CAM role with C(AssumeRole) before calling
        C(GetCallerIdentity), so the returned identity is the assumed role.
      - Falls back to C(TENCENTCLOUD_ROLE_ARN).
    type: str
    env:
      - name: TENCENTCLOUD_ROLE_ARN
notes:
  - Requires the C(tencentcloud-sdk-python-sts) package on the controller.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Show the caller identity
  ansible.builtin.debug:
    msg: "{{ lookup('susunola.tencentcloud.sts_caller_identity') }}"

- name: Identity of an assumed role in a specific region
  ansible.builtin.debug:
    msg: >-
      {{ lookup('susunola.tencentcloud.sts_caller_identity',
                'region=ap-guangzhou',
                'role_arn=qcs::cam::uin/100000000001:roleName/ops') }}
'''

RETURN = r'''
_raw:
  description:
    - A one-element list holding a dict with the caller identity.
    - Keys mirror the C(GetCallerIdentity) response fields, for example
      C(AccountId), C(Arn), C(PrincipalId), C(Type) and C(UserId).
  returned: success
  type: list
  elements: dict
'''

from ansible.errors import AnsibleError
from ansible.module_utils.common.text.converters import to_native
from ansible.parsing.splitter import parse_kv
from ansible.plugins.lookup import LookupBase

from ansible_collections.susunola.tencentcloud.plugins.module_utils.client import load_profile

try:
    from tencentcloud.sts.v20180813 import sts_client, models as sts_models
    from tencentcloud.common import credential as tc_credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    HAS_TENCENTCLOUD_SDK = True
except ImportError:
    sts_client = None
    sts_models = None
    tc_credential = None
    ClientProfile = None
    HttpProfile = None
    HAS_TENCENTCLOUD_SDK = False


SDK_IMP_ERR = "The tencentcloud-sdk-python-sts package is required on the Ansible controller."

ROLE_SESSION_NAME = "ansible-tencentcloud"
ROLE_SESSION_DURATION = 7200


def build_credential(credential_module, secret_id, secret_key, token=None):
    """Build an SDK credential object from raw parts."""
    return credential_module.Credential(secret_id, secret_key, token)


def assume_role(client, models, role_arn, session_name=ROLE_SESSION_NAME,
                duration=ROLE_SESSION_DURATION):
    """Assume a CAM role and return the temporary Credentials model."""
    request = models.AssumeRoleRequest()
    request.RoleArn = role_arn
    request.RoleSessionName = session_name
    request.DurationSeconds = duration
    return client.AssumeRole(request).Credentials


def serialize_identity(response):
    """Convert a GetCallerIdentity response model to a plain dict."""
    return {
        "AccountId": response.AccountId,
        "Arn": response.Arn,
        "PrincipalId": response.PrincipalId,
        "Type": response.Type,
        "UserId": response.UserId,
    }


def get_caller_identity(client, models):
    """Call GetCallerIdentity and return the identity as a plain dict."""
    request = models.GetCallerIdentityRequest()
    return serialize_identity(client.GetCallerIdentity(request))


def sdk_error_message(action, exc):
    """Format an SDK exception with its error code and request id."""
    get_code = getattr(exc, "get_code", None)
    get_request_id = getattr(exc, "get_request_id", None)
    detail = to_native(exc)
    if callable(get_code) and get_code():
        detail = "%s (%s)" % (detail, get_code())
    if callable(get_request_id) and get_request_id():
        detail = "%s [RequestId: %s]" % (detail, get_request_id())
    return "%s failed: %s" % (action, detail)


class LookupModule(LookupBase):

    def run(self, terms, variables=None, **kwargs):
        if not HAS_TENCENTCLOUD_SDK:
            raise AnsibleError(SDK_IMP_ERR)
        for term in terms or []:
            kwargs.update(parse_kv(term))
        self.set_options(var_options=variables, direct=kwargs)

        secret_id = self.get_option("secret_id")
        secret_key = self.get_option("secret_key")
        if not secret_id or not secret_key:
            profile = load_profile(self.get_option("profile"))
            secret_id = secret_id or profile.get("secret_id")
            secret_key = secret_key or profile.get("secret_key")
        if not secret_id or not secret_key:
            raise AnsibleError(
                "Set secret_id and secret_key, their TENCENTCLOUD_* environment "
                "variables, or the secret_id/secret_key keys of a profile in "
                "~/.tencentcloud/default.configure."
            )

        credential = build_credential(
            tc_credential, secret_id, secret_key, self.get_option("token")
        )
        client = self._create_client(credential)
        role_arn = self.get_option("role_arn")
        if role_arn:
            try:
                temporary = assume_role(client, sts_models, role_arn)
            except Exception as exc:
                raise AnsibleError(sdk_error_message("AssumeRole", exc))
            credential = build_credential(
                tc_credential, temporary.TmpSecretId, temporary.TmpSecretKey, temporary.Token
            )
            client = self._create_client(credential)
        try:
            return [get_caller_identity(client, sts_models)]
        except Exception as exc:
            raise AnsibleError(sdk_error_message("GetCallerIdentity", exc))

    def _create_client(self, credential):
        """Build an STS client directly from the SDK."""
        http_profile = HttpProfile()
        http_profile.endpoint = "sts.tencentcloudapi.com"
        http_profile.reqTimeout = 60
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        client_profile.language = "en-US"
        return sts_client.StsClient(
            credential, self.get_option("region") or "", client_profile
        )
