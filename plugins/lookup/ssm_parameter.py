# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
name: ssm_parameter
short_description: Retrieve Tencent Cloud Secrets Manager secret values
version_added: "0.5.0"
description:
  - Lookup terms are Tencent Cloud Secrets Manager (SSM) secret names; the
    current version (C(SSM_Current)) of each secret is fetched with the
    C(GetSecretValue) API and the plaintext payload is returned.
  - Terms containing C(=) are parsed as keyword arguments, for example
    C(region=ap-guangzhou); all other terms are treated as secret names.
  - Tencent Cloud SSM is a secrets manager, not a parameter store; this
    lookup is the closest equivalent of the C(amazon.aws.aws_ssm) lookup.
options:
  region:
    description:
      - Tencent Cloud region hosting the secrets.
      - Falls back to C(TENCENTCLOUD_REGION).
    type: str
    required: true
    env:
      - name: TENCENTCLOUD_REGION
  with_decryption:
    description:
      - Accepted for parity with the C(amazon.aws.aws_ssm) lookup.
      - C(GetSecretValue) always returns the decrypted payload, so this
        option has no effect on the returned values.
    type: bool
    default: true
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
notes:
  - Requires the C(tencentcloud-sdk-python-ssm) package on the controller.
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Look up a single secret
  ansible.builtin.debug:
    msg: "{{ lookup('tencentcloud.cloud.ssm_parameter', 'db-password', region='ap-guangzhou') }}"

- name: Look up several secrets at once
  ansible.builtin.debug:
    msg: >-
      {{ lookup('tencentcloud.cloud.ssm_parameter',
                'db-password', 'api-token',
                'region=ap-guangzhou') }}
'''

RETURN = r'''
_raw:
  description:
    - List of secret payloads, one per requested secret name, in term order.
    - Text secrets yield their C(SecretString) value; binary secrets yield
      the base64-encoded C(SecretBinary) value.
  returned: success
  type: list
  elements: str
'''

from ansible.errors import AnsibleError
from ansible.module_utils.common.text.converters import to_native
from ansible.parsing.splitter import parse_kv
from ansible.plugins.lookup import LookupBase

try:
    from tencentcloud.ssm.v20190923 import ssm_client, models as ssm_models
    from tencentcloud.common import credential as tc_credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    HAS_TENCENTCLOUD_SDK = True
except ImportError:
    ssm_client = None
    ssm_models = None
    tc_credential = None
    ClientProfile = None
    HttpProfile = None
    HAS_TENCENTCLOUD_SDK = False


SDK_IMP_ERR = "The tencentcloud-sdk-python-ssm package is required on the Ansible controller."

CURRENT_VERSION = "SSM_Current"


def build_get_secret_value_request(models, name, version_id=CURRENT_VERSION):
    """Build a GetSecretValue request for one secret name."""
    request = models.GetSecretValueRequest()
    request.SecretName = name
    request.VersionId = version_id
    return request


def extract_value(response):
    """Return the plaintext payload of a GetSecretValue response."""
    if response.SecretString is not None:
        return response.SecretString
    return response.SecretBinary


def get_secret_value(client, models, name):
    """Fetch one secret and return its payload."""
    request = build_get_secret_value_request(models, name)
    return extract_value(client.GetSecretValue(request))


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
        names = []
        for term in terms or []:
            if "=" in term:
                kwargs.update(parse_kv(term))
            else:
                names.append(term)
        self.set_options(var_options=variables, direct=kwargs)

        region = self.get_option("region")
        if not region:
            raise AnsibleError("Set region or the TENCENTCLOUD_REGION environment variable.")
        secret_id = self.get_option("secret_id")
        secret_key = self.get_option("secret_key")
        if not secret_id or not secret_key:
            raise AnsibleError(
                "Set secret_id and secret_key, or their TENCENTCLOUD_* environment variables."
            )

        credential = tc_credential.Credential(secret_id, secret_key, self.get_option("token"))
        client = self._create_client(credential, region)
        values = []
        for name in names:
            try:
                values.append(get_secret_value(client, ssm_models, name))
            except Exception as exc:
                raise AnsibleError(sdk_error_message("GetSecretValue(%s)" % name, exc))
        return values

    def _create_client(self, credential, region):
        """Build an SSM client for one region directly from the SDK."""
        http_profile = HttpProfile()
        http_profile.endpoint = "ssm.tencentcloudapi.com"
        http_profile.reqTimeout = 60
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        client_profile.language = "en-US"
        return ssm_client.SsmClient(credential, region, client_profile)
