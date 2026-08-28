#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tcr_instance
short_description: Manage Tencent Cloud TCR enterprise instances
version_added: "0.13.0"
description:
  - Create, update and delete Tencent Cloud TCR (Tencent Container
    Registry) enterprise instances through the C(tcr.v20190924) API.
  - This module is idempotent. Running it twice leaves the instance
    unchanged and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
  - An instance is identified by O(registry_id) or by O(name). The instance
    type is only applied at creation; O(deletion_protection) is enforced on
    existing instances with V(ModifyInstance).
options:
  state:
    description:
      - C(present) creates the instance when it does not exist and enforces
        O(deletion_protection) on an existing instance.
      - C(absent) deletes the instance with V(DeleteInstance).
    type: str
    choices: [present, absent]
    default: present
  registry_id:
    description:
      - ID of an existing instance, e.g. C(tcr-xxxxxxxx).
      - When given, the module operates on that instance; otherwise it is
        matched by O(name).
    type: str
  name:
    description:
      - Name of the instance, written to
        V(CreateInstanceRequest.RegistryName).
      - Required when creating the instance.
    type: str
  registry_type:
    description:
      - Edition of the instance, written to
        V(CreateInstanceRequest.RegistryType).
      - C(basic) is the basic edition, C(standard) the standard edition,
        C(premium) the premium edition.
      - Required when creating the instance.
    type: str
    choices: [basic, standard, premium]
  deletion_protection:
    description:
      - Whether the deletion protection is enabled, written to
        V(CreateInstanceRequest.DeletionProtection) at creation and
        V(ModifyInstanceRequest.DeletionProtection) on existing instances.
    type: bool
    default: false
  period_months:
    description:
      - Prepaid period in months, written to
        V(RegistryChargePrepaid.Period).
      - When given the instance is billed prepaid; otherwise it is created
        postpaid.
      - Only applied at creation.
    type: int
  auto_renew:
    description:
      - Auto-renew flag for prepaid instances, written to
        V(RegistryChargePrepaid.RenewFlag).
      - C(0) renews manually, C(1) renews automatically, C(2) does not
        renew.
      - Only applied at creation.
    type: int
    choices: [0, 1, 2]
  sync_tag:
    description:
      - Sync the TCR tags to the backing COS bucket, written to
        V(CreateInstanceRequest.SyncTag).
      - Only applied at creation.
    type: bool
  enable_cos_maz:
    description:
      - Enable multi-AZ for the backing COS bucket, written to
        V(CreateInstanceRequest.EnableCosMAZ).
      - Only applied at creation.
    type: bool
  tags:
    description:
      - Tags to apply to the instance as a dict, for example I(env=prod).
      - Only applied at creation.
    type: dict
    default: {}
  retries:
    description: Number of retries for transient SDK failures.
    type: int
    default: 5
  waiter_delay:
    description: Seconds to wait between state-polling attempts.
    type: int
    default: 5
  waiter_timeout:
    description: Overall timeout in seconds for state polling.
    type: int
    default: 120
  user_agent:
    description:
      - Value appended to the SDK User-Agent header so API usage can be
        attributed to this collection.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-tcr) package on the controller.
  - TCR enterprise instances are billed while present; delete them as soon
    as they are no longer needed to avoid unnecessary charges.
  - O(state=absent) with deletion protection enabled fails at the API level;
    set O(deletion_protection=false) first.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a basic TCR enterprise instance
  susunola.tencentcloud.tcr_instance:
    region: ap-guangzhou
    state: present
    name: prod-registry
    registry_type: basic
    deletion_protection: true
    tags:
      env: prod

- name: Disable deletion protection before deleting
  susunola.tencentcloud.tcr_instance:
    region: ap-guangzhou
    state: present
    name: prod-registry
    registry_type: basic
    deletion_protection: false

- name: Delete the instance
  susunola.tencentcloud.tcr_instance:
    region: ap-guangzhou
    state: absent
    name: prod-registry
'''

RETURN = r'''
instance:
  description: The instance as reported by V(DescribeInstances) after the
    operation.
  returned: success
  type: dict
  sample:
    RegistryId: tcr-xxxxxxxx
    RegistryName: prod-registry
    RegistryType: basic
    Status: Running
    PublicDomain: prod-registry.tencentcloudcr.com
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_tcr():
    from tencentcloud.tcr.v20190924 import models, tcr_client
    return models, tcr_client


def build_describe_request(models, registry_id, name):
    request = models.DescribeInstancesRequest()
    request.Limit = 100
    if registry_id:
        request.Registryids = [registry_id]
    # The DescribeInstances filters do not carry a documented registry-name
    # key, so the caller filters the full page set by name instead.
    return request


