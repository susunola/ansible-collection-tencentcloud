#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cls_alarm
short_description: Create or delete a Tencent Cloud CLS alarm
version_added: "1.1.0"
description:
  - Creates or deletes a Tencent Cloud CLS (Cloud Log Service) alarm policy,
    identified by its name. The module is idempotent; it reads the current
    alarms before changing anything and matches on the alarm name.
  - The alarm configuration is a raw SDK-shaped dictionary (the full
    C(AlarmInfo) / C(CreateAlarmRequest) body) passed through verbatim, because
    the alarm object is a large nested structure (monitor targets, conditions,
    callbacks, analysis) with no clean flat suboption set. The C(Name) field is
    forced to the module's top-level I(name) so the create and the idempotency
    lookup stay consistent.
options:
  state:
    description: Desired state of the alarm.
    type: str
    choices: [present, absent]
    default: present
  name:
    description: Alarm name, used to identify the alarm and as its C(Name).
    type: str
    required: true
  alarm:
    description: Raw SDK-shaped alarm configuration (the C(CreateAlarmRequest) body).
    type: dict
    required: true
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
- name: Create a CLS alarm that fires when error logs appear
  susunola.tencentcloud.cls_alarm:
    name: error-spike
    alarm:
      Name: error-spike
      MonitorObjectType: log
      MonitorTime:
        Type: Relative
        TimeGap: 600
      Condition: "$1.error_count > 10"
      AlarmTargets:
        - TopicId: "log-topic-abc"
      TriggerCount: 1

- name: Remove the alarm
  susunola.tencentcloud.cls_alarm:
    name: error-spike
    state: absent
'''

RETURN = r'''
name:
  description: Alarm name the operation targeted.
  returned: always
  type: str
alarm_id:
  description: Server-assigned alarm ID after a create, or the matched alarm ID.
  returned: always
  type: str
exists:
  description: Whether the alarm exists after the operation.
  returned: always
  type: bool
'''

import json

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def _load_cls():
    from tencentcloud.cls.v20201016 import models, cls_client
    return models, cls_client


def find_alarm(module, client, models, name):
    request = models.DescribeAlarmsRequest()
    flt = models.Filter()
    flt.Key = "name"
    flt.Values = [name]
    request.Filters = [flt]
    request.Limit = 100
    request.Offset = 0
    response = module.sdk_call(client.DescribeAlarms, request)
    alarms = list(getattr(response, "Alarms", None) or [])
    for item in alarms:
        if getattr(item, "Name", None) == name:
            return item
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "name": {"type": "str", "required": True},
            "alarm": {"type": "dict"},
        },
        required_if=[("state", "present", ("alarm",))],
        supports_check_mode=True,
    )
    p = module.params
    name = p["name"]
    alarm = p["alarm"] or {}
    desired_present = p["state"] == "present"
    module.require_sdk()
    models, cls_client = _load_cls()
    client = module.create_client(cls_client.ClsClient, "cls.tencentcloudapi.com")
    try:
        current = find_alarm(module, client, models, name)
        if bool(current) == desired_present:
            module.exit_json(
                changed=False,
                name=name,
                alarm_id=getattr(current, "AlarmId", None),
                exists=bool(current),
                msg="CLS alarm already %s" % ("present" if desired_present else "absent"),
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                name=name,
                alarm_id=None,
                exists=desired_present,
                msg="Would %s CLS alarm" % ("create" if desired_present else "delete"),
            )
        if desired_present:
            payload = dict(alarm)
            payload["Name"] = name
            request = models.CreateAlarmRequest()
            request.from_json_string(json.dumps(payload))
            response = module.sdk_call(client.CreateAlarm, request)
            created_id = getattr(response, "AlarmId", None)
        else:
            request = models.DeleteAlarmRequest()
            request.AlarmId = getattr(current, "AlarmId", None)
            module.sdk_call(client.DeleteAlarm, request)
            created_id = None
        final = find_alarm(module, client, models, name)
        module.exit_json(
            changed=True,
            name=name,
            alarm_id=created_id if desired_present else (getattr(final, "AlarmId", None) if final else None),
            exists=bool(final),
            msg="CLS alarm %s" % ("created" if desired_present else "deleted"),
        )
    except Exception as exc:
        module.fail_sdk_error(exc, "Tencent Cloud CLS alarm request failed")


def main():
    run_module()


if __name__ == "__main__":
    main()
