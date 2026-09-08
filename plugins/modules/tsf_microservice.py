#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tsf_microservice
short_description: Manage a Tencent Cloud TSF microservice
version_added: "0.15.0"
description: Creates, updates and deletes a TSF microservice using namespace-scoped identity.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  microservice_id: {type: str, description: Existing microservice ID; namespace and exact name are used when omitted.}
  namespace_id: {type: str, required: true, description: TSF namespace ID.}
  name: {type: str, required: true, description: Microservice name.}
  description: {type: str, description: Microservice description.}
extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tsf_microservice:
    namespace_id: namespace-xxxxxxxx
    name: orders
    description: Order service
"""
RETURN = r"""microservice: {description: Effective microservice metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.tsf.v20180326 import models, tsf_client

    return models, tsf_client


def _ser(x):
    return x._serialize(allow_none=True) if x is not None else None


def find(module, client, models, p):
    r = models.DescribeMicroservicesRequest()
    r.NamespaceId = p["namespace_id"]
    r.Offset, r.Limit = 0, 50
    if p.get("microservice_id"):
        r.MicroserviceIdList = [p["microservice_id"]]
    else:
        r.MicroserviceNameList = [p["name"]]
    result = module.sdk_call(client.DescribeMicroservices, r).Result
    values = [_ser(x) for x in ((result.Content if result else None) or [])]
    matches = (
        [x for x in values if x.get("MicroserviceId") == p.get("microservice_id")]
        if p.get("microservice_id")
        else [x for x in values if x.get("MicroserviceName") == p["name"] and x.get("NamespaceId") == p["namespace_id"]]
    )
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSF microservices matched", namespace_id=p["namespace_id"], name=p["name"])
    return matches[0] if matches else None


def desired(p):
    mapping = {"namespace_id": "NamespaceId", "name": "MicroserviceName", "description": "MicroserviceDesc"}
    return {b: p[a] for a, b in mapping.items() if p.get(a) is not None}


def comparable(current, target):
    return {k: current.get(k) for k in target if k in ("NamespaceId", "MicroserviceName", "MicroserviceDesc")}


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "microservice_id": {},
            "namespace_id": {"required": True},
            "name": {"required": True},
            "description": {},
        },
        supports_check_mode=True,
    )
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TsfClient, "tsf.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, microservice=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                r = models.DeleteMicroserviceRequest()
                r.MicroserviceId = current["MicroserviceId"]
                response = module.sdk_call(client.DeleteMicroservice, r)
                if response.Result is False:
                    module.fail_json(msg="Tencent Cloud rejected the TSF microservice deletion", request_id=response.RequestId)
            module.exit_json(changed=True, **(diff or {}), microservice=None)
        target = desired(p)
        if current:
            require_immutable_unchanged(module, current, target, ["NamespaceId", "MicroserviceName"], "TSF microservice")
        compare_target = {k: v for k, v in target.items() if k in ("NamespaceId", "MicroserviceName", "MicroserviceDesc")}
        if current and comparable(current, target) == compare_target:
            module.exit_json(changed=False, microservice=current)
        diff = maybe_diff(module, comparable(current, target) if current else None, compare_target)
        if not module.check_mode:
            if current:
                r = models.ModifyMicroserviceRequest()
                r.MicroserviceId = current["MicroserviceId"]
                r.MicroserviceDesc = target.get("MicroserviceDesc")
                response = module.sdk_call(client.ModifyMicroservice, r)
                if response.Result is False:
                    module.fail_json(msg="Tencent Cloud rejected the TSF microservice update", request_id=response.RequestId)
                p["microservice_id"] = current["MicroserviceId"]
            else:
                r = models.CreateMicroserviceWithDetailRespRequest()
                for key, value in target.items():
                    setattr(r, key, value)
                p["microservice_id"] = module.sdk_call(client.CreateMicroserviceWithDetailResp, r).Result
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), microservice=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
