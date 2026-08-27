#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: ssl_certificate
short_description: Manage Tencent Cloud SSL certificates
version_added: "0.12.0"
description:
  - Upload, rename, deploy and delete SSL certificates through the
    C(ssl.v20191205) API.
  - This module is idempotent. Running it twice leaves the certificate
    unchanged and the second run reports C(changed=false).
  - Supports check mode; no API write happens in check mode, only reads.
  - A certificate is identified by O(certificate_id) or by O(alias). When
    neither exists and O(cert_content) is given, the certificate is
    uploaded.
  - Deployment pushes the certificate to cloud resources (e.g. CLB
    instances) with V(DeployCertificateInstance), closing the loop with the
    C(cert_id) value of the C(certificate) suboption of
    M(susunola.tencentcloud.clb_listener) and M(susunola.tencentcloud.clb_rule).
options:
  state:
    description:
      - C(present) uploads the certificate when it does not exist, renames it
        when O(alias) differs, and deploys it when O(deploy_instances) is
        given.
      - C(absent) deletes the certificate.
    type: str
    choices: [present, absent]
    default: present
  certificate_id:
    description:
      - ID of an existing certificate, e.g. C(XXXX-XXXX-XXXX).
      - When given, the module operates on that certificate; otherwise it is
        matched by O(alias).
    type: str
  alias:
    description:
      - Name of the certificate, written to V(UploadCertificateRequest.Alias)
        and V(ModifyCertificateAliasRequest.Alias).
    type: str
  cert_content:
    description:
      - PEM content of the certificate public key, written to
        V(UploadCertificateRequest.CertificatePublicKey).
      - Required to upload a new certificate.
    type: str
  private_key:
    description:
      - PEM content of the certificate private key, written to
        V(UploadCertificateRequest.CertificatePrivateKey).
      - Required to upload a new certificate. The value is masked from
        output automatically.
    type: str
  certificate_type:
    description:
      - Type of the certificate, written to
        V(UploadCertificateRequest.CertificateType).
    type: str
    choices: [CA, SVR]
    default: SVR
  project_id:
    description:
      - Project the certificate belongs to, written to
        V(UploadCertificateRequest.ProjectId).
    type: int
  deploy_instances:
    description:
      - IDs of the instances to deploy the certificate to (e.g. CLB load
        balancer IDs), written to V(DeployCertificateInstanceRequest.
        InstanceIdList).
      - Deployment is skipped when the list is empty.
    type: list
    elements: str
  resource_type:
    description:
      - Resource type of O(deploy_instances), written to
        V(DeployCertificateInstanceRequest.ResourceType).
    type: str
    default: clb
  tags:
    description:
      - Tags to apply to the certificate as a dict, for example I(env=prod).
      - Only applied at upload.
    type: dict
    default: {}
  retries:
    description: Number of retries for transient SDK failures.
    type: int
    default: 5
  waiter_delay:
    description: Seconds to wait between state-polling attempts.
    type: int
    default: 5
  waiter_timeout:
    description: Overall timeout in seconds for state polling.
    type: int
    default: 120
  user_agent:
    description:
      - Value appended to the SDK User-Agent header so API usage can be
        attributed to this collection.
    type: str
    default: ansible-collection.susunola.tencentcloud
notes:
  - Requires the C(tencentcloud-sdk-python-ssl) package on the controller.
  - Keep O(private_key) out of V(--check) output; use V(no_log) on the task
    or V(ANSIBLE_NO_LOG) when the value must be masked.
extends_documentation_fragment: susunola.tencentcloud.tencentcloud
author: Tencent Cloud Ansible Collection Contributors (@susunola)
'''

EXAMPLES = r'''
- name: Upload a certificate and deploy it to a CLB instance
  susunola.tencentcloud.ssl_certificate:
    region: ap-guangzhou
    state: present
    alias: api-tls
    cert_content: "{{ lookup('ansible.builtin.file', 'api.crt') }}"
    private_key: "{{ lookup('ansible.builtin.file', 'api.key') }}"
    deploy_instances:
      - lb-xxxxxxxx
    resource_type: clb

- name: Reference the certificate from a CLB HTTPS listener
  susunola.tencentcloud.clb_listener:
    region: ap-guangzhou
    load_balancer_id: lb-xxxxxxxx
    port: 443
    protocol: HTTPS
    certificate:
      cert_id: "{{ cert.certificate_id }}"
      ssl_mode: MUTUAL

- name: Delete the certificate
  susunola.tencentcloud.ssl_certificate:
    region: ap-guangzhou
    state: absent
    alias: api-tls
'''

RETURN = r'''
certificate:
  description: The certificate as reported by V(DescribeCertificates) after
    the operation.
  returned: success
  type: dict
  sample:
    CertificateId: XXXX-XXXX-XXXX
    Alias: api-tls
    CertificateType: SVR
    Status: 1
    Domain: api.example.com
deploy_record_id:
  description: ID of the deployment record when O(deploy_instances) was used.
  returned: when deployed
  type: str
  sample: 12345
