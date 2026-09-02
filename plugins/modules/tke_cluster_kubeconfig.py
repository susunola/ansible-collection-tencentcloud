#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tke_cluster_kubeconfig
short_description: Fetch the kubeconfig of a Tencent Cloud TKE cluster
version_added: "0.14.0"
description:
  - Fetch the kubeconfig of a TKE (Tencent Kubernetes Engine) cluster via
    the C(DescribeClusterKubeconfig) API.
  - When O(dest) is given the kubeconfig is written to that file with
    C(0600) permissions; rerunning with identical content reports
    C(changed=false). When O(dest) is omitted the kubeconfig is returned
    in the task result instead.
  - The API call itself is read-only; the module never modifies the
    cluster. Check mode reports whether the destination file would change.
options:
  cluster_id:
    description:
      - ID of the TKE cluster, e.g. C(cls-xxxxxxxx).
    type: str
    required: true
  is_extranet:
    description:
      - When C(true) the public-access (extranet) kubeconfig is returned;
        otherwise the private-access (intranet) kubeconfig is returned.
      - The corresponding access must be enabled on the cluster first (see
        the M(susunola.tencentcloud.tke_cluster_endpoint) module).
    type: bool
    default: false
  dest:
    description:
      - Local file path the kubeconfig is written to.
      - The file is created (or normalized) with C(0600) permissions because
        the kubeconfig carries cluster credentials.
      - When omitted, the kubeconfig is returned as the C(kubeconfig) return
        value; consider setting C(no_log) to C(true) on the task to keep the
        credentials out of logs.
    type: path
  retries:
    description:
      - Maximum number of retry attempts for throttled or transient API
        failures, using exponential backoff with jitter.
    type: int
    default: 5
  waiter_timeout:
    description:
      - Maximum time in seconds to wait for an asynchronous resource to reach
        the desired state.
    type: int
    default: 120
  waiter_delay:
    description: Interval in seconds between state polls while waiting.
    type: int
    default: 5
  user_agent:
    description:
      - User-Agent string sent with API requests.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - The kubeconfig contains cluster access credentials; protect task output
    with C(no_log) set to C(true) when O(dest) is not set.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Write the intranet kubeconfig of a cluster to a local file
  susunola.tencentcloud.tke_cluster_kubeconfig:
    region: ap-guangzhou
    cluster_id: cls-xxxxxxxx
    dest: ~/.kube/cls-xxxxxxxx.config

- name: Fetch the extranet kubeconfig into a variable
  susunola.tencentcloud.tke_cluster_kubeconfig:
    region: ap-guangzhou
    cluster_id: cls-xxxxxxxx
    is_extranet: true
  register: kubeconfig_result
  no_log: true
'''

RETURN = r'''
cluster_id:
  description: The cluster ID the kubeconfig belongs to.
  returned: success
  type: str
  sample: cls-xxxxxxxx
is_extranet:
  description: Whether the returned kubeconfig is the extranet one.
  returned: success
  type: bool
  sample: false
dest:
  description: File the kubeconfig was written to.
  returned: when O(dest) is given
  type: str
  sample: /home/user/.kube/cls-xxxxxxxx.config
kubeconfig:
  description:
    - The kubeconfig content. Contains cluster credentials.
    - Only returned when O(dest) is not set.
  returned: when O(dest) is omitted
  type: str
  sample: "apiVersion: v1"
'''

import errno
import hashlib
import os

from ansible.module_utils.common.text.converters import to_bytes

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_tke():
    from tencentcloud.tke.v20180525 import models, tke_client
    return models, tke_client


def build_request(models, cluster_id, is_extranet):
    request = models.DescribeClusterKubeconfigRequest()
    request.ClusterId = cluster_id
    request.IsExtranet = is_extranet
    return request


def fetch_kubeconfig(module, client, models, cluster_id, is_extranet):
    """Return the kubeconfig string reported by DescribeClusterKubeconfig."""
    request = build_request(models, cluster_id, is_extranet)
    response = module.sdk_call(client.DescribeClusterKubeconfig, request)
    return response.Kubeconfig


def _sha256(content):
    return hashlib.sha256(to_bytes(content)).hexdigest()


def _read_file(path):
    """Return the file content as text, or None when the file is absent."""
    try:
        with open(path, "rb") as handle:
            return handle.read().decode("utf-8")
    except IOError as exc:
        if exc.errno == errno.ENOENT:
            return None
        raise


def _write_kubeconfig(path, content):
    """Write the kubeconfig with 0600 permissions, normalizing existing files."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, to_bytes(content))
    finally:
        os.close(fd)
    # O_CREAT mode only applies to new files; chmod normalizes existing ones.
    os.chmod(path, 0o600)


def _file_state(path):
    """Diff-safe snapshot of the destination file (hash only, never content)."""
    content = _read_file(path)
    if content is None:
        return None
    return {"dest": path, "sha256": _sha256(content)}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "cluster_id": {"type": "str", "required": True},
            "is_extranet": {"type": "bool", "default": False},
            "dest": {"type": "path"},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    cluster_id = module.params["cluster_id"]
    is_extranet = module.params["is_extranet"]
    dest = module.params["dest"]

    models, tke_client = _load_tke()
    client = module.create_client(tke_client.TkeClient, "tke.tencentcloudapi.com")

    try:
        kubeconfig = fetch_kubeconfig(module, client, models, cluster_id, is_extranet)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    result = {"changed": False, "cluster_id": cluster_id, "is_extranet": is_extranet}

    if not dest:
        result["kubeconfig"] = kubeconfig
        module.exit_json(**result)

    current = _read_file(dest)
    if current == kubeconfig:
        result["dest"] = dest
        module.exit_json(**result, msg="Kubeconfig file is up to date")

    before = _file_state(dest)
    after = {"dest": dest, "sha256": _sha256(kubeconfig)}
    diff = maybe_diff(module, before, after)
    if module.check_mode:
        module.exit_json(changed=True, **(diff or {}), dest=dest, msg="Would write kubeconfig file")
    _write_kubeconfig(dest, kubeconfig)
    module.exit_json(changed=True, **(diff or {}), dest=dest, msg="Kubeconfig file written")


def main():
    run_module()


if __name__ == "__main__":
    main()
