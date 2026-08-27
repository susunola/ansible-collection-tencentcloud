# -*- coding: utf-8 -*-
"""Base module class for Tencent Cloud resource modules.

New resource modules should build on :class:`TencentCloudModule` rather than
raw ``AnsibleModule`` so that:

- every module carries the same retry/waiter parameters (via the shared
  argument spec and doc fragment)
- every SDK call goes through the same retry policy
- every client is built by the same factory

The original ``tencentcloud.py`` helpers are preserved as a shim so the
existing discovery modules keep working unchanged; new code should import
from the dedicated modules instead.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.module_utils.basic import AnsibleModule, env_fallback

from ansible_collections.tencentcloud.cloud.plugins.module_utils import client
from ansible_collections.tencentcloud.cloud.plugins.module_utils.retries import retry_on


def base_argument_spec():
    """Arguments shared by every Tencent Cloud module, including write ops."""
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
        "retries": {"type": "int", "default": 5},
        "waiter_timeout": {"type": "int", "default": 120},
        "waiter_delay": {"type": "int", "default": 5},
        "user_agent": {"type": "str", "default": "ansible-collection.tencentcloud.cloud"},
    }


class TencentCloudModule(AnsibleModule):
    """AnsibleModule with Tencent Cloud conventions pre-wired."""

    def __init__(self, argument_spec=None, **kwargs):
        spec = base_argument_spec()
        if argument_spec:
            spec.update(argument_spec)
        super(TencentCloudModule, self).__init__(argument_spec=spec, **kwargs)

    def require_sdk(self):
        client.require_sdk(self)

    def create_credential(self):
        return client.create_credential(self)

    def create_client(self, client_class, default_endpoint):
        return client.create_client(self, client_class, default_endpoint)

    def sdk_call(self, operation, request=None, retry=True):
        """Run an SDK call with the module's retry policy.

        :param operation: SDK client method, e.g. ``client.DescribeVpcs``.
        :param request: request object; when given the operation is invoked
            as ``operation(request)``, otherwise ``operation()``.
        :param retry: when False the call runs without retrying.

        Exhausted retries re-raise the last SDK exception; the caller is
        responsible for mapping it to ``fail_json`` (request id, error code).
        """
        def invoke():
            if request is not None:
                return operation(request)
            return operation()

        if not retry:
            return invoke()
        return retry_on(invoke, retries=self.params["retries"])
