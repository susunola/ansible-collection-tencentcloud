#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
DOCUMENTATION = r'''
---
module: lighthouse_key_pair
short_description: Manage imported Tencent Cloud Lighthouse SSH key pairs
version_added: "0.14.0"
description: Imports and deletes Lighthouse public SSH keys and reconciles their exact instance associations.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  key_id: {type: str, description: Existing key pair ID; preferred for replacement and deletion.}
  name: {type: str, description: Immutable key pair name.}
  public_key: {type: str, description: OpenSSH public key imported when the key does not exist.}
  instance_ids: {type: list, elements: str, default: [], description: Exact set of Lighthouse instances associated with the key.}
  association_type: {type: str, choices: [ONLINE, OFFLINE], default: ONLINE, description: Whether association operations may run without shutting down instances.}
  username: {type: str, description: Operating-system username for online association and disassociation.}
  force_replace: {type: bool, default: false, description: "Disassociate, delete and re-import when immutable name or public key differs."}
  force_delete: {type: bool, default: false, description: Disassociate every instance before deleting the key pair.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.lighthouse_key_pair:
    name: production-automation
    public_key: "{{ lookup('ansible.builtin.file', '~/.ssh/id_ed25519.pub') }}"
    instance_ids: [lhins-xxxxxxxx, lhins-yyyyyyyy]
    association_type: ONLINE
    username: root
'''
RETURN = r'''key_pair: {description: Lighthouse key pair metadata., type: dict, returned: always}'''
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.lighthouse.v20200324 import models, lighthouse_client
    return models, lighthouse_client
def describe_request(models, p, offset=0):
    request = models.DescribeKeyPairsRequest(); request.Offset, request.Limit = offset, 100
    if p.get("key_id"): request.KeyIds = [p["key_id"]]
    return request
def import_request(models, p):
    request = models.ImportKeyPairRequest(); request.KeyName, request.PublicKey = p["name"], p["public_key"].strip(); return request
def delete_request(models, key_id):
    request = models.DeleteKeyPairsRequest(); request.KeyIds = [key_id]; return request
def associate_request(models, p, key_id, instance_ids):
    request = models.AssociateInstancesKeyPairsRequest(); request.KeyIds, request.InstanceIds, request.AssociateType = [key_id], sorted(instance_ids), p["association_type"]
    if p.get("username") and p["association_type"] == "ONLINE": request.Username = p["username"]
    return request
def disassociate_request(models, p, key_id, instance_ids):
    request = models.DisassociateInstancesKeyPairsRequest(); request.KeyIds, request.InstanceIds, request.DisassociateType = [key_id], sorted(instance_ids), p["association_type"]
    if p.get("username") and p["association_type"] == "ONLINE": request.Username = p["username"]
    return request
def _instances(value): return sorted(value.get("AssociatedInstanceIds") or [item.get("InstanceId") for item in (value.get("AssociatedInstanceSet") or []) if item.get("InstanceId")])
def comparable(value): return {"KeyName": value.get("KeyName"), "PublicKey": (value.get("PublicKey") or "").strip(), "InstanceIds": _instances(value)}
def desired(p): return {"KeyName": p["name"], "PublicKey": p["public_key"].strip(), "InstanceIds": sorted(p["instance_ids"])}
def find(module, client, models, p):
    offset = 0; matches = []
    while True:
        response = module.sdk_call(client.DescribeKeyPairs, describe_request(models, p, offset)); values = list(response.KeyPairSet or [])
        for item in values:
            value = item._serialize(allow_none=True)
            if (p.get("key_id") and value.get("KeyId") == p["key_id"]) or (not p.get("key_id") and value.get("KeyName") == p.get("name")): matches.append(value)
        offset += len(values)
        if offset >= int(response.TotalCount or 0) or not values: break
    if len(matches) > 1: module.fail_json(msg="Multiple Lighthouse key pairs matched; specify key_id")
    return matches[0] if matches else None
def remove(module, client, models, p, current):
    bound = _instances(current)
    if bound: module.sdk_call(client.DisassociateInstancesKeyPairs, disassociate_request(models, p, current["KeyId"], bound))
    module.sdk_call(client.DeleteKeyPairs, delete_request(models, current["KeyId"]))


def run_module():
    module = TencentCloudModule(argument_spec={"state": {"choices": ["present", "absent"], "default": "present"}, "key_id": {}, "name": {}, "public_key": {}, "instance_ids": {"type": "list", "elements": "str", "default": []}, "association_type": {"choices": ["ONLINE", "OFFLINE"], "default": "ONLINE"}, "username": {}, "force_replace": {"type": "bool", "default": False}, "force_delete": {"type": "bool", "default": False}}, required_one_of=[("key_id", "name")], supports_check_mode=True)
    p = module.params
    if p["state"] == "present" and (not p["name"] or not p["public_key"]): module.fail_json(msg="name and public_key are required when state=present")
    module.require_sdk(); models, cm = _load(); client = module.create_client(cm.LighthouseClient, "lighthouse.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current: module.exit_json(changed=False, key_pair=None)
            bound = _instances(current)
            if bound and not p["force_delete"]: module.fail_json(msg="key pair is associated with instances; set force_delete=true to disassociate and delete", instance_ids=bound)
            diff = maybe_diff(module, comparable(current), None)
            if not module.check_mode: remove(module, client, models, p, current)
            module.exit_json(changed=True, **(diff or {}), key_pair=current if module.check_mode else None)
        target = desired(p); before = comparable(current) if current else None; replace = bool(current and (before["KeyName"] != target["KeyName"] or before["PublicKey"] != target["PublicKey"]))
        if replace and not p["force_replace"]: module.fail_json(msg="name and public_key are immutable; set force_replace=true to disassociate and re-import")
        if before == target: module.exit_json(changed=False, key_pair=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if replace: remove(module, client, models, p, current); current = None
            if not current: p["key_id"] = module.sdk_call(client.ImportKeyPair, import_request(models, p)).KeyId; current = find(module, client, models, p)
            old_ids, new_ids = set(_instances(current)), set(p["instance_ids"])
            if old_ids - new_ids: module.sdk_call(client.DisassociateInstancesKeyPairs, disassociate_request(models, p, current["KeyId"], old_ids - new_ids))
            if new_ids - old_ids: module.sdk_call(client.AssociateInstancesKeyPairs, associate_request(models, p, current["KeyId"], new_ids - old_ids))
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), key_pair=current)
    except Exception as exc: module.fail_json(**sdk_error_payload(exc))


def main(): run_module()
if __name__ == "__main__": main()
