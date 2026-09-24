#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cls_alarm_notice
short_description: Create or delete a Tencent Cloud CLS alarm notice (notification channel group)
version_added: "1.1.0"
description:
  - Creates or deletes a Tencent Cloud CLS (Cloud Log Service) alarm notice
    (notification channel group), identified by its name. The module is
    idempotent; it reads the current alarm notices before changing anything and
    matches on the notice name.
  - The notice configuration is a raw SDK-shaped dictionary (the full
    C(CreateAlarmNoticeRequest) body) passed through verbatim, because the
    notice object is a large nested structure (simple/advanced receivers,
    web callbacks, delivery config) with no clean flat suboption set. The
    C(Name) field is forced to the module's top-level I(name) so the create and
    the idempotency lookup stay consistent.
options:
  state:
    description: Desired state of the alarm notice.
    type: str
    choices: [present, absent]
    default: present
  name:
    description: Alarm notice name, used to identify the notice and as its C(Name).
    type: str
    required: true
  notice:
    description:
      - Raw SDK-shaped alarm notice configuration (the C(CreateAlarmNoticeRequest) body).
      - The receiver entries are validated server-side. C(ReceiverType) accepts
        only C(Uin) and C(Group), C(ReceiverIds) is a list of B(int64) (not
        strings), and C(StartTime) / C(EndTime) are mandatory and formatted
        C(15:04:05).
    type: dict
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
- name: Create a CLS alarm notice that emails the on-call team
  susunola.tencentcloud.cls_alarm_notice:
    name: oncall-email
    notice:
      Name: oncall-email
      Type: All
      NoticeReceivers:
        # ReceiverType is Uin (account/子用户 uid) or Group (CAM group id);
        # ReceiverIds are int64 values, not strings.
        - ReceiverType: Uin
          ReceiverIds:
            - 1137546
          ReceiverChannels:
            - Email
          StartTime: "00:00:00"
          EndTime: "23:59:59"

- name: Remove the alarm notice
  susunola.tencentcloud.cls_alarm_notice:
    name: oncall-email
    state: absent
'''

RETURN = r'''
name:
  description: Alarm notice name the operation targeted.
  returned: always
  type: str
alarm_notice_id:
  description: Server-assigned alarm notice ID after a create, or the matched notice ID.
  returned: always
  type: str
exists:
  description: Whether the alarm notice exists after the operation.
  returned: always
  type: bool
'''

import json

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def _load_cls():
    from tencentcloud.cls.v20201016 import models, cls_client
    return models, cls_client


def find_notice(module, client, models, name):
    request = models.DescribeAlarmNoticesRequest()
    flt = models.Filter()
    flt.Key = "name"
    flt.Values = [name]
    request.Filters = [flt]
    request.Limit = 100
    request.Offset = 0
    response = module.sdk_call(client.DescribeAlarmNotices, request)
    notices = list(getattr(response, "AlarmNotices", None) or [])
    for item in notices:
        if getattr(item, "Name", None) == name:
            return item
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "name": {"type": "str", "required": True},
            "notice": {"type": "dict"},
        },
        required_if=[("state", "present", ("notice",))],
        supports_check_mode=True,
    )
    p = module.params
    name = p["name"]
    notice = p["notice"] or {}
    desired_present = p["state"] == "present"
    module.require_sdk()
    models, cls_client = _load_cls()
    client = module.create_client(cls_client.ClsClient, "cls.tencentcloudapi.com")
    try:
        current = find_notice(module, client, models, name)
        if bool(current) == desired_present:
            module.exit_json(
                changed=False,
                name=name,
                alarm_notice_id=getattr(current, "AlarmNoticeId", None),
                exists=bool(current),
                msg="CLS alarm notice already %s" % ("present" if desired_present else "absent"),
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                name=name,
                alarm_notice_id=None,
                exists=desired_present,
                msg="Would %s CLS alarm notice" % ("create" if desired_present else "delete"),
            )
        if desired_present:
            payload = dict(notice)
            payload["Name"] = name
            request = models.CreateAlarmNoticeRequest()
            request.from_json_string(json.dumps(payload))
            response = module.sdk_call(client.CreateAlarmNotice, request)
            created_id = getattr(response, "AlarmNoticeId", None)
        else:
            request = models.DeleteAlarmNoticeRequest()
            request.AlarmNoticeId = getattr(current, "AlarmNoticeId", None)
            module.sdk_call(client.DeleteAlarmNotice, request)
            created_id = None
        final = find_notice(module, client, models, name)
        module.exit_json(
            changed=True,
            name=name,
            alarm_notice_id=created_id if desired_present else (getattr(final, "AlarmNoticeId", None) if final else None),
            exists=bool(final),
            msg="CLS alarm notice %s" % ("created" if desired_present else "deleted"),
        )
    except Exception as exc:
        module.fail_sdk_error(exc, "Tencent Cloud CLS alarm notice request failed")


def main():
    run_module()


if __name__ == "__main__":
    main()
