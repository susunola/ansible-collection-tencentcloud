#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tcr_webhook_trigger
short_description: Create or delete a Tencent Cloud TCR webhook trigger
version_added: "1.1.0"
description:
  - Creates or deletes a Tencent Cloud Container Registry (TCR) webhook
    trigger inside a namespace, identified by its name. The module is
    idempotent; it reads the current webhook triggers in the registry before
    changing anything and matches on the trigger name and namespace.
  - The trigger payload is a raw SDK-shaped dictionary (the C(sub)fields of
    C(WebhookTrigger)) passed through verbatim, because the nested model mixes
    fuzzy enumeration values (C(Condition), C(EventTypes)) with free-form
    endpoint targets that do not map cleanly to Ansible suboptions. Provide at
    least C(Name) to identify the trigger; C(Description), C(Enabled),
    C(Condition), C(EventTypes) and C(Targets) are optional.
options:
  state:
    description: Desired state of the webhook trigger.
    type: str
    choices: [present, absent]
    default: present
  registry_id:
    description: ID of the TCR instance (registry) that owns the namespace.
    type: str
    required: true
  namespace:
    description: Name of the namespace the trigger applies to.
    type: str
    required: true
  trigger:
    description: Raw SDK-shaped webhook trigger payload (C(WebhookTrigger)).
    type: dict
    required: true
    suboptions:
      Name:
        description: Trigger name (used to identify the trigger).
        type: str
      Description:
        description: Trigger description.
        type: str
      Enabled:
        description: Whether the trigger is enabled.
        type: bool
      Condition:
        description: Trigger condition (e.g. C(all) or C(tag).
        type: str
      EventTypes:
        description: Event types that fire the trigger.
        type: list
        elements: str
      Targets:
        description: Delivery targets (endpoint addresses) for the trigger.
        type: list
        elements: str
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
  - susunola.tencentcloud.waiter
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Create a webhook trigger that fires on every push
  susunola.tencentcloud.tcr_webhook_trigger:
    registry_id: tcr-abc123
    namespace: production
    trigger:
      Name: push-notify
      Description: Notify on image push
      Enabled: true
      Condition: all
      EventTypes: [PUSH_IMAGE, DELETE_IMAGE]
      Targets: ["https://hooks.example.com/tcr"]

- name: Remove the webhook trigger
  susunola.tencentcloud.tcr_webhook_trigger:
    registry_id: tcr-abc123
    namespace: production
    trigger:
      Name: push-notify
    state: absent
'''

RETURN = r'''
registry_id:
  description: Registry ID the operation targeted.
  returned: always
  type: str
namespace:
  description: Namespace name the operation targeted.
  returned: always
  type: str
trigger_id:
  description: Server-assigned trigger ID after a create, or the matched trigger ID.
  returned: always
  type: str
exists:
  description: Whether the webhook trigger exists after the operation.
  returned: always
  type: bool
'''

import json

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def _load_tcr():
    from tencentcloud.tcr.v20190924 import models, tcr_client
    return models, tcr_client


def find_trigger(module, client, models, registry_id, namespace, name):
    request = models.DescribeWebhookTriggerRequest()
    request.RegistryId = registry_id
    request.Namespace = namespace
    request.Limit = 100
    request.Offset = 0
    response = module.sdk_call(client.DescribeWebhookTrigger, request)
    triggers = list(getattr(response, "Triggers", None) or [])
    for item in triggers:
        if getattr(item, "Name", None) == name and getattr(item, "NamespaceName", None) == namespace:
            return item
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "registry_id": {"type": "str", "required": True},
            "namespace": {"type": "str", "required": True},
            "trigger": {"type": "dict", "required": True},
        },
        supports_check_mode=True,
    )
    p = module.params
    registry_id = p["registry_id"]
    namespace = p["namespace"]
    trigger = p["trigger"] or {}
    name = trigger.get("Name")
    if not name:
        module.fail_json(msg="trigger.Name is required to identify a webhook trigger")
    desired_present = p["state"] == "present"
    module.require_sdk()
    models, tcr_client = _load_tcr()
    client = module.create_client(tcr_client.TcrClient, "tcr.tencentcloudapi.com")
    try:
        current = find_trigger(module, client, models, registry_id, namespace, name)
        if bool(current) == desired_present:
            module.exit_json(
                changed=False,
                registry_id=registry_id,
                namespace=namespace,
                trigger_id=getattr(current, "Id", None),
                exists=bool(current),
                msg="Webhook trigger already %s" % ("present" if desired_present else "absent"),
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                registry_id=registry_id,
                namespace=namespace,
                trigger_id=None,
                exists=desired_present,
                msg="Would %s webhook trigger" % ("create" if desired_present else "delete"),
            )
        if desired_present:
            payload = {"RegistryId": registry_id, "Namespace": namespace, "Trigger": trigger}
            request = models.CreateWebhookTriggerRequest()
            request.from_json_string(json.dumps(payload))
            module.sdk_call(client.CreateWebhookTrigger, request)
        else:
            request = models.DeleteWebhookTriggerRequest()
            request.Id = getattr(current, "Id", None)
            request.Namespace = namespace
            request.RegistryId = registry_id
            module.sdk_call(client.DeleteWebhookTrigger, request)
        final = find_trigger(module, client, models, registry_id, namespace, name)
        module.exit_json(
            changed=True,
            registry_id=registry_id,
            namespace=namespace,
            trigger_id=getattr(final, "Id", None) if final else None,
            exists=bool(final),
            msg="Webhook trigger %s" % ("created" if desired_present else "deleted"),
        )
    except Exception as exc:
        module.fail_sdk_error(exc, "Tencent Cloud TCR webhook trigger request failed")


def main():
    run_module()


if __name__ == "__main__":
    main()
