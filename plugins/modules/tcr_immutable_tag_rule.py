#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: tcr_immutable_tag_rule
short_description: Create or delete a Tencent Cloud TCR immutable tag rule
version_added: "1.1.0"
description:
  - Creates or deletes a Tencent Cloud Container Registry (TCR) immutable tag
    rule inside a namespace, identified by its repository and tag patterns. The
    module is idempotent; it reads the current immutable tag rules in the
    registry before changing anything and matches on the repository pattern,
    tag pattern and namespace.
  - The rule payload is a raw SDK-shaped dictionary (the C(sub)fields of
    C(ImmutableTagRule)) passed through verbatim, because the nested model mixes
    fuzzy enumeration values with free-form patterns that do not map cleanly to
    Ansible suboptions. Provide at least C(RepositoryPattern) and C(TagPattern)
    to identify the rule; C(RepositoryDecoration), C(TagDecoration) and
    C(Disabled) are optional.
options:
  state:
    description: Desired state of the immutable tag rule.
    type: str
    choices: [present, absent]
    default: present
  registry_id:
    description: ID of the TCR instance (registry) that owns the namespace.
    type: str
    required: true
  namespace_name:
    description: Name of the namespace the rule applies to.
    type: str
    required: true
  rule:
    description: Raw SDK-shaped immutable tag rule payload (C(ImmutableTagRule)).
    type: dict
    required: true
    suboptions:
      RepositoryPattern:
        description: Repository name match pattern (e.g. C(repo*)).
        type: str
      TagPattern:
        description: Tag match pattern (e.g. C(latest) or C(v*)).
        type: str
      RepositoryDecoration:
        description: C(repoMatches) or C(repoExcludes).
        type: str
      TagDecoration:
        description: C(matches) or C(excludes).
        type: str
      Disabled:
        description: Whether the rule is disabled.
        type: bool
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
- name: Make the latest tag immutable for a repository in a namespace
  susunola.tencentcloud.tcr_immutable_tag_rule:
    registry_id: tcr-abc123
    namespace_name: production
    rule:
      RepositoryPattern: "web-*"
      TagPattern: "latest"
      RepositoryDecoration: repoMatches
      TagDecoration: matches

- name: Remove the immutable tag rule
  susunola.tencentcloud.tcr_immutable_tag_rule:
    registry_id: tcr-abc123
    namespace_name: production
    rule:
      RepositoryPattern: "web-*"
      TagPattern: "latest"
    state: absent
'''

RETURN = r'''
registry_id:
  description: Registry ID the operation targeted.
  returned: always
  type: str
namespace_name:
  description: Namespace name the operation targeted.
  returned: always
  type: str
rule_id:
  description: Server-assigned rule ID after a create, or the matched rule ID.
  returned: always
  type: int
exists:
  description: Whether the immutable tag rule exists after the operation.
  returned: always
  type: bool
'''

import json

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def _load_tcr():
    from tencentcloud.tcr.v20190924 import models, tcr_client
    return models, tcr_client


def find_rule(module, client, models, registry_id, namespace_name, repo_pattern, tag_pattern):
    request = models.DescribeImmutableTagRulesRequest()
    request.RegistryId = registry_id
    request.Page = 1
    request.PageSize = 100
    response = module.sdk_call(client.DescribeImmutableTagRules, request)
    rules = list(getattr(response, "Rules", None) or [])
    for item in rules:
        if (getattr(item, "NsName", None) == namespace_name
                and getattr(item, "RepositoryPattern", None) == repo_pattern
                and getattr(item, "TagPattern", None) == tag_pattern):
            return item
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "registry_id": {"type": "str", "required": True},
            "namespace_name": {"type": "str", "required": True},
            "rule": {"type": "dict", "required": True},
        },
        supports_check_mode=True,
    )
    p = module.params
    registry_id = p["registry_id"]
    namespace_name = p["namespace_name"]
    rule = p["rule"] or {}
    repo_pattern = rule.get("RepositoryPattern")
    tag_pattern = rule.get("TagPattern")
    if not repo_pattern or not tag_pattern:
        module.fail_json(
            msg="rule.RepositoryPattern and rule.TagPattern are required to identify an immutable tag rule")
    desired_present = p["state"] == "present"
    module.require_sdk()
    models, tcr_client = _load_tcr()
    client = module.create_client(tcr_client.TcrClient, "tcr.tencentcloudapi.com")
    try:
        current = find_rule(module, client, models, registry_id, namespace_name, repo_pattern, tag_pattern)
        if bool(current) == desired_present:
            module.exit_json(
                changed=False,
                registry_id=registry_id,
                namespace_name=namespace_name,
                rule_id=getattr(current, "RuleId", None),
                exists=bool(current),
                msg="Immutable tag rule already %s" % ("present" if desired_present else "absent"),
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                registry_id=registry_id,
                namespace_name=namespace_name,
                rule_id=None,
                exists=desired_present,
                msg="Would %s immutable tag rule" % ("create" if desired_present else "delete"),
            )
        if desired_present:
            payload = {"RegistryId": registry_id, "NamespaceName": namespace_name, "Rule": rule}
            request = models.CreateImmutableTagRulesRequest()
            request.from_json_string(json.dumps(payload))
            module.sdk_call(client.CreateImmutableTagRules, request)
        else:
            request = models.DeleteImmutableTagRulesRequest()
            request.RegistryId = registry_id
            request.NamespaceName = namespace_name
            request.RuleId = getattr(current, "RuleId", None)
            module.sdk_call(client.DeleteImmutableTagRules, request)
        final = find_rule(module, client, models, registry_id, namespace_name, repo_pattern, tag_pattern)
        module.exit_json(
            changed=True,
            registry_id=registry_id,
            namespace_name=namespace_name,
            rule_id=getattr(final, "RuleId", None) if final else None,
            exists=bool(final),
            msg="Immutable tag rule %s" % ("created" if desired_present else "deleted"),
        )
    except Exception as exc:
        module.fail_sdk_error(exc, "Tencent Cloud TCR immutable tag rule request failed")


def main():
    run_module()


if __name__ == "__main__":
    main()
