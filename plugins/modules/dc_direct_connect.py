#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: dc_direct_connect
short_description: Manage Tencent Cloud physical Direct Connect circuits
version_added: "0.14.0"
description: Creates, updates and deletes physical Direct Connect circuit applications.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  direct_connect_id: {type: str, description: Existing physical connection ID.}
  name: {type: str, description: Physical connection name.}
  access_point_id: {type: str, description: Access point ID required for creation and immutable afterwards.}
  line_operator: {type: str, description: Carrier required for creation and immutable afterwards.}
  port_type: {type: str, description: Physical port type required for creation and immutable afterwards.}
  circuit_code: {type: str, description: Carrier circuit code.}
  location: {type: str, description: Customer equipment room location required for creation.}
  bandwidth: {type: int, description: Circuit bandwidth in Mbps.}
  redundant_direct_connect_id: {type: str, description: Creation-time redundant connection ID.}
  vlan: {type: int, description: Management VLAN.}
  tencent_address: {type: str, description: Tencent-side management address.}
  customer_address: {type: str, description: Customer-side management address.}
  customer_name: {type: str, description: Customer organization name.}
  customer_contact_mail: {type: str, description: Customer contact email.}
  customer_contact_number: {type: str, description: Customer contact phone.}
  fault_contact_name: {type: str, description: Fault-report contact name.}
  fault_contact_number: {type: str, description: Fault-report contact phone.}
  fault_contact_email: {type: str, description: Fault-report contact email.}
  sign_law: {type: bool, description: Accept applicable service agreement.}
  macsec: {type: bool, description: Creation-time MACsec selection.}
  tags: {type: dict, description: Creation-time tags.}
  retries: {type: int, default: 5, description: Number of retries for transient failures.}
  waiter_delay: {type: int, default: 5, description: Seconds between polling attempts.}
  waiter_timeout: {type: int, default: 120, description: Overall polling timeout in seconds.}
  user_agent: {type: str, default: ansible-collection.susunola.tencentcloud, description: User-Agent suffix.}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.dc_direct_connect:
    name: primary-circuit
    access_point_id: ap-xxxxxxxx
    line_operator: ChinaTelecom
    port_type: 10GBase-LR
    location: Customer IDC A
    bandwidth: 1000
    customer_name: Example Corp
    customer_contact_mail: network@example.com
    customer_contact_number: '13800000000'
