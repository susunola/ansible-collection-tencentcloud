#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: dnspod_domain
short_description: Manage Tencent Cloud DNSPod domains
version_added: "0.14.0"
description: Creates, updates, enables, disables and deletes DNSPod domains.
options:
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  domain_id: {type: int, description: Existing DNSPod domain ID.}
  name: {type: str, description: Domain name.}
  group_id: {type: int, default: 1, description: DNSPod domain group ID at creation.}
  remark: {type: str, default: '', description: Domain remark.}
  enabled: {type: bool, default: true, description: Enable DNS resolution.}
  tags: {type: dict, default: {}, description: Tags applied at creation.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dnspod_domain:
    name: example.com
    remark: Public production zone
"""
RETURN = r"""domain: {description: DNSPod domain metadata., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.dnspod.v20210323 import dnspod_client, models

    return models, dnspod_client


def find(module, client, models, domain_id, name):
    offset = 0
    matches = []
    while domain_id or name:
        request = models.DescribeDomainListRequest()
        request.Type = "ALL"
        request.Offset, request.Limit = offset, 100
        request.Keyword = name
        response = module.sdk_call(client.DescribeDomainList, request)
        items = list(response.DomainList or [])
        matches.extend(x._serialize(allow_none=True) for x in items if (domain_id and x.DomainId == domain_id) or (not domain_id and x.Name == name))
        offset += len(items)
        total = int((response.DomainCountInfo.DomainTotal if response.DomainCountInfo else 0) or 0)
        if domain_id or not items or offset >= total:
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple DNSPod domains have the requested name", name=name)
    return matches[0] if matches else None


def tag_models(models, values):
    result = []
    for key, value in sorted(values.items()):
        item = models.TagItem()
        item.TagKey, item.TagValue = str(key), str(value)
        result.append(item)
    return result


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "domain_id": {"type": "int"},
            "name": {},
            "group_id": {"type": "int", "default": 1},
            "remark": {"default": ""},
            "enabled": {"type": "bool", "default": True},
            "tags": {"type": "dict", "default": {}},
        },
        required_one_of=[("domain_id", "name")],
        supports_check_mode=True,
    )
    p = module.params
    if p["state"] == "present" and not p["name"]:
        module.fail_json(msg="name is required when state=present")
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DnspodClient, "dnspod.tencentcloudapi.com")
    try:
        current = find(module, client, models, p["domain_id"], p["name"])
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, domain=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                request = models.DeleteDomainRequest()
                request.DomainId = current["DomainId"]
                module.sdk_call(client.DeleteDomain, request)
            module.exit_json(changed=True, **(diff or {}), domain=current if module.check_mode else None)
        target = {"Remark": p["remark"], "Status": "ENABLE" if p["enabled"] else "DISABLE"}
        before = {k: current.get(k) for k in target} if current else None
        if before == target:
            module.exit_json(changed=False, domain=current)
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            if not current:
                request = models.CreateDomainRequest()
                request.Domain, request.GroupId = p["name"], p["group_id"]
                request.Tags = tag_models(models, p["tags"])
                current = module.sdk_call(client.CreateDomain, request).DomainInfo._serialize(allow_none=True)
                p["domain_id"] = current["DomainId"]
            if current.get("Remark") != p["remark"]:
                request = models.ModifyDomainRemarkRequest()
                request.DomainId, request.Remark = current["DomainId"], p["remark"]
                module.sdk_call(client.ModifyDomainRemark, request)
            if current.get("Status") != target["Status"]:
                request = models.ModifyDomainStatusRequest()
                request.DomainId, request.Status = current["DomainId"], target["Status"]
                module.sdk_call(client.ModifyDomainStatus, request)
            current = find(module, client, models, current["DomainId"], None)
        module.exit_json(changed=True, **(diff or {}), domain=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