'''

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff


def _load_ssl():
    from tencentcloud.ssl.v20191205 import models, ssl_client
    return models, ssl_client


def build_describe_request(models, certificate_id, alias):
    request = models.DescribeCertificatesRequest()
    request.Limit = 100
    if certificate_id:
        request.CertIds = [certificate_id]
    elif alias:
        request.SearchKey = alias
    return request


def _first(collection):
    return collection[0] if collection else None


def find_certificate(module, client, models, certificate_id, alias):
    """Return the matching certificate dict or None."""
    request = build_describe_request(models, certificate_id, alias)
    response = module.sdk_call(client.DescribeCertificates, request)
    if certificate_id:
        cert = _first(response.Certificates or [])
        return cert._serialize(allow_none=True) if cert is not None else None
    for cert in response.Certificates or []:
        current = cert._serialize(allow_none=True)
        if current.get("Alias") == alias:
            return current
    return None


def _upload(module, client, models, params):
    request = models.UploadCertificateRequest()
    request.CertificatePublicKey = params["cert_content"]
    request.CertificatePrivateKey = params["private_key"]
    request.CertificateType = params["certificate_type"]
    if params["alias"]:
        request.Alias = params["alias"]
    if params["project_id"] is not None:
        request.ProjectId = params["project_id"]
    if params["tags"]:
        sdk_tags = []
        for key, value in sorted(params["tags"].items()):
            sdk_tag = models.Tags()
            sdk_tag.TagKey = key
            sdk_tag.TagValue = value
            sdk_tags.append(sdk_tag)
        request.Tags = sdk_tags
    response = module.sdk_call(client.UploadCertificate, request)
    return response.CertificateId


def _rename(module, client, models, certificate_id, alias):
    request = models.ModifyCertificateAliasRequest()
    request.CertificateId = certificate_id
    request.Alias = alias
    module.sdk_call(client.ModifyCertificateAlias, request)


def _deploy(module, client, models, certificate_id, instance_ids, resource_type):
    request = models.DeployCertificateInstanceRequest()
    request.CertificateId = certificate_id
    request.InstanceIdList = instance_ids
    request.ResourceType = resource_type
    response = module.sdk_call(client.DeployCertificateInstance, request)
    return getattr(response, "DeployRecordId", None)


def _delete(module, client, models, certificate_id):
    request = models.DeleteCertificateRequest()
    request.CertificateId = certificate_id
    module.sdk_call(client.DeleteCertificate, request)


def run_module():
    module = TencentCloudModule(
        argument_spec={
            "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
            "certificate_id": {"type": "str"},
            "alias": {"type": "str"},
            "cert_content": {"type": "str"},
            "private_key": {"type": "str", "no_log": True},
            "certificate_type": {"type": "str", "choices": ["CA", "SVR"], "default": "SVR"},
            "project_id": {"type": "int"},
            "deploy_instances": {"type": "list", "elements": "str"},
            "resource_type": {"type": "str", "default": "clb"},
            "tags": {"type": "dict", "default": {}},
        },
        supports_check_mode=True,
    )
    module.require_sdk()

    state = module.params["state"]
    certificate_id = module.params["certificate_id"]
    alias = module.params["alias"]

    if not certificate_id and not alias:
        module.fail_json(msg="certificate_id or alias is required to identify the certificate")

    models, ssl_client = _load_ssl()
    client = module.create_client(ssl_client.SslClient, "ssl.tencentcloudapi.com")

    try:
        current = find_certificate(module, client, models, certificate_id, alias)
    except Exception as exc:
        module.fail_json(
            msg="Tencent Cloud API request failed",
            error=str(exc),
            error_code=getattr(exc, "get_code", lambda: None)(),
            request_id=getattr(exc, "get_request_id", lambda: None)(),
        )

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, msg="Certificate already absent")
        diff = maybe_diff(module, current, None)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would delete certificate")
        _delete(module, client, models, current["CertificateId"])
        module.exit_json(changed=True, **(diff or {}), certificate=None, msg="Certificate deleted")

    # state == present
    deploy_instances = module.params["deploy_instances"] or []
    if current is None:
        if not module.params["cert_content"] or not module.params["private_key"]:
            module.fail_json(msg="cert_content and private_key are required to upload a certificate")
        desired = {
            "Alias": alias,
            "CertificateType": module.params["certificate_type"],
        }
        diff = maybe_diff(module, None, desired)
        if module.check_mode:
            module.exit_json(changed=True, **(diff or {}), msg="Would upload certificate")
        uploaded_id = _upload(module, client, models, module.params)
        result = {
            "CertificateId": uploaded_id,
            "Alias": alias,
            "CertificateType": module.params["certificate_type"],
        }
        deploy_record_id = None
        if deploy_instances:
            deploy_record_id = _deploy(
                module, client, models, uploaded_id, deploy_instances, module.params["resource_type"]
            )
            result["DeployedTo"] = deploy_instances
        module.exit_json(
            changed=True, **(diff or {}), certificate=result,
            deploy_record_id=deploy_record_id, msg="Certificate uploaded",
        )

    target_id = current["CertificateId"]
    changes = []
    if alias and current.get("Alias") != alias:
        changes.append("alias")
    if deploy_instances:
        changes.append("deploy")

    if not changes:
        module.exit_json(changed=False, certificate=current, msg="Certificate is up to date")

    diff = maybe_diff(module, current, {
        "Alias": alias or current.get("Alias"),
    })
    if module.check_mode:
        module.exit_json(changed=True, **(diff or {}), msg="Would update certificate")

    if "alias" in changes:
        _rename(module, client, models, target_id, alias)
    deploy_record_id = None
    if "deploy" in changes:
        deploy_record_id = _deploy(
            module, client, models, target_id, deploy_instances, module.params["resource_type"]
        )
    updated = find_certificate(module, client, models, target_id, None)
    module.exit_json(
        changed=True, **(diff or {}), certificate=updated,
        deploy_record_id=deploy_record_id, msg="Certificate updated",
    )


def main():
    run_module()


if __name__ == "__main__":
    main()
