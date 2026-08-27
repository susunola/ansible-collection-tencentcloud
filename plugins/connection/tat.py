# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""TAT connection plugin: run commands and transfer files over the Tencent
Automation Tools (TAT) agent, no public IP or SSH required.

The plugin executes every command through the C(tat.v20201028) API:
``CreateCommand`` + ``InvokeCommand`` on the target instance, polling
``DescribeInvocationTasks`` until the task reaches a terminal state. It is
meant for instances that cannot be reached over SSH directly — e.g. CVM or
Lighthouse instances behind a NAT gateway with no public IP, where only the
TAT agent (outbound HTTPS to ``tat.tencentcloudapi.com``) is reachable.

Files are transferred by streaming base64 chunks into an ``echo``-based
append command, then decoding in place; ``fetch_file`` streams the remote
file back the same way in reverse.
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
name: tat
short_description: Execute commands and transfer files on Tencent Cloud instances via TAT
version_added: "0.12.0"
description:
  - Run commands and transfer files on Tencent Cloud CVM and Lighthouse
    instances through the Tencent Automation Tools (TAT) agent.
  - Requires the C(tencentcloud-sdk-python-tat) package on the controller
    and the TAT agent running on the target instance.
  - The instance does not need a public IP or a reachable SSH port; only
    outbound HTTPS from the instance to C(tat.tencentcloudapi.com) is used.
  - Commands run as the TAT agent user, which is C(root) on the standard
    Linux agent. When privilege escalation (become) is enabled with a
    different user, the requested user is passed to V(InvokeCommandRequest.Username).
  - The connection is stateless; every command execution creates a fresh
    command. Commands are named C(ansible-tat-<sha1-prefix>) so they can be
    correlated in the TAT console.
options:
  instance_id:
    description:
      - ID of the target instance, e.g. C(ins-xxxxxxxx) (CVM) or
        C(lhins-xxxxxxxx) (Lighthouse).
      - Required. Set it with the C(ansible_tat_instance_id) variable or in
        the play's connection options.
    type: str
    required: true
  command_type:
    description:
      - Script type passed to V(CreateCommandRequest.Type).
      - Use C(POWERSHELL) for Windows targets.
    type: str
    choices: [SHELL, POWERSHELL]
    default: SHELL
  working_directory:
    description:
      - Directory the command runs in, passed to
        V(CreateCommandRequest.WorkingDirectory).
    type: str
    default: /root
  command_timeout:
    description:
      - Per-command timeout in seconds, passed to
        V(CreateCommandRequest.Timeout).
    type: int
    default: 60
  poll_interval:
    description: Seconds to wait between V(DescribeInvocationTasks) polls.
    type: int
    default: 2
  poll_timeout:
    description:
      - Overall time in seconds to keep polling before failing. Must be
        larger than O(command_timeout).
    type: int
    default: 300
  max_command_chars:
    description:
      - Upper bound for a single command payload. Commands (and file
        transfer chunks) longer than this fail instead of being silently
        truncated by the API.
    type: int
    default: 60000
notes:
  - The TAT API returns at most 64 KiB of output per invocation; longer
    command output is truncated server-side.
  - Because every command is a fresh TAT command, connection-oriented
    features that assume an interactive shell (e.g. ``environment``
    persistence between commands) are not supported. Set what the command
    needs inside the command itself.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Run an ad-hoc command over TAT without a public IP
  hosts: all
  connection: susunola.tencentcloud.tat
  vars:
    ansible_tat_instance_id: ins-xxxxxxxx
    ansible_tat_region: ap-guangzhou
  tasks:
    - ansible.builtin.shell: |
        uptime && df -h / | tail -1

- name: Configure TAT as the default connection in a play
  hosts: tat_hosts
  connection: susunola.tencentcloud.tat
  vars:
    ansible_tat_instance_id: "{{ inventory_hostname }}"
    ansible_tat_command_timeout: 120
    ansible_tat_working_directory: /home/app
  tasks:
    - ansible.builtin.copy:
        src: app.service
        dest: /etc/systemd/system/app.service
    - ansible.builtin.systemd:
        name: app
        state: restarted
