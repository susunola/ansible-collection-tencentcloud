#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: scf_custom_domain
short_description: Create or delete a Tencent Cloud SCF custom domain
version_added: "1.1.0"
description:
  - Creates or deletes a Tencent Cloud SCF (Serverless Cloud Function) custom
    domain, identified by its domain name. The module is idempotent; it reads
    the current custom domains before changing anything.
  - Only the domain name and protocol are set on create. Certificate, WAF and
    endpoint routing configuration are managed outside this module (they are
    immutable after creation and updated through the console or a separate
    raw-payload increment).
options:
  state:
    description: Desired state of the custom domain.
    type: str
    choices: [present, absent]
    default: present
  domain:
    description: Custom domain name to create or delete.
    type: str
    required: true
  protocol:
    description: Protocol the custom domain serves.
    type: str
    choices: [HTTP, HTTPS, HTTP&HTTPS]
    default: HTTP
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
- name: Create an SCF custom domain
  susunola.tencentcloud.scf_custom_domain:
    domain: functions.example.com
    protocol: HTTPS

- name: Delete an SCF custom domain
  susunola.tencentcloud.scf_custom_domain:
    domain: functions.example.com
    state: absent
'''

RETURN = r'''
domain:
  description: Custom domain name the operation targeted.
  returned: always
  type: str
exists:
  description: Whether the custom domain exists after the operation.
  returned: always
  type: bool
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule


def _load_scf():
    from tencentcloud.scf.v20180416 import models, scf_client
    return models, scf_client


def find_domain(module, client, models, domain):
    request = models.ListCustomDomainsRequest()
    flt = models.Filter()
    flt.Name = "Domain"
    flt.Values = [domain]
    request.Filters = [flt]
    request.Limit = 100
    request.Offset = 0
    response = module.sdk_call(client.ListCustomDomains, request)
    domains = list(getattr(response, "Domains", None) or [])
    for item in domains:
        if getattr(item, "Domain", None) == domain:
            return item
    return None


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "domain": {"type": "str", "required": True},
            "protocol": {"type": "str", "choices": ["HTTP", "HTTPS", "HTTP&HTTPS"], "default": "HTTP"},
        },
        supports_check_mode=True,
    )
    p = module.params
    domain = p["domain"]
    desired_present = p["state"] == "present"
    module.require_sdk()
    models, scf_client = _load_scf()
    client = module.create_client(scf_client.ScfClient, "scf.tencentcloudapi.com")
    try:
        current = find_domain(module, client, models, domain)
        if bool(current) == desired_present:
            module.exit_json(
                changed=False,
                domain=domain,
                exists=bool(current),
                msg="Custom domain %s already %s" % (domain, "present" if desired_present else "absent"),
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                domain=domain,
                exists=desired_present,
                msg="Would %s custom domain %s" % ("create" if desired_present else "delete", domain),
            )
        if desired_present:
            request = models.CreateCustomDomainRequest()
            request.Domain = domain
            request.Protocol = p["protocol"]
            module.sdk_call(client.CreateCustomDomain, request)
        else:
            request = models.DeleteCustomDomainRequest()
            request.Domain = domain
            module.sdk_call(client.DeleteCustomDomain, request)
        final = find_domain(module, client, models, domain)
        module.exit_json(
            changed=True,
            domain=domain,
            exists=bool(final),
            msg="Custom domain %s %s" % (domain, "created" if desired_present else "deleted"),
        )
    except Exception as exc:
        module.fail_sdk_error(exc, "Tencent Cloud SCF custom domain request failed")


def main():
    run_module()


if __name__ == "__main__":
    main()
