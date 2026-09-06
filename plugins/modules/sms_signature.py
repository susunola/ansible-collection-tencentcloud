#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: sms_signature
short_description: Manage Tencent Cloud SMS signatures
version_added: "0.14.0"
description:
  - Create or remove an SMS signature (签名) through the C(sms.v20210111)
    API C(AddSmsSign), C(DeleteSmsSign) and C(DescribeSmsSignList).
  - SMS signatures are review-based resources. The content fields
    (sign_type, document_type, sign_purpose, proof_image and friends) are
    only sent at application time; the platform reviews them asynchronously
    and the signature becomes usable only after approval.
  - This module is idempotent. When a signature with the same name already
    exists and is in a usable or pending state, the module reports
    C(changed=false) and issues no API write. A signature whose review
    failed (status code -1) is treated as absent, so re-running the task
    after fixing the materials resubmits the application.
  - Supports check mode; no API write happens in check mode, only reads.
options:
  sign_name:
    description: Signature content, without the C([]) brackets, e.g. C(Tencent Cloud).
    type: str
    required: true
  state:
    description: Whether the signature should exist.
    type: str
    choices: [present, absent]
    default: present
  international:
    description:
      - Whether this is an international SMS signature. Domestic
        signatures use false. Written to
        V(DescribeSmsSignListRequest.International) and
        V(AddSmsSignRequest.International).
    type: bool
    default: false
  sign_type:
    description:
      - Signature type, written to V(AddSmsSignRequest.SignType).
        Required when the signature has to be created. Allowed values
        depend on the account type; refer to the SMS console.
    type: int
  document_type:
    description:
      - Qualification document type, written to
        V(AddSmsSignRequest.DocumentType). Required when the signature has
        to be created.
    type: int
  sign_purpose:
    description:
      - Signature purpose, written to V(AddSmsSignRequest.SignPurpose).
        Required when the signature has to be created.
    type: int
  proof_image:
    description:
      - Base64-encoded qualification material image, written to
        V(AddSmsSignRequest.ProofImage). Required when the signature has to
        be created.
    type: str
  commission_image:
    description:
      - Base64-encoded authorization letter image, written to
        V(AddSmsSignRequest.CommissionImage). Only sent when provided.
    type: str
  qualification_id:
    description:
      - Domestic SMS qualification ID, written to
        V(AddSmsSignRequest.QualificationId). Only sent when provided.
    type: str
  remark:
    description:
      - Remark shown to the reviewers, written to
        V(AddSmsSignRequest.Remark). Only sent when provided.
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
  - The platform reviews signature applications asynchronously; this module
    returns as soon as the application is submitted or deleted and does not
    wait for the review result.
  - Changing the content of an approved signature requires a fresh
    application. Remove the signature (state=absent) and re-run, or use the
    SMS console.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Apply for a domestic signature
  susunola.tencentcloud.sms_signature:
    region: ap-guangzhou
    sign_name: Tencent Cloud
    sign_type: 0
    document_type: 0
    sign_purpose: 0
    proof_image: "{{ lookup('file', 'proof.png') | b64encode }}"

- name: Apply for an international signature
  susunola.tencentcloud.sms_signature:
    region: ap-singapore
    sign_name: Tencent Cloud
    international: true
    sign_type: 0
    document_type: 0
    sign_purpose: 0
    proof_image: "{{ lookup('file', 'proof.png') | b64encode }}"

- name: Remove a signature
  susunola.tencentcloud.sms_signature:
    region: ap-guangzhou
    sign_name: Tencent Cloud
    state: absent
'''

RETURN = r'''
sign_id:
  description: ID of the matched or newly applied signature.
  returned: when known
  type: int
sign_name:
  description: Name of the managed signature.
  returned: always
  type: str
status_code:
  description:
    - Review status of the existing signature. 0 means active, 1 means in
      review, 2 means approved pending effect and -1 means rejected or
      otherwise unavailable.
  returned: when a matching signature exists
  type: int
