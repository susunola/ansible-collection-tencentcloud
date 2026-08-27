#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: security_group_rule
short_description: Manage Tencent Cloud security group rules
version_added: "0.4.0"
description:
  - Reconcile the rule set of a single Tencent Cloud security group.
  - The module compares the desired rules with the rules currently configured
    on the group, creates the missing delta and, when O(purge=true), deletes
    the surplus.
  - This module is idempotent. Running it twice leaves the rule set unchanged
    and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
options:
  security_group_id:
    description:
      - ID of the security group whose rules are managed, e.g. C(sg-xxxxxxxx).
    type: str
    required: true
  rules:
    description:
      - Desired rules for the security group.
      - Each rule is identified by the combination of direction, protocol,
        port, CIDR block, action and policy description. Changing the
        description of an existing rule replaces the rule (delete and
        re-create), because the API identifies rules by protocol, port, CIDR
        and action only.
    type: list
    elements: dict
    default: []
    suboptions:
      protocol:
        description:
          - IP protocol of the rule. One of C(TCP), C(UDP), C(ICMP),
            C(ICMPv6) or C(ALL).
          - Values are normalized to upper case before comparison.
        type: str
        required: true
      port:
        description:
          - Port of the rule, e.g. a single port (C(80)), a range
            (C(8000-8010)), a comma separated list (C(80,443)) or C(all).
          - Must be C(all) when O(rules.protocol=ALL).
        type: str
        default: all
      cidr_block:
        description:
          - IPv4 CIDR block or IP address the rule applies to, e.g.
            C(10.0.0.0/8).
          - The API maps every C(0.0.0.0/n) value to C(0.0.0.0/0); the module
            normalizes the same way before comparing rules.
        type: str
        required: true
      action:
        description: Whether the rule accepts or drops traffic.
        type: str
        choices: [ACCEPT, DROP]
        default: ACCEPT
      policy_description:
        description: Description of the rule.
        type: str
        default: ""
      direction:
        description: Direction of the traffic the rule applies to.
        type: str
        choices: [ingress, egress]
        default: ingress
  purge:
    description:
      - When C(true), existing rules not listed in O(rules) are deleted.
      - When C(false), rules from O(rules) are created when missing, but no
        rule is ever deleted.
    type: bool
    default: true
  retries:
    description:
      - Maximum number of retry attempts for throttled or transient API
        failures, using exponential backoff with jitter.
    type: int
    default: 5
  waiter_timeout:
    description:
      - Maximum time in seconds to wait for an asynchronous resource to reach
        the desired state.
    type: int
    default: 120
  waiter_delay:
    description: Interval in seconds between state polls while waiting.
    type: int
    default: 5
  user_agent:
    description:
      - User-Agent string sent with API requests.
    type: str
    default: ansible-collection.tencentcloud.cloud
notes:
  - Requires the C(tencentcloud-sdk-python-vpc) package on the controller.
  - The C(DeleteSecurityGroupPolicies) API accepts rules of a single direction
    per request, so deletions are issued as one request per direction.
  - Deletion addresses rules by the full policy object (action, protocol,
    CIDR block and port), as required by the API.
  - Rules using service templates or address templates are not supported;
    such pre-existing rules are only deleted when O(purge=true) because they
    never match a rule from O(rules).
extends_documentation_fragment: tencentcloud.cloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Set the exact ingress rules of a security group
  tencentcloud.cloud.security_group_rule:
    region: ap-guangzhou
    security_group_id: sg-xxxxxxxx
    rules:
      - protocol: TCP
        port: 443
        cidr_block: 0.0.0.0/0
        action: ACCEPT
        policy_description: HTTPS from anywhere
      - protocol: TCP
        port: 22
        cidr_block: 10.0.0.0/8
        action: ACCEPT
        policy_description: SSH from the internal network
        direction: ingress

- name: Add a rule without removing existing ones
  tencentcloud.cloud.security_group_rule:
    region: ap-guangzhou
    security_group_id: sg-xxxxxxxx
    purge: false
    rules:
      - protocol: UDP
        port: 53
        cidr_block: 10.0.1.0/24
        action: ACCEPT
        direction: egress