'''

import base64
import hashlib
import os
import time

from ansible.errors import AnsibleConnectionFailure
from ansible.plugins.connection import ConnectionBase
from ansible.utils.display import Display

from ansible_collections.susunola.tencentcloud.plugins.module_utils.client import (
    HAS_TENCENTCLOUD_SDK,
    load_profile,
)

display = Display()

_TERMINAL_TASK_STATES = (
    "SUCCESS",
    "FAILED",
    "TIMEOUT",
    "PARTIAL_FAILED",
    "TERMINATED",
    "CANCELED",
)

_TERMINAL_COMMAND_STATES = _TERMINAL_TASK_STATES


class _OptionAdapter(object):
    """Expose connection options under a module-like ``params`` mapping.

    Lets the shared ``module_utils.client`` helpers resolve credentials,
    region and profiles without importing an actual Ansible module.
    """

    def __init__(self, connection, region=None):
        self._connection = connection
        self.params = {}
        for name in (
            "secret_id", "secret_key", "token", "role_arn",
            "role_session_name", "role_session_duration", "profile",
            "region", "endpoint", "timeout",
        ):
            try:
                self.params[name] = connection.get_option(name)
            except KeyError:
                self.params[name] = None
        if region is not None:
            self.params["region"] = region

    def fail_json(self, **kwargs):
        raise AnsibleConnectionFailure(kwargs.get("msg", "TAT connection failed"))


class Connection(ConnectionBase):
    """TAT connection over the Tencent Cloud Automation Tools agent."""

    transport = "susunola.tencentcloud.tat"
    has_pipelining = False
    default_user = "root"

    def __init__(self, play_context, new_stdin=None, *args, **kwargs):
        super(Connection, self).__init__(play_context, new_stdin, *args, **kwargs)
        self._connected = False
        self._client = None
        self._models = None
        self._instance_id = None
        self._command_cache = {}
        self._command_cache_order = []

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------

    def _option(self, name, default=None):
        try:
            value = self.get_option(name)
        except KeyError:
            return default
        return value if value not in (None, "") else default

    def _build_client(self):
        """Build the TAT SDK client, resolving credentials like modules do."""
        secret_id = self._option("secret_id") or os.environ.get("TENCENTCLOUD_SECRET_ID")
        secret_key = self._option("secret_key") or os.environ.get("TENCENTCLOUD_SECRET_KEY")
        token = self._option("token") or os.environ.get("TENCENTCLOUD_TOKEN")
        profile = {}
        if not secret_id or not secret_key:
            profile = load_profile(self._option("profile"))
            secret_id = secret_id or profile.get("secret_id")
            secret_key = secret_key or profile.get("secret_key")
        if not secret_id or not secret_key:
            raise AnsibleConnectionFailure(
                "Set secret_id/secret_key (or TENCENTCLOUD_SECRET_ID/KEY), or the "
                "secret_id/secret_key keys of a profile in ~/.tencentcloud/default.configure"
            )
        region = (
            self._option("region")
            or os.environ.get("TENCENTCLOUD_REGION")
            or profile.get("region")
        )
        if not region:
            raise AnsibleConnectionFailure(
                "Set the region (or TENCENTCLOUD_REGION), or the region key of a "
                "profile in ~/.tencentcloud/default.configure"
            )

        if not HAS_TENCENTCLOUD_SDK:
            raise AnsibleConnectionFailure(
                "The tencentcloud-sdk-python package is required on the Ansible controller"
            )
        try:
            from tencentcloud.common import credential as tc_credential
            from tencentcloud.common.profile.client_profile import ClientProfile
            from tencentcloud.common.profile.http_profile import HttpProfile
            from tencentcloud.tat.v20201028 import models, tat_client
        except ImportError as exc:
            raise AnsibleConnectionFailure(
                "The tencentcloud-sdk-python-tat package is required: %s" % exc
            )

        credential = tc_credential.Credential(secret_id, secret_key, token)
        http_profile = HttpProfile()
        http_profile.endpoint = self._option("endpoint") or "tat.tencentcloudapi.com"
        http_profile.reqTimeout = self._option("timeout", 60)
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        client_profile.language = "en-US"
        return tat_client.TatClient(credential, region, client_profile), models

    def _connect(self):
        if self._connected:
            return self
        self._instance_id = self._option("instance_id")
        if not self._instance_id:
            raise AnsibleConnectionFailure(
                "instance_id is required for the tat connection; set ansible_tat_instance_id"
            )
        self._client, self._models = self._build_client()
        self._connected = True
        return self

    def close(self):
        self._connected = False
        self._client = None
        self._command_cache = {}
        self._command_cache_order = []

    def reset(self):
        self.close()
        return self

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    def _api(self, operation, request, what):
        try:
            return operation(request)
        except Exception as exc:
            request_id = getattr(exc, "get_request_id", lambda: None)()
            detail = " (request_id=%s)" % request_id if request_id else ""
            raise AnsibleConnectionFailure(
                "TAT %s failed: %s%s" % (what, exc, detail)
            )

    def _ensure_command(self, content, username):
        """Create (or reuse) a TAT command for the given content."""
        cache_key = (username, content)
        cached = self._command_cache.get(cache_key)
        if cached is not None:
            return cached
        if len(content) > self._option("max_command_chars", 60000):
            raise AnsibleConnectionFailure(
                "Command payload of %d chars exceeds max_command_chars; split the task"
                % len(content)
            )
        models = self._models
        request = models.CreateCommandRequest()
        digest = hashlib.sha1(content.encode("utf-8")).hexdigest()[:8]
        request.CommandName = "ansible-tat-%s" % digest
        request.Type = self._option("command_type", "SHELL")
        request.Content = content
        request.WorkingDirectory = self._option("working_directory", "/root")
        request.Timeout = self._option("command_timeout", 60)
        if username and username != "root":
            request.Username = username
        response = self._api(self._client.CreateCommand, request, "CreateCommand")
        command_id = response.CommandId
        if not command_id:
            raise AnsibleConnectionFailure("CreateCommand returned no CommandId")
        self._command_cache[cache_key] = command_id
        self._command_cache_order.append(cache_key)
        if len(self._command_cache) > 8:
            oldest = self._command_cache_order.pop(0)
            self._command_cache.pop(oldest, None)
        return command_id

    def _invoke(self, command_id, username):
        models = self._models
        request = models.InvokeCommandRequest()
        request.CommandId = command_id
        request.InstanceIds = [self._instance_id]
        if username and username != "root":
            request.Username = username
        response = self._api(self._client.InvokeCommand, request, "InvokeCommand")
        task_ids = response.InvocationTaskIdSet or []
        if not task_ids:
            raise AnsibleConnectionFailure("InvokeCommand returned no task IDs")
        return task_ids[0]

    def _poll_task(self, task_id):
        """Poll until the invocation task is terminal; return (rc, output)."""
        models = self._models
        poll_interval = self._option("poll_interval", 2)
        poll_timeout = self._option("poll_timeout", 300)
        deadline = time.time() + poll_timeout
        while True:
            request = models.DescribeInvocationTasksRequest()
            request.InvocationTaskIds = [task_id]
            response = self._api(
                self._client.DescribeInvocationTasks, request, "DescribeInvocationTasks"
            )
            tasks = response.InvocationTaskSet or []
            if not tasks:
                raise AnsibleConnectionFailure(
                    "DescribeInvocationTasks returned no task for %s" % task_id
                )
            task = tasks[0]
            state = task.TaskStatus
            if state in _TERMINAL_TASK_STATES:
                result = task.TaskResult
                exit_code = getattr(result, "ExitCode", 1) if result else 1
                output = getattr(result, "Output", "") if result else ""
                error = getattr(result, "ErrorMsg", None) if result else None
                if error:
                    output = "%s\n%s" % (output, error)
                if state == "SUCCESS" and exit_code == 0:
                    return 0, output
                # FAILED/TIMEOUT/PARTIAL_FAILED carry a non-zero exit code or
                # a failed state; the module runner treats non-zero as error.
                return exit_code, output
            if time.time() > deadline:
                raise AnsibleConnectionFailure(
                    "TAT invocation %s still in state %s after %ds"
                    % (task_id, state, poll_timeout)
                )
            time.sleep(poll_interval)

    def _become_username(self):
        """Return the user commands should run as, or None for the agent user."""
        if not self._play_context.become:
            return None
        return self._play_context.become_user or self.default_user

    def exec_command(self, cmd, in_data=None, sudoable=True):
        """Run a command over TAT and return (rc, stdout, stderr)."""
        self._connect()

        if in_data:
            payload = base64.b64encode(in_data).decode("ascii")
            decoded_path = "/tmp/ansible_stdin_%d" % os.getpid()
            cmd = (
                "printf '%s' | base64 -d > %s\n%s" % (payload, decoded_path, cmd)
            )
        username = self._become_username()
        command_id = self._ensure_command(cmd, username)
        task_id = self._invoke(command_id, username)
        display.vvv("TAT invocation %s on %s" % (task_id, self._instance_id))
        return_code, output = self._poll_task(task_id)
        return return_code, output, ""

    # ------------------------------------------------------------------
    # File transfer
    # ------------------------------------------------------------------

    def put_file(self, in_path, out_path):
        """Copy a local file to the instance by streaming base64 chunks."""
        self._connect()
        with open(in_path, "rb") as handle:
            data = handle.read()
        encoded = base64.b64encode(data).decode("ascii")
        max_chars = min(self._option("max_command_chars", 60000), 24000)
        remote_b64_path = "%s.tc-b64" % out_path
        first = True
        for offset in range(0, len(encoded), max_chars):
            chunk = encoded[offset:offset + max_chars]
            if first:
                # Truncate any leftovers from an interrupted transfer, then write.
                command = (
                    "printf '%%s\\n' '%s' > '%s'" % (chunk, remote_b64_path)
                )
            else:
                command = (
                    "printf '%%s\\n' '%s' >> '%s'" % (chunk, remote_b64_path)
                )
            return_code, stdout, stderr = self.exec_command(command)
            if return_code != 0:
                raise AnsibleConnectionFailure(
                    "Failed to transfer %s (rc=%s): %s"
                    % (in_path, return_code, stderr or stdout)
                )
            first = False
        # Decode into place with an atomic rename; drop the base64 staging file.
        decode_command = (
            "base64 -d < '%s' > '%s.tmp' && mv '%s.tmp' '%s' && rm -f '%s'"
            % (remote_b64_path, out_path, out_path, out_path, remote_b64_path)
        )
        return_code, stdout, stderr = self.exec_command(decode_command)
        if return_code != 0:
            raise AnsibleConnectionFailure(
                "Failed to decode %s (rc=%s): %s" % (out_path, return_code, stderr or stdout)
            )

    def fetch_file(self, in_path, out_path):
        """Copy a remote file to the controller via base64 streaming."""
        self._connect()
        command = "base64 -w0 < '%s'" % in_path
        return_code, stdout, stderr = self.exec_command(command)
        if return_code != 0:
            raise AnsibleConnectionFailure(
                "Failed to read remote file %s (rc=%s): %s"
                % (in_path, return_code, stderr or stdout)
            )
        try:
            data = base64.b64decode(stdout.encode("ascii"))
        except Exception as exc:
            raise AnsibleConnectionFailure(
                "Remote file %s did not return valid base64: %s" % (in_path, exc)
            )
        directory = os.path.dirname(os.path.abspath(out_path))
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        with open(out_path, "wb") as handle:
            handle.write(data)
