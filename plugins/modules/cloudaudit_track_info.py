#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: cloudaudit_track_info
short_description: Gather Tencent Cloud CloudAudit tracks
version_added: "1.4.0"
description:
  - Lists CloudAudit tracks and resolves each match to its complete delivery configuration.
  - Results can be filtered by track ID or exact name.
options:
  track_id: {description: Audit track ID., type: int}
  name: {description: Exact audit track name., type: str}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: List all CloudAudit tracks
  susunola.tencentcloud.cloudaudit_track_info:
    region: ap-guangzhou

- name: Read a track by ID
  susunola.tencentcloud.cloudaudit_track_info:
    region: ap-guangzhou
    track_id: 12345
'''

RETURN = r'''
tracks: {description: Matching complete track configurations., returned: always, type: list, elements: dict}
track: {description: The single matching track when exactly one matches., returned: always, type: dict}
request_id: {description: Request ID returned by the final API call., returned: always, type: str}
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.tencentcloud import (
    create_client_profile, create_credential, sdk_call, serialize_sdk_object, tencentcloud_argument_spec,
)


def list_request(models, page=1, page_size=50):
    request = models.DescribeAuditTracksRequest()
    request.PageNumber, request.PageSize = page, page_size
    return request


def detail_request(models, track_id):
    request = models.DescribeAuditTrackRequest()
    request.TrackId = track_id
    return request


def run_module():
    argument_spec = tencentcloud_argument_spec()
    argument_spec.update({"track_id": {"type": "int"}, "name": {"type": "str"}})
    module = AnsibleModule(argument_spec=argument_spec, mutually_exclusive=[("track_id", "name")], supports_check_mode=True)
    try:
        from tencentcloud.cloudaudit.v20190319 import cloudaudit_client, models
    except ImportError:
        module.fail_json(msg="The tencentcloud-sdk-python-cloudaudit package is required.")
    p = module.params
    client = cloudaudit_client.CloudauditClient(create_credential(module), p["region"], create_client_profile(module, "cloudaudit.tencentcloudapi.com"))
    page, summaries, request_id = 1, [], None
    while True:
        response = sdk_call(module, client.DescribeAuditTracks, list_request(models, page))
        request_id = getattr(response, "RequestId", None)
        items = list(getattr(response, "Tracks", None) or [])
        summaries.extend(item for item in items if (p.get("track_id") is None or item.TrackId == p["track_id"]) and (p.get("name") is None or item.Name == p["name"]))
        if page * 50 >= int(getattr(response, "TotalCount", 0) or 0):
            break
        page += 1
    tracks = []
    for summary in summaries:
        response = sdk_call(module, client.DescribeAuditTrack, detail_request(models, summary.TrackId))
        request_id = getattr(response, "RequestId", None)
        value = serialize_sdk_object(response)
        value.pop("RequestId", None)
        value["TrackId"] = summary.TrackId
        tracks.append(value)
    module.exit_json(changed=False, tracks=tracks, track=tracks[0] if len(tracks) == 1 else None, request_id=request_id)


def main():
    run_module()


if __name__ == "__main__":
    main()
