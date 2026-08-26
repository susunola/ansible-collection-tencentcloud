#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: key_pair
short_description: Manage Tencent Cloud CVM key pairs
version_added: "0.4.0"
description:
  - Create, import, and delete Tencent Cloud CVM key pairs (SSH keys).
  - This module is idempotent. Running it twice leaves the resource unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  state:
    description:
      - C(present) creates the key pair if it does not exist. When
        O(public_key) is given the key pair is imported with
        C(ImportKeyPair), otherwise a new key pair is generated with
        C(CreateKeyPair) and the private key is returned once.
      - C(absent) deletes the key pair if it exists. Deleting a key pair that
        does not exist is treated as success.
    type: str
    choices: [present, absent]
    default: present
  key_id:
    description:
      - ID of an existing key pair, e.g. C(skey-xxxxxxxx).
      - When given, the module matches the key pair by ID; otherwise it is
        matched by O(name).
    type: str
  name:
    description:
      - Name of the key pair. Required when C(state=present).
      - May contain digits, letters and underscores, at most 25 characters,
        and must be unique in the region.
    type: str
  public_key:
    description:
      - Public key material in C(OpenSSH RSA) format. When given, the key
        pair is imported instead of generated.
      - Only used at creation; the public key of an existing key pair is
        never modified.
    type: str
  project_id:
    description:
      - Project ID the key pair belongs to. Only applied at creation;
        changing it after creation is a no-op (the API does not support it).
    type: int
    default: 0
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
    default: ansible-collection/tencentcloud.cloud
notes:
  - Requires the C(tencentcloud-sdk-python-cvm) package on the controller.
  - Key pairs are immutable after creation; name, project and public key
    cannot be modified through the API. To change any of them, delete the key
    pair and create it again.
  - The generated V(private_key) is only returned once, at creation time, when
    O(public_key) is not given. Tencent Cloud does not store the private key;
    save it immediately (for example with the C(copy) module and
    C(no_log=true)).
  - Uses the C(cvm.tencentcloudapi.com) endpoint by default.
extends_documentation_fragment: tencentcloud.cloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a key pair (private key returned once)
  tencentcloud.cloud.key_pair:
    region: ap-guangzhou
    state: present
    name: deploy-key
  register: generated_key
  no_log: true

- name: Save the generated private key
  ansible.builtin.copy:
    content: "{{ generated_key.private_key }}"
    dest: ~/.ssh/deploy-key.pem
    mode: "0600"
  no_log: true
  when: generated_key.private_key is defined

- name: Import an existing public key
  tencentcloud.cloud.key_pair:
    region: ap-guangzhou
    state: present
    name: deploy-key
    public_key: "ssh-rsa AAAA..."

- name: Delete a key pair
  tencentcloud.cloud.key_pair:
    region: ap-guangzhou
    state: absent
    name: deploy-key
'''

RETURN = r'''
key_pair:
  description: The key pair as reported by the API after the operation.
  returned: success
  type: dict
  sample:
    KeyId: skey-xxxxxxxx
    KeyName: deploy-key
    ProjectId: 0
    PublicKey: ssh-rsa AAAA...
    AssociatedInstanceIds: []
    CreatedTime: "2026-08-26T12:00:00Z"
private_key:
  description:
    - The generated private key in PEM format.
    - Only returned when the module created the key pair (C(CreateKeyPair)),
      i.e. on a run with C(state=present), no O(public_key) given, and the
      key pair did not already exist. Sensitive; treat it like a password.
  returned: when a key pair is generated
  type: str
  sample: "-----BEGIN RSA PRIVATE KEY-----\n..."
'''

from ansible_collections.tencentcloud.cloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.tencentcloud.cloud.plugins.module_utils.comparison import build_diff
from ansible_collections.tencentcloud.cloud.plugins.module_utils.errors import (
    is_idempotent_success,
)


def _load_cvm():
    from tencentcloud.cvm.v20170312 import models, cvm_client
    return models, cvm_client


def build_describe_request(models, name, key_id):
    request = models.DescribeKeyPairsRequest()
    request.Limit = 100
    if key_id:
        request.KeyIds = [key_id]
    if name and not key_id:
        name_filter = models.Filter()
        name_filter.Name = "key-name"
        name_filter.Values = [name]
        request.Filters = [name_filter]
    return request


def _first(collection):
    return collection[0] if collection else None


def find_key_pair(module, client, models, name, key_id):
    """Return the matching key pair dict or None."""
    request = build_describe_request(models, name, key_id)
    response = module.sdk_call(client.DescribeKeyPairs, request)
    key_pair = _first(response.KeyPairSet or [])
    if key_pair is None:
        return None
    return key_pair._serialize(allow_none=True)


def _create(module, client, models, name, project_id):
    """Generate a new key pair; the response carries the private key."""
    request = models.CreateKeyPairRequest()
    request.KeyName = name
    request.ProjectId = project_id
    response = module.sdk_call(client.CreateKeyPair, request)
    key_pair = response.KeyPair._serialize(allow_none=True)
    private_key = key_pair.pop("PrivateKey", None)
    return key_pair, private_key


def _import(module, client, models, name, project_id, public_key):
    """Import an existing public key; no private key is returned."""
    request = models.ImportKeyPairRequest()
    request.KeyName = name
    request.ProjectId = project_id
    request.PublicKey = public_key
    response = module.sdk_call(client.ImportKeyPair, request)
    return response.KeyId


def _delete(module, client, models, key_id):
    request = models.DeleteKeyPairsRequest()
    request.KeyIds = [key_id]
    module.sdk_call(client.DeleteKeyPairs, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "key_id": {"type": "str"},
            "name": {"type": "str"},
            "public_key": {"type": "str"},
            "project_id": {"type": "int", "default": 0},
        },
        required_if=[("state", "present", ["name"])],
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    key_id = module.params["key_id"]
    name = module.params["name"]
    public_key = module.params["public_key"]
    project_id = module.params["project_id"]

    if state == "absent" and not name and not key_id:
        module.fail_json(msg="name or key_id is required when state=absent")

    models, cvm_client = _load_cvm()
    client = module.create_client(cvm_client.CvmClient, "cvm.tencentcloudapi.com")

    try:
        current = find_key_pair(module, client, models, name, key_id)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="Key pair already absent")
        diff = build_diff(current, None)
        if module.check_mode:
            module.exit_json(changed=True, diff=diff, msg="Would delete key pair")
        try:
            _delete(module, client, models, current["KeyId"])
        except Exception as exc:
            if is_idempotent_success(exc):
                module.exit_json(changed=True, diff=diff, msg="Key pair deleted")
            raise
        module.exit_json(changed=True, diff=diff, key_pair=None, msg="Key pair deleted")

    # state == present
    desired = {"name": name, "project_id": project_id}
    if current is None:
        diff = build_diff(None, desired)
        if module.check_mode:
            module.exit_json(changed=True, diff=diff, msg="Would create key pair")
        if public_key:
            new_key_id = _import(module, client, models, name, project_id, public_key)
            created = find_key_pair(module, client, models, None, new_key_id)
            module.exit_json(changed=True, diff=diff, key_pair=created, msg="Key pair imported")
        created, private_key = _create(module, client, models, name, project_id)
        module.exit_json(
            changed=True, diff=diff, key_pair=created, private_key=private_key,
            msg="Key pair created",
        )

    module.exit_json(
        changed=False, key_pair=current,
        msg="Key pair is up to date (key pairs are immutable after creation)",
    )


def main():
    run_module()


if __name__ == "__main__":
    main()
