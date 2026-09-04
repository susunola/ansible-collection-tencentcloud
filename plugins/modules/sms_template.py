#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: sms_template
short_description: Manage Tencent Cloud SMS templates
version_added: "0.14.0"
description:
  - Create or remove an SMS template (短信模板) through the C(sms.v20210111)
    API C(AddSmsTemplate), C(DeleteSmsTemplate) and
    C(DescribeSmsTemplateList).
  - SMS templates are review-based resources. The content fields
    (sms_type, template_content and remark) are only sent at application
    time; the platform reviews them asynchronously and the template becomes
    usable only after approval.
  - This module is idempotent. When a template with the same name already
    exists and is in a usable or pending state, the module reports
    C(changed=false) and issues no API write. A template whose review failed
    (status code -1) is treated as absent, so re-running the task after
    fixing the content resubmits the application.
  - Supports check mode; no API write happens in check mode, only reads.
options:
  template_name:
    description: Name of the SMS template, e.g. C(Login verification code).
    type: str
    required: true
  state:
    description: Whether the template should exist.
    type: str
    choices: [present, absent]
    default: present
  international:
    description:
      - Whether this is an international SMS template. Domestic templates
        use false. Written to V(DescribeSmsTemplateListRequest.International)
        and V(AddSmsTemplateRequest.International).
    type: bool
    default: false
  sms_type:
    description:
      - Template type, written to V(AddSmsTemplateRequest.SmsType).
        Required when the template has to be created. 0 is a normal
        (transactional) message and 1 is a marketing message.
    type: int
  template_content:
    description:
      - Body of the template, with C({1}), C({2}) style placeholders,
        written to V(AddSmsTemplateRequest.TemplateContent). Required when
        the template has to be created.
    type: str
  remark:
    description:
      - Remark shown to the reviewers, written to
        V(AddSmsTemplateRequest.Remark). Only sent when provided.
    type: str
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
  - Requires the C(tencentcloud-sdk-python-sms) package on the controller.
  - The platform reviews template applications asynchronously; this module
    returns as soon as the application is submitted or deleted and does not
    wait for the review result.
  - Changing the content of an approved template requires a fresh
    application. Remove the template (state=absent) and re-run, or use the
    SMS console.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Apply for a transactional template
  susunola.tencentcloud.sms_template:
    region: ap-guangzhou
    template_name: Login verification code
    sms_type: 0
    template_content: "Your verification code is {1}. It expires in {2} minutes."

- name: Remove a template
  susunola.tencentcloud.sms_template:
    region: ap-guangzhou
    template_name: Login verification code
    state: absent
'''

RETURN = r'''
template_id:
  description: ID of the matched or newly applied template.
  returned: when known
  type: int
template_name:
  description: Name of the managed template.
  returned: always
  type: str
status_code:
  description:
    - Review status of the existing template. 0 means active, 1 means in
      review, 2 means approved pending effect and -1 means rejected or
      otherwise unavailable.
  returned: when a matching template exists
  type: int
review_reply:
  description: Review feedback, usually the rejection reason.
  returned: when a matching template exists
  type: str
changed:
  description: Whether an API write happened.
  returned: always
  type: bool
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load_sms():
    from tencentcloud.sms.v20210111 import models, sms_client
    return models, sms_client


def _to_int(flag):
    return 1 if flag else 0


def find_template(module, client, models, template_name, international):
    """Return the serialized matching template dict, preferring a usable entry.

    A template whose review failed (StatusCode == -1) is only returned when
    no other entry carries the same name, so callers can resubmit it.
    """
    request = models.DescribeSmsTemplateListRequest()
    request.International = _to_int(international)
    matches = []
    offset = 0
    while True:
        request.Offset = offset
        request.Limit = 100
        response = module.sdk_call(client.DescribeSmsTemplateList, request)
        items = response.DescribeTemplateStatusSet or []
        for item in items:
            data = item._serialize(allow_none=True)
            if data.get("TemplateName") == template_name:
                matches.append(data)
        if len(items) < 100:
            break
        offset += len(items)
    for match in matches:
        if match.get("StatusCode") != -1:
            return match
    return matches[0] if matches else None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "template_name": {"type": "str", "required": True},
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "international": {"type": "bool", "default": False},
            "sms_type": {"type": "int"},
            "template_content": {"type": "str"},
            "remark": {"type": "str"},
        },
        supports_check_mode=True,
    )
    module.require_sdk()
    p = module.params

    models, sms_client = _load_sms()
    client = module.create_client(sms_client.SmsClient, "sms.tencentcloudapi.com")
    try:
        template = find_template(module, client, models, p["template_name"], p["international"])

        if p["state"] == "absent":
            if template is None:
                module.exit_json(changed=False, template_name=p["template_name"], msg="Template not present")
            diff = maybe_diff(module, template, None)
            if module.check_mode:
                module.exit_json(
                    changed=True, **(diff or {}),
                    template_name=p["template_name"],
                    msg="Would delete template {0}".format(template.get("TemplateId")),
                )
            request = models.DeleteSmsTemplateRequest()
            request.TemplateId = int(template["TemplateId"])
            module.sdk_call(client.DeleteSmsTemplate, request)
            module.exit_json(
                changed=True, **(diff or {}),
                template_name=p["template_name"],
                msg="Deleted template {0}".format(template.get("TemplateId")),
            )

        # state == present
        if template is not None and template.get("StatusCode") != -1:
            module.exit_json(
                changed=False,
                template_id=template.get("TemplateId"),
                template_name=p["template_name"],
                status_code=template.get("StatusCode"),
                review_reply=template.get("ReviewReply"),
                msg="Template already present (status {0})".format(template.get("StatusCode")),
            )

        missing = [k for k in ("sms_type", "template_content") if p[k] is None]
        if missing:
            module.fail_json(
                msg="Parameters required to apply for a template are missing: {0}".format(", ".join(missing)),
            )
        after = {"TemplateName": p["template_name"], "International": _to_int(p["international"])}
        diff = maybe_diff(module, template, after)
        if module.check_mode:
            module.exit_json(
                changed=True, **(diff or {}),
                template_name=p["template_name"],
                msg="Would apply for template {0}".format(p["template_name"]),
            )

        request = models.AddSmsTemplateRequest()
        request.TemplateName = p["template_name"]
        request.TemplateContent = p["template_content"]
        request.SmsType = p["sms_type"]
        request.International = _to_int(p["international"])
        if p["remark"]:
            request.Remark = p["remark"]
        response = module.sdk_call(client.AddSmsTemplate, request)
        status = getattr(response, "AddTemplateStatus", None)
        template_id = getattr(status, "TemplateId", None) if status is not None else None
        module.exit_json(
            changed=True, **(diff or {}),
            template_id=template_id,
            template_name=p["template_name"],
            msg="Template application submitted for review",
        )
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