- name: Preview the reconciliation (no changes applied)
  tencentcloud.cloud.security_group_rule:
    region: ap-guangzhou
    security_group_id: sg-xxxxxxxx
    rules:
      - protocol: ALL
        port: all
        cidr_block: 10.0.0.0/8
        action: ACCEPT
  check_mode: true

- name: Remove every rule from a security group
  tencentcloud.cloud.security_group_rule:
    region: ap-guangzhou
    security_group_id: sg-xxxxxxxx
    rules: []
'''

RETURN = r'''
security_group_id:
  description: ID of the managed security group.
  returned: always
  type: str
  sample: sg-xxxxxxxx
rules:
  description:
    - Rules of the security group as reported by the API after the operation,
    - normalized to the module's rule format.
  returned: success
  type: list
  elements: dict
  sample:
    - protocol: TCP
      port: "443"
      cidr_block: 0.0.0.0/0
      action: ACCEPT
      policy_description: HTTPS from anywhere
      direction: ingress
'''

from ansible_collections.tencentcloud.cloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.tencentcloud.cloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.tencentcloud.cloud.plugins.module_utils.errors import (
    is_idempotent_success,
)


def _load_vpc():
    from tencentcloud.vpc.v20170312 import models, vpc_client
    return models, vpc_client


def build_describe_request(models, security_group_id):
    request = models.DescribeSecurityGroupPoliciesRequest()
    request.SecurityGroupId = security_group_id
    return request


def _normalize_cidr(cidr_block):
    """The API maps every 0.0.0.0/n value to 0.0.0.0/0; mirror that."""
    cidr = (cidr_block or "").strip()
    if cidr.startswith("0.0.0.0/"):
        return "0.0.0.0/0"
    return cidr


def normalize_desired_rule(rule):
    """Normalize a user-supplied rule dict for comparison and API calls."""
    return {
        "protocol": (rule.get("protocol") or "").upper(),
        "port": str(rule.get("port") or "all").lower(),
        "cidr_block": _normalize_cidr(rule.get("cidr_block")),
        "action": (rule.get("action") or "ACCEPT").upper(),
        "policy_description": rule.get("policy_description") or "",
        "direction": (rule.get("direction") or "ingress").lower(),
    }


def normalize_current_rule(policy, direction):
    """Normalize a SecurityGroupPolicy dict from the API."""
    return {
        "protocol": (policy.get("Protocol") or "").upper(),
        "port": str(policy.get("Port") or "all").lower(),
        "cidr_block": _normalize_cidr(policy.get("CidrBlock")),
        "action": (policy.get("Action") or "").upper(),
        "policy_description": policy.get("PolicyDescription") or "",
        "direction": direction,
    }


def _rule_key(rule):
    return (
        rule["direction"],
        rule["protocol"],
        rule["port"],
        rule["cidr_block"],
        rule["action"],
        rule["policy_description"],
    )


def find_rules(module, client, models, security_group_id):
    """Return the current rules of the group as normalized dicts.

    The API reports egress and ingress rules in separate lists of the
    SecurityGroupPolicySet; the direction is recovered from list membership.
    """
    request = build_describe_request(models, security_group_id)
    response = module.sdk_call(client.DescribeSecurityGroupPolicies, request)
    policy_set = response.SecurityGroupPolicySet
    if policy_set is None:
        return []
    rules = []
    for direction, attribute in (("ingress", "Ingress"), ("egress", "Egress")):
        for policy in (getattr(policy_set, attribute) or []):
            rules.append(normalize_current_rule(policy._serialize(allow_none=True), direction))
    return rules


def reconcile_rules(desired, current, purge):
    """Compute the create/delete delta between desired and current rules.

    Rules are compared as a multiset on (direction, protocol, port,
    cidr_block, action, policy_description) so duplicate identical rules are
    matched one to one. Returns (to_create, to_delete); when purge is false
    the delete list is always empty.
    """
    remaining = {}
    for rule in current:
        remaining.setdefault(_rule_key(rule), []).append(rule)
    to_create = []
    for rule in desired:
        matches = remaining.get(_rule_key(rule))
        if matches:
            matches.pop()
        else:
            to_create.append(rule)
    to_delete = []
    if purge:
        for matches in remaining.values():
            to_delete.extend(matches)
    return to_create, to_delete


def build_policy_set(models, rules, include_description=True):
    """Build a SecurityGroupPolicySet from normalized rules, split by direction."""
    policy_set = models.SecurityGroupPolicySet()
    policy_set.Ingress = []
    policy_set.Egress = []
    for rule in rules:
        policy = models.SecurityGroupPolicy()
        policy.Protocol = rule["protocol"]
        policy.Port = rule["port"]
        policy.CidrBlock = rule["cidr_block"]
        policy.Action = rule["action"]
        if include_description and rule.get("policy_description"):
            policy.PolicyDescription = rule["policy_description"]
        if rule["direction"] == "egress":
            policy_set.Egress.append(policy)
        else:
            policy_set.Ingress.append(policy)
    return policy_set


def create_rules(module, client, models, security_group_id, rules):
    request = models.CreateSecurityGroupPoliciesRequest()
    request.SecurityGroupId = security_group_id
    request.SecurityGroupPolicySet = build_policy_set(models, rules)
    module.sdk_call(client.CreateSecurityGroupPolicies, request)


def delete_rules(module, client, models, security_group_id, rules):
    """Delete rules; the API accepts a single direction per request.

    Rule matching deletion requires only Action, Protocol, CidrBlock and Port,
    so the policy description is left out of the request.
    """
    for direction in ("ingress", "egress"):
        directed = [rule for rule in rules if rule["direction"] == direction]
        if not directed:
            continue
        request = models.DeleteSecurityGroupPoliciesRequest()
        request.SecurityGroupId = security_group_id
        request.SecurityGroupPolicySet = build_policy_set(
            models, directed, include_description=False
        )
        try:
            module.sdk_call(client.DeleteSecurityGroupPolicies, request)
        except Exception as exc:
            if not is_idempotent_success(exc):
                raise


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "security_group_id": {"type": "str", "required": True},
            "rules": {
                "type": "list",
                "elements": "dict",
                "default": [],
                "options": {
                    "protocol": {"type": "str", "required": True},
                    "port": {"type": "str", "default": "all"},
                    "cidr_block": {"type": "str", "required": True},
                    "action": {
                        "type": "str",
                        "choices": ["ACCEPT", "DROP"],
                        "default": "ACCEPT",
                    },
                    "policy_description": {"type": "str", "default": ""},
                    "direction": {
                        "type": "str",
                        "choices": ["ingress", "egress"],
                        "default": "ingress",
                    },
                },
            },
            "purge": {"type": "bool", "default": True},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    security_group_id = module.params["security_group_id"]
    purge = module.params["purge"]
    desired = [normalize_desired_rule(rule) for rule in module.params["rules"]]

    models, vpc_client = _load_vpc()
    client = module.create_client(vpc_client.VpcClient, "vpc.tencentcloudapi.com")

    try:
        current = find_rules(module, client, models, security_group_id)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    to_create, to_delete = reconcile_rules(desired, current, purge)

    if not to_create and not to_delete:
        module.exit_json(
            changed=False,
            security_group_id=security_group_id,
            rules=current,
            msg="Security group rules are up to date",
        )

    after_rules = desired if purge else current + to_create
    diff = maybe_diff(
        module,
        {"security_group_id": security_group_id, "rules": current},
        {"security_group_id": security_group_id, "rules": after_rules},
    )
    if module.check_mode:
        module.exit_json(
            changed=True,
            **(diff or {}),
            security_group_id=security_group_id,
            msg="Would reconcile security group rules",
        )

    if to_create:
        create_rules(module, client, models, security_group_id, to_create)
    if to_delete:
        delete_rules(module, client, models, security_group_id, to_delete)

    updated = find_rules(module, client, models, security_group_id)
    module.exit_json(
        changed=True,
        **(diff or {}),
        security_group_id=security_group_id,
        rules=updated,
        msg="Security group rules reconciled",
    )


def main():
    run_module()


if __name__ == "__main__":
    main()
