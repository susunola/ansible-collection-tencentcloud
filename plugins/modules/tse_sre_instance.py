#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_sre_instance
short_description: Manage Tencent Cloud TSE service registry engines
version_added: "0.14.0"
description: Creates and deletes TSE registry engines and reconciles client internet access for Nacos, Zookeeper, Consul, Apollo, Eureka and Polaris.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  instance_id: {type: str, description: Existing engine instance ID.}
  name: {type: str, description: Engine name; immutable after creation.}
  engine_type: {type: str, choices: [zookeeper, nacos, consul, apollo, eureka, polarismesh], description: Engine type; immutable after creation.}
  engine_version: {type: str, description: Open-source engine version; immutable after creation.}
  product_version: {type: str, choices: [STANDARD, PROFESSIONAL], description: Product edition; immutable after creation.}
  resource_spec: {type: str, description: Node or capacity specification ID.}
  node_count: {type: int, description: Engine node count.}
  vpc_id: {type: str, description: VPC ID; immutable after creation.}
  subnet_id: {type: str, description: Subnet ID; immutable after creation.}
  zone_ids: {type: list, elements: int, description: Numeric availability-zone IDs.}
  storage_type: {type: str, description: Storage type.}
  storage_capacity: {type: int, description: Storage capacity in GiB.}
  storage_option: {type: list, elements: int, description: Storage option identifiers.}
  admin_name: {type: str, description: Initial console administrator name.}
  admin_password: {type: str, description: Initial console administrator password.}
  admin_token: {type: str, description: Initial engine API administrator token.}
  apollo_environments:
    type: list
    elements: dict
    description: Apollo environment topology required by Apollo engines.
    suboptions:
      name: {type: str, required: true, description: Environment name.}
      resource_spec: {type: str, required: true, description: Environment node specification.}
      node_count: {type: int, required: true, description: Environment node count.}
      storage_capacity: {type: int, required: true, description: Environment storage in GiB.}
      vpc_id: {type: str, required: true, description: Environment VPC ID.}
      subnet_id: {type: str, required: true, description: Environment subnet ID.}
      description: {type: str, description: Environment description.}
  tags: {type: dict, description: Tags applied during creation.}
  internet_access: {type: bool, description: Enable client internet access.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_sre_instance:
    name: production-nacos
    engine_type: nacos
    engine_version: '2.4.3'
    product_version: STANDARD
    resource_spec: spec-xxxxxxxx
    node_count: 3
    vpc_id: vpc-xxxxxxxx
    subnet_id: subnet-xxxxxxxx
    admin_name: admin
    admin_password: "{{ vault_tse_password }}"
    internet_access: false
"""
RETURN = r"""instance: {description: Effective TSE registry-engine metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload
from ansible_collections.susunola.tencentcloud.plugins.module_utils.waiters import wait_for_state


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def describe_request(models, p, offset=0):
    r = models.DescribeSREInstancesRequest()
    r.Offset, r.Limit = offset, 100
    if p.get("instance_id") or p.get("name"):
        f = models.Filter()
        f.Name, f.Values = ("InstanceId", [p["instance_id"]]) if p.get("instance_id") else ("Name", [p["name"]])
        r.Filters = [f]
    return r


def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        item = models.InstanceTagInfo()
        item.TagKey, item.TagValue = key, value
        result.append(item)
    return result


def _apollo(models, values):
    result = []
    for value in values or []:
        item = models.ApolloEnvParam()
        item.Name, item.EngineResourceSpec, item.EngineNodeNum = value["name"], value["resource_spec"], value["node_count"]
        item.StorageCapacity, item.VpcId, item.SubnetId, item.EnvDesc = value["storage_capacity"], value["vpc_id"], value["subnet_id"], value.get("description")
        result.append(item)
    return result


def create_request(models, p):
    r = models.CreateEngineRequest()
    r.EngineType, r.EngineVersion, r.EngineProductVersion = p["engine_type"], p["engine_version"], p["product_version"]
    r.EngineRegion, r.EngineName, r.TradeType = p["region"], p["name"], 0
    r.EngineResourceSpec, r.EngineNodeNum = p.get("resource_spec"), p.get("node_count")
    r.VpcId, r.SubnetId, r.ZoneIds = p.get("vpc_id"), p.get("subnet_id"), p.get("zone_ids")
    r.StorageType, r.StorageCapacity, r.StorageOption = p.get("storage_type"), p.get("storage_capacity"), p.get("storage_option")
    if p.get("admin_name") or p.get("admin_password") or p.get("admin_token"):
        admin = models.EngineAdmin()
        admin.Name, admin.Password, admin.Token = p.get("admin_name"), p.get("admin_password"), p.get("admin_token")
        r.EngineAdmin = admin
    r.ApolloEnvParams, r.EngineTags = _apollo(models, p.get("apollo_environments")), _tags(models, p.get("tags"))
    return r


def internet_request(models, instance_id, engine_type, enabled):
    r = models.UpdateEngineInternetAccessRequest()
    r.InstanceId, r.EngineType, r.EnableClientInternetAccess = instance_id, engine_type, enabled
    return r


def delete_request(models, instance_id):
    r = models.DeleteEngineRequest()
    r.InstanceId = instance_id
    return r


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeSREInstances, describe_request(models, p))
    matches = []
    for item in response.Content or []:
        value = item._serialize(allow_none=True)
        if (p.get("instance_id") and value.get("InstanceId") == p["instance_id"]) or (not p.get("instance_id") and value.get("Name") == p.get("name")):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE engines matched; specify instance_id")
    return matches[0] if matches else None


def _wait(module, client, models, p, states):
    wait_for_state(
        module,
        lambda: str((find(module, client, models, p) or {}).get("Status", "")).lower(),
        states,
        timeout=module.params["waiter_timeout"],
        delay=module.params["waiter_delay"],
    )


def run_module():
    env = {
        "type": "list",
        "elements": "dict",
        "options": {
            "name": {"required": True},
            "resource_spec": {"required": True},
            "node_count": {"type": "int", "required": True},
            "storage_capacity": {"type": "int", "required": True},
            "vpc_id": {"required": True},
            "subnet_id": {"required": True},
            "description": {},
        },
    }
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "instance_id": {},
        "name": {},
        "engine_type": {"choices": ["zookeeper", "nacos", "consul", "apollo", "eureka", "polarismesh"]},
        "engine_version": {},
        "product_version": {"choices": ["STANDARD", "PROFESSIONAL"]},
        "resource_spec": {},
        "node_count": {"type": "int"},
        "vpc_id": {},
        "subnet_id": {},
        "zone_ids": {"type": "list", "elements": "int"},
        "storage_type": {},
        "storage_capacity": {"type": "int"},
        "storage_option": {"type": "list", "elements": "int"},
        "admin_name": {},
        "admin_password": {"no_log": True},
        "admin_token": {"no_log": True},
        "apollo_environments": env,
        "tags": {"type": "dict"},
        "internet_access": {"type": "bool"},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("instance_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, instance=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteEngine, delete_request(models, current["InstanceId"]))
            module.exit_json(changed=True, **(diff or {}), instance=None)
        if not current:
            missing = [k for k in ("name", "engine_type", "engine_version", "product_version") if p.get(k) is None]
            if missing:
                module.fail_json(msg="creation parameters are required for a new TSE engine", missing=missing)
            if p["engine_type"] == "apollo" and not p.get("apollo_environments"):
                module.fail_json(msg="apollo_environments is required for an Apollo engine")
            target = {
                "Name": p["name"],
                "Type": p["engine_type"],
                "Edition": p["product_version"],
                "SpecId": p.get("resource_spec"),
                "Replica": p.get("node_count"),
                "VpcId": p.get("vpc_id"),
                "StorageType": p.get("storage_type"),
                "StorageCapacity": p.get("storage_capacity"),
            }
            diff = maybe_diff(module, None, target)
            if not module.check_mode:
                p["instance_id"] = module.sdk_call(client.CreateEngine, create_request(models, p)).InstanceId
                _wait(module, client, models, p, ["running"])
                current = find(module, client, models, p)
            else:
                current = target
            changed = True
        else:
            changed, diff = False, None
        immutable = {
            "Name": p.get("name"),
            "Type": p.get("engine_type"),
            "Edition": p.get("product_version"),
            "SpecId": p.get("resource_spec"),
            "Replica": p.get("node_count"),
            "VpcId": p.get("vpc_id"),
            "StorageType": p.get("storage_type"),
            "StorageCapacity": p.get("storage_capacity"),
        }
        drift = {k: (current.get(k), v) for k, v in immutable.items() if v is not None and current.get(k) != v}
        if drift:
            module.fail_json(msg="TSE engine identity, topology, network and storage are immutable", immutable_drift=drift)
        if p.get("internet_access") is not None and bool(current.get("EnableInternet")) != p["internet_access"]:
            changed = True
            diff = maybe_diff(module, {"EnableInternet": current.get("EnableInternet")}, {"EnableInternet": p["internet_access"]})
            if not module.check_mode:
                module.sdk_call(
                    client.UpdateEngineInternetAccess,
                    internet_request(models, current["InstanceId"], current.get("Type") or p["engine_type"], p["internet_access"]),
                )
                p["instance_id"] = current["InstanceId"]
                _wait(module, client, models, p, ["running"])
                current = find(module, client, models, p)
        module.exit_json(changed=changed, **(diff or {}), instance=current)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