"""
RETURN = r"""direct_connect: {description: Effective physical Direct Connect metadata., type: dict, returned: always}"""
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import require_immutable_unchanged, sdk_error_payload


def _load():
    from tencentcloud.dc.v20180410 import models, dc_client

    return models, dc_client


def describe_request(models, p):
    r = models.DescribeDirectConnectsRequest()
    r.Offset, r.Limit = 0, 100
    if p.get("direct_connect_id"):
        r.DirectConnectIds = [p["direct_connect_id"]]
    return r


def _tags(models, values):
    result = []
    for key, value in sorted((values or {}).items()):
        x = models.Tag()
        x.Key, x.Value = key, value
        result.append(x)
    return result


def _fill(r, p):
    r.DirectConnectName, r.CircuitCode, r.Vlan, r.TencentAddress, r.CustomerAddress = (
        p["name"],
        p.get("circuit_code"),
        p.get("vlan"),
        p.get("tencent_address"),
        p.get("customer_address"),
    )
    r.CustomerName, r.CustomerContactMail, r.CustomerContactNumber = p.get("customer_name"), p.get("customer_contact_mail"), p.get("customer_contact_number")
    r.FaultReportContactPerson, r.FaultReportContactNumber, r.FaultReportContactEmail = (
        p.get("fault_contact_name"),
        p.get("fault_contact_number"),
        p.get("fault_contact_email"),
    )
    r.SignLaw, r.Bandwidth = p.get("sign_law"), p.get("bandwidth")
    return r


def create_request(models, p):
    r = _fill(models.CreateDirectConnectRequest(), p)
    r.AccessPointId, r.LineOperator, r.PortType, r.Location = p["access_point_id"], p["line_operator"], p["port_type"], p["location"]
    r.RedundantDirectConnectId, r.IsMacSec, r.Tags = p.get("redundant_direct_connect_id"), p.get("macsec"), _tags(models, p.get("tags"))
    return r


def update_request(models, p, direct_connect_id):
    r = _fill(models.ModifyDirectConnectAttributeRequest(), p)
    r.DirectConnectId = direct_connect_id
    return r


def delete_request(models, direct_connect_id):
    r = models.DeleteDirectConnectRequest()
    r.DirectConnectId = direct_connect_id
    return r


def find(module, client, models, p):
    response = module.sdk_call(client.DescribeDirectConnects, describe_request(models, p))
    matches = []
    for item in response.DirectConnectSet or []:
        value = item._serialize(allow_none=True)
        if (p.get("direct_connect_id") and value.get("DirectConnectId") == p["direct_connect_id"]) or (
            not p.get("direct_connect_id") and value.get("DirectConnectName") == p.get("name")
        ):
            matches.append(value)
    if len(matches) > 1:
        module.fail_json(msg="Multiple physical connections matched; specify direct_connect_id")
    return matches[0] if matches else None


FIELDS = {
    "DirectConnectName": "name",
    "AccessPointId": "access_point_id",
    "LineOperator": "line_operator",
    "PortType": "port_type",
    "CircuitCode": "circuit_code",
    "Location": "location",
    "Bandwidth": "bandwidth",
    "Vlan": "vlan",
    "TencentAddress": "tencent_address",
    "CustomerAddress": "customer_address",
    "CustomerName": "customer_name",
    "CustomerContactMail": "customer_contact_mail",
    "CustomerContactNumber": "customer_contact_number",
    "FaultReportContactPerson": "fault_contact_name",
    "FaultReportContactNumber": "fault_contact_number",
    "FaultReportContactEmail": "fault_contact_email",
    "SignLaw": "sign_law",
}


def desired(p, current=None):
    old = current or {}
    return {api: p.get(param) if p.get(param) is not None else old.get(api) for api, param in FIELDS.items()}


def comparable(v):
    return {k: v.get(k) for k in FIELDS}


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "direct_connect_id": {},
        "name": {},
        "access_point_id": {},
        "line_operator": {},
        "port_type": {},
        "circuit_code": {},
        "location": {},
        "bandwidth": {"type": "int"},
        "redundant_direct_connect_id": {},
        "vlan": {"type": "int"},
        "tencent_address": {},
        "customer_address": {},
        "customer_name": {},
        "customer_contact_mail": {},
        "customer_contact_number": {},
        "fault_contact_name": {},
        "fault_contact_number": {},
        "fault_contact_email": {},
        "sign_law": {"type": "bool"},
        "macsec": {"type": "bool"},
        "tags": {"type": "dict"},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("direct_connect_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.DcClient, "dc.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, direct_connect=None)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteDirectConnect, delete_request(models, current["DirectConnectId"]))
            module.exit_json(changed=True, **(diff or {}), direct_connect=None)
        if not current:
            missing = [
                k
                for k in (
                    "name",
                    "access_point_id",
                    "line_operator",
                    "port_type",
                    "location",
                    "bandwidth",
                    "customer_name",
                    "customer_contact_mail",
                    "customer_contact_number",
                )
                if p.get(k) is None
            ]
            if missing:
                module.fail_json(msg="creation parameters are required for a physical connection", missing=missing)
        before, target = comparable(current) if current else None, desired(p, current)
        if before == target:
            module.exit_json(changed=False, direct_connect=current)
        if current:
            require_immutable_unchanged(module, before, target, ("AccessPointId", "LineOperator", "PortType", "Location"), "physical Direct Connect")
        diff = maybe_diff(module, before, target)
        if not module.check_mode:
            effective = dict(p)
            for api, param in FIELDS.items():
                effective[param] = target[api]
            response = module.sdk_call(
                client.ModifyDirectConnectAttribute if current else client.CreateDirectConnect,
                update_request(models, effective, current["DirectConnectId"]) if current else create_request(models, effective),
            )
            p["direct_connect_id"] = current["DirectConnectId"] if current else response.DirectConnectIdSet[0]
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), direct_connect=current if not module.check_mode else target)
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
