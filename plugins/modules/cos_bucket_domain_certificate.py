#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: cos_bucket_domain_certificate
short_description: Manage Tencent Cloud COS custom-domain certificates
version_added: "0.14.0"
description:
  - Binds a Tencent Cloud SSL certificate to one COS custom domain.
  - Uses certificate IDs so the desired certificate can be read back and reconciled reliably.
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  name: {type: str, required: true, description: Bucket short name or full name.}
  appid: {type: str, description: Tencent Cloud AppId used in the bucket suffix.}
  domain_name: {type: str, required: true, description: Custom domain bound to the bucket.}
  certificate_id: {type: str, description: Tencent Cloud SSL certificate ID.}
  retries: {description: Number of retries for transient failures., type: int, default: 5}
  waiter_delay: {description: Seconds between polling attempts., type: int, default: 5}
  waiter_timeout: {description: Overall polling timeout in seconds., type: int, default: 120}
  user_agent: {description: User-Agent suffix., type: str, default: ansible-collection.susunola.tencentcloud}
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- name: Bind a managed SSL certificate
  susunola.tencentcloud.cos_bucket_domain_certificate:
    region: ap-guangzhou
    name: public-site
    domain_name: static.example.com
    certificate_id: 8u9example

- name: Remove the domain certificate
  susunola.tencentcloud.cos_bucket_domain_certificate:
    region: ap-guangzhou
    name: public-site
    domain_name: static.example.com
    state: absent
"""
RETURN = r"""domain_certificate: {description: Effective certificate status and identity., type: dict, returned: always}"""

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def normalize(value):
    if not value:
        return None
    root = value.get("DomainCertificate", value)
    info = root.get("CertificateInfo") or {}
    return {"Status": root.get("Status"), "CertType": root.get("CertType") or info.get("CertType"), "CertificateInfo": {"CertID": info.get("CertID")}}


def get_certificate(client, bucket, domain_name):
    try:
        return normalize(client.get_bucket_domain_certificate(Bucket=bucket, DomainName=domain_name))
    except Exception as exc:
        if cos.is_not_found(exc):
            return None
        raise


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"choices": ["present", "absent"], "default": "present"},
            "name": {"required": True},
            "appid": {},
            "domain_name": {"required": True},
            "certificate_id": {},
        },
        required_if=[("state", "present", ["certificate_id"])],
        supports_check_mode=True,
    )
    p = module.params
    cos.require_cos_sdk(module)
    bucket = cos.bucket_full_name(p["name"], cos.resolve_appid(module))
    client = cos.create_cos_client(module)
    try:
        current = get_certificate(client, bucket, p["domain_name"])
        target = {"Status": "Enabled", "CertType": "CustomCert", "CertificateInfo": {"CertID": p["certificate_id"]}} if p["state"] == "present" else None
        if current == target:
            module.exit_json(changed=False, domain_certificate=current)
        diff = maybe_diff(module, current, target)
        if not module.check_mode:
            if target is None:
                client.delete_bucket_domain_certificate(Bucket=bucket, DomainName=p["domain_name"])
            else:
                config = {
                    "DomainList": {"DomainName": [p["domain_name"]]},
                    "CertificateInfo": {"CertType": "CustomCert", "CustomCert": {"CertID": p["certificate_id"]}},
                }
                client.put_bucket_domain_certificate(Bucket=bucket, DomainCertificateConfiguration=config)
        module.exit_json(changed=True, **(diff or {}), domain_certificate=target)
    except Exception as exc:
        cos.fail_on_cos_error(module, exc)


def main():
    run_module()


if __name__ == "__main__":
    main()