def _first(collection):
    return collection[0] if collection else None


def _serialize(item):
    return item._serialize(allow_none=True)


def find_instance(module, client, models, registry_id, name):
    """Return the matching instance dict or None."""
    request = build_describe_request(models, registry_id, name)
    response = module.sdk_call(client.DescribeInstances, request)
    if registry_id:
        instance = _first(response.Registries or [])
        return _serialize(instance) if instance is not None else None
    for instance in response.Registries or []:
        current = _serialize(instance)
        if current.get("RegistryName") == name:
            return current
    return None


def build_create_request(models, params):
    request = models.CreateInstanceRequest()
    request.RegistryName = params["name"]
    request.RegistryType = params["registry_type"]
    request.DeletionProtection = params["deletion_protection"]
    if params["period_months"] is not None:
        prepaid = models.RegistryChargePrepaid()
        prepaid.Period = params["period_months"]
        if params["auto_renew"] is not None:
            prepaid.RenewFlag = params["auto_renew"]
        request.RegistryChargePrepaid = prepaid
    if params["sync_tag"] is not None:
        request.SyncTag = params["sync_tag"]
    if params["enable_cos_maz"] is not None:
        request.EnableCosMAZ = params["enable_cos_maz"]
    if params["tags"]:
        spec = models.TagSpecification()
        spec.ResourceType = "instance"
        spec.Tags = []
        for key, value in sorted(params["tags"].items()):
            sdk_tag = models.Tag()
            sdk_tag.Key = key
            sdk_tag.Value = value
            spec.Tags.append(sdk_tag)
        request.TagSpecification = spec
    return request


def _create(module, client, models, params):
    request = build_create_request(models, params)
    module.sdk_call(client.CreateInstance, request)


def _update(module, client, models, registry_id, deletion_protection):
    request = models.ModifyInstanceRequest()
    request.RegistryId = registry_id
    request.DeletionProtection = deletion_protection
    module.sdk_call(client.ModifyInstance, request)


def _delete(module, client, models, registry_id, delete_bucket):
    request = models.DeleteInstanceRequest()
    request.RegistryId = registry_id
    request.DeleteBucket = delete_bucket
    module.sdk_call(client.DeleteInstance, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "registry_id": {"type": "str"},
            "name": {"type": "str"},
            "registry_type": {"type": "str", "choices": ["basic", "standard", "premium"]},
            "deletion_protection": {"type": "bool", "default": False},
            "period_months": {"type": "int"},
            "auto_renew": {"type": "int", "choices": [0, 1, 2]},
            "sync_tag": {"type": "bool"},
            "enable_cos_maz": {"type": "bool"},
            "tags": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    registry_id = module.params["registry_id"]
    name = module.params["name"]

    if not registry_id and not name:
        module.fail_json(msg="registry_id or name is required to identify the instance")

    models, tcr_client = _load_tcr()
    client = module.create_client(tcr_client.TcrClient, "tcr.tencentcloudapi.com")

    try:
        current = find_instance(module, client, models, registry_id, name)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="TCR instance already absent")
        target_id = current["RegistryId"]
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete TCR instance")
        _delete(module, client, models, target_id, True)
        module.exit_json(changed=True, **(diff or {}), instance=None, msg="TCR instance deleted")

    # state == present
    if current is None:
        missing = [key for key in ("name", "registry_type") if not module.params[key]]
        if missing:
            module.fail_json(msg="%s is required when creating a TCR instance" % ", ".join(missing))
        desired = {
            "RegistryName": name,
            "RegistryType": module.params["registry_type"],
            "DeletionProtection": module.params["deletion_protection"],
        }
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would create TCR instance")
        _create(module, client, models, module.params)
        current = find_instance(module, client, models, None, name)
        module.exit_json(changed=True, **(diff or {}), instance=current, msg="TCR instance created")

    target_id = current["RegistryId"]
    current_protection = current.get("DeletionProtection")
    desired_protection = module.params["deletion_protection"]
    if current_protection != desired_protection:
        diff = maybe_diff(
            module,
            {"DeletionProtection": current_protection},
            {"DeletionProtection": desired_protection},
        )
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would update TCR deletion protection")
        _update(module, client, models, target_id, desired_protection)
        updated = find_instance(module, client, models, target_id, None)
        module.exit_json(changed=True, **(diff or {}), instance=updated, msg="TCR deletion protection updated")

    module.exit_json(changed=False, instance=current, msg="TCR instance is up to date")


def main():
    run_module()


if __name__ == "__main__":
    main()
