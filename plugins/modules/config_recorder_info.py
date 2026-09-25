#!/usr/bin/python
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: config_recorder_info
short_description: Gather Tencent Cloud Config recorder state
version_added: "1.4.0"
description: Returns recorder status and the complete observable resource-type set.
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.timeout
attributes:
  check_mode:
    description:
      - Can run in C(check_mode), reading the current state and predicting
        the result without issuing a write API call.
    support: full
  idempotent:
    description:
      - Read-only, so every run returns the current state and never changes
        the target, and a repeated run reports C(changed=false).
    support: full
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''
EXAMPLES = r'''
- susunola.tencentcloud.config_recorder_info:
    region: ap-guangzhou
'''
RETURN = r'''
recorders: {description: Recorder state as a single-element list., returned: always, type: list, elements: dict}
recorder: {description: Recorder state and monitored resource types., returned: always, type: dict}
request_id: {description: Request ID returned by the API., returned: always, type: str}
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile, create_credential, sdk_call, serialize_sdk_object,
    tencentcloud_argument_spec,
)


def build_request(models):
    return models.DescribeConfigRecorderRequest()


def normalize(response):
    value = serialize_sdk_object(response)
    value.pop("RequestId", None)
    value["ResourceTypes"] = sorted(set(item.ResourceType for item in (getattr(response, "Items", None) or []) if item.ResourceType))
    return value


def run_module():
    module = AnsibleModule(argument_spec=tencentcloud_argument_spec(), supports_check_mode=True)
    try:
        from tencentcloud.config.v20220802 import config_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-config package is required.")
    client = config_client.ConfigClient(create_credential(module), module.params["region"], create_client_profile(module, "config.tencentcloudapi.com"))
    response = sdk_call(module, client.DescribeConfigRecorder, build_request(models))
    recorder = normalize(response)
    module.exit_json(changed=False, recorders=[recorder], recorder=recorder, request_id=getattr(response, "RequestId", None))


def main():
    run_module()


if __name__ == "__main__":
    main()