review_reply:
  description: Review feedback, usually the rejection reason.
  returned: when a matching signature exists
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


def find_sign(module, client, models, sign_name, international):
    """Return the serialized matching sign dict, preferring a usable entry.

    A sign whose review failed (StatusCode == -1) is only returned when no
    other entry carries the same name, so callers can resubmit it.
    """
    request = models.DescribeSmsSignListRequest()
    request.International = _to_int(international)
    matches = []
    offset = 0
    while True:
        request.Offset = offset
        request.Limit = 100
        response = module.sdk_call(client.DescribeSmsSignList, request)
        items = response.DescribeSignListStatusSet or []
        for item in items:
            data = item._serialize(allow_none=True)
            if data.get("SignName") == sign_name:
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
            "sign_name": {"type": "str", "required": True},
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "international": {"type": "bool", "default": False},
            "sign_type": {"type": "int"},
            "document_type": {"type": "int"},
            "sign_purpose": {"type": "int"},
            "proof_image": {"type": "str", "no_log": True},
            "commission_image": {"type": "str", "no_log": True},
            "qualification_id": {"type": "str"},
            "remark": {"type": "str"},
        },
        supports_check_mode=True,
    )
    module.require_sdk()
    p = module.params

    models, sms_client = _load_sms()
    client = module.create_client(sms_client.SmsClient, "sms.tencentcloudapi.com")
    try:
        sign = find_sign(module, client, models, p["sign_name"], p["international"])

        if p["state"] == "absent":
            if sign is None:
                module.exit_json(changed=False, sign_name=p["sign_name"], msg="Signature not present")
            diff = maybe_diff(module, sign, None)
            if module.check_mode:
                module.exit_json(
                    changed=True, **(diff or {}),
                    sign_name=p["sign_name"],
                    msg="Would delete signature {0}".format(sign.get("SignId")),
                )
            request = models.DeleteSmsSignRequest()
            request.SignId = int(sign["SignId"])
            module.sdk_call(client.DeleteSmsSign, request)
            module.exit_json(
                changed=True, **(diff or {}),
                sign_name=p["sign_name"],
                msg="Deleted signature {0}".format(sign.get("SignId")),
            )

        # state == present
        if sign is not None and sign.get("StatusCode") != -1:
            module.exit_json(
                changed=False,
                sign_id=sign.get("SignId"),
                sign_name=p["sign_name"],
                status_code=sign.get("StatusCode"),
                review_reply=sign.get("ReviewReply"),
                msg="Signature already present (status {0})".format(sign.get("StatusCode")),
            )

        missing = [k for k in ("sign_type", "document_type", "sign_purpose", "proof_image") if p[k] is None]
        if missing:
            module.fail_json(
                msg="Parameters required to apply for a signature are missing: {0}".format(", ".join(missing)),
            )
        after = {"SignName": p["sign_name"], "International": _to_int(p["international"])}
        diff = maybe_diff(module, sign, after)
        if module.check_mode:
            module.exit_json(
                changed=True, **(diff or {}),
                sign_name=p["sign_name"],
                msg="Would apply for signature {0}".format(p["sign_name"]),
            )

        request = models.AddSmsSignRequest()
        request.SignName = p["sign_name"]
        request.SignType = p["sign_type"]
        request.DocumentType = p["document_type"]
        request.International = _to_int(p["international"])
        request.SignPurpose = p["sign_purpose"]
        request.ProofImage = p["proof_image"]
        if p["commission_image"]:
            request.CommissionImage = p["commission_image"]
        if p["qualification_id"]:
            request.QualificationId = p["qualification_id"]
        if p["remark"]:
            request.Remark = p["remark"]
        response = module.sdk_call(client.AddSmsSign, request)
        status = getattr(response, "AddSignStatus", None)
        sign_id = getattr(status, "SignId", None) if status is not None else None
        module.exit_json(
            changed=True, **(diff or {}),
            sign_id=sign_id,
            sign_name=p["sign_name"],
            msg="Signature application submitted for review",
        )
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
