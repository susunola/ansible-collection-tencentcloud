#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = r"""
---
module: tse_gateway_certificate
short_description: Manage a Tencent Cloud TSE gateway certificate
version_added: "0.14.0"
description:
  - Manages native PEM and Tencent Cloud SSL-platform certificates on a cloud-native gateway.
  - Private keys are never returned. Native or SSL certificate material changes require C(rotate_certificate=true).
options:
  state: {type: str, choices: [present, absent], default: present, description: Desired state.}
  gateway_id: {type: str, required: true, description: Gateway ID.}
  certificate_id: {type: str, description: Existing gateway certificate ID.}
  name: {type: str, description: Instance-unique certificate name.}
  cert_source: {type: str, choices: [native, ssl], description: Certificate source.}
  ssl_certificate_id: {type: str, description: Tencent Cloud SSL-platform certificate ID.}
  private_key: {type: str, description: Native PEM private key.}
  certificate: {type: str, description: Native PEM certificate chain.}
  bind_domains: {type: list, elements: str, description: Bound domain names.}
  cert_type: {type: str, choices: [SVR, CA], description: Certificate type.}
  cert_usage: {type: str, choices: [SERVER, CLIENT], description: Certificate usage.}
  rotate_certificate: {type: bool, default: false, description: Explicitly replace certificate material in place.}
  force_delete: {type: bool, default: false, description: Delete even when the API reports active references.}

extends_documentation_fragment:
  - susunola.tencentcloud.credentials
  - susunola.tencentcloud.region
  - susunola.tencentcloud.connection
  - susunola.tencentcloud.retry
  - susunola.tencentcloud.user_agent
author: Tencent Cloud Ansible Collection Contributors (@susunola)
"""
EXAMPLES = r"""
- susunola.tencentcloud.tse_gateway_certificate:
    gateway_id: gateway-xxxxxxxx
    name: public-api
    cert_source: ssl
    ssl_certificate_id: jDZJ5jSa
    bind_domains: [api.example.com]
    cert_type: SVR
    cert_usage: SERVER
"""
RETURN = r"""certificate_info: {description: Effective certificate metadata with private key redacted., type: dict, returned: always}"""
import json
from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.module_utils.comparison import maybe_diff
from ansible_collections.susunola.tencentcloud.plugins.module_utils.lifecycle import sdk_error_payload


def _load():
    from tencentcloud.tse.v20201207 import models, tse_client

    return models, tse_client


def scrub(value):
    if isinstance(value, dict):
        return {key: scrub(item) for key, item in value.items() if key != "Key"}
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value


def list_request(models, p, offset=0):
    r = models.DescribeCloudNativeAPIGatewayCertificatesRequest()
    r.GatewayId, r.Offset, r.Limit, r.CertType, r.CertUsage = p["gateway_id"], offset, 20, p.get("cert_type"), p.get("cert_usage")
    return r


def detail_request(models, p, certificate_id):
    r = models.DescribeCloudNativeAPIGatewayCertificateDetailsRequest()
    r.GatewayId, r.Id = p["gateway_id"], certificate_id
    return r


def delete_request(models, p, current):
    r = models.DeleteCloudNativeAPIGatewayCertificateRequest()
    r.GatewayId, r.Id = p["gateway_id"], current["Id"]
    return r


def create_payload(p):
    payload = {
        "GatewayId": p["gateway_id"],
        "Name": p["name"],
        "BindDomains": p.get("bind_domains") or [],
        "CertType": p["cert_type"],
        "CertUsage": p["cert_usage"],
    }
    if p["cert_source"] == "ssl":
        payload["CertId"] = p["ssl_certificate_id"]
    else:
        payload.update({"Key": p["private_key"], "Crt": p["certificate"]})
    return payload


def modify_payload(p, current):
    source = p.get("cert_source") or current["CertSource"]
    payload = {
        "GatewayId": p["gateway_id"],
        "Id": current["Id"],
        "Name": p.get("name") or current.get("Name"),
        "BindDomains": p.get("bind_domains") if p.get("bind_domains") is not None else current.get("BindDomains"),
        "CertSource": source,
    }
    if source == "ssl":
        payload["CertId"] = p.get("ssl_certificate_id") or current.get("CertId")
    else:
        payload.update({"Key": p.get("private_key"), "Crt": p.get("certificate") or current.get("Crt")})
    return payload


def metadata_request(models, p, current):
    r = models.UpdateCloudNativeAPIGatewayCertificateInfoRequest()
    r.GatewayId, r.Id = p["gateway_id"], current["Id"]
    r.Name = p.get("name") or current.get("Name")
    r.BindDomains = p.get("bind_domains") if p.get("bind_domains") is not None else current.get("BindDomains")
    return r


def json_request(cls, payload):
    r = cls()
    r.from_json_string(json.dumps(payload))
    return r


def find(module, client, models, p):
    offset = 0
    matches = []
    while True:
        result = module.sdk_call(client.DescribeCloudNativeAPIGatewayCertificates, list_request(models, p, offset)).Result
        values = result.CertificatesList if result else []
        for item in values or []:
            value = scrub(item._serialize(allow_none=True))
            if (p.get("certificate_id") and value.get("Id") == p["certificate_id"]) or (not p.get("certificate_id") and value.get("Name") == p["name"]):
                matches.append(value)
        offset += len(values or [])
        if not result or offset >= int(result.Total or 0):
            break
    if len(matches) > 1:
        module.fail_json(msg="Multiple TSE gateway certificates matched; specify certificate_id")
    if not matches:
        return None
    detail = module.sdk_call(client.DescribeCloudNativeAPIGatewayCertificateDetails, detail_request(models, p, matches[0]["Id"])).Result
    if detail and detail.Cert:
        return scrub(detail.Cert._serialize(allow_none=True))
    return matches[0]


def validate_create(module, p):
    missing = [key for key in ("name", "cert_source", "cert_type", "cert_usage") if not p.get(key)]
    if missing:
        module.fail_json(msg="Required for certificate creation: %s" % ", ".join(missing))
    if p["cert_source"] == "ssl" and not p.get("ssl_certificate_id"):
        module.fail_json(msg="ssl_certificate_id is required when cert_source=ssl")
    if p["cert_source"] == "native" and (not p.get("private_key") or not p.get("certificate")):
        module.fail_json(msg="private_key and certificate are required when cert_source=native")


def run_module():
    spec = {
        "state": {"choices": ["present", "absent"], "default": "present"},
        "gateway_id": {"required": True},
        "certificate_id": {},
        "name": {},
        "cert_source": {"choices": ["native", "ssl"]},
        "ssl_certificate_id": {},
        "private_key": {"no_log": True},
        "certificate": {},
        "bind_domains": {"type": "list", "elements": "str"},
        "cert_type": {"choices": ["SVR", "CA"]},
        "cert_usage": {"choices": ["SERVER", "CLIENT"]},
        "rotate_certificate": {"type": "bool", "default": False},
        "force_delete": {"type": "bool", "default": False},
    }
    module = TencentCloudModule(argument_spec=spec, required_one_of=[("certificate_id", "name")], supports_check_mode=True)
    p = module.params
    module.require_sdk()
    models, cm = _load()
    client = module.create_client(cm.TseClient, "tse.tencentcloudapi.com")
    try:
        current = find(module, client, models, p)
        if p["state"] == "absent":
            if not current:
                module.exit_json(changed=False, certificate_info=None)
            if int(current.get("ReferCount") or 0) > 0 and not p["force_delete"]:
                module.fail_json(msg="Certificate is still referenced; set force_delete=true to override", certificate_info=current)
            diff = maybe_diff(module, current, None)
            if not module.check_mode:
                module.sdk_call(client.DeleteCloudNativeAPIGatewayCertificate, delete_request(models, p, current))
            module.exit_json(changed=True, **(diff or {}), certificate_info=None)
        if not current:
            validate_create(module, p)
        if current:
            source = p.get("cert_source") or current.get("CertSource")
            immutable = {
                "CertSource": source,
                "CertType": p.get("cert_type") or current.get("CertType"),
                "CertUsage": p.get("cert_usage") or current.get("CertUsage"),
            }
            before = {key: current.get(key) for key in immutable}
            if before != immutable:
                module.fail_json(msg="cert_source, cert_type and cert_usage cannot be changed in place", immutable_before=before, immutable_after=immutable)
            material_changed = (source == "ssl" and p.get("ssl_certificate_id") and p["ssl_certificate_id"] != current.get("CertId")) or (
                source == "native" and p.get("certificate") and p["certificate"] != current.get("Crt")
            )
            if material_changed and not p["rotate_certificate"]:
                module.fail_json(msg="Certificate material differs; set rotate_certificate=true to replace it")
            if p["rotate_certificate"]:
                if source == "ssl" and not p.get("ssl_certificate_id"):
                    module.fail_json(msg="ssl_certificate_id is required for SSL certificate rotation")
                if source == "native" and (not p.get("private_key") or not p.get("certificate")):
                    module.fail_json(msg="private_key and certificate are required for native certificate rotation")
            target = {
                "Name": p.get("name") or current.get("Name"),
                "BindDomains": p.get("bind_domains") if p.get("bind_domains") is not None else current.get("BindDomains"),
                "CertId": p.get("ssl_certificate_id") or current.get("CertId"),
                "Crt": p.get("certificate") or current.get("Crt"),
            }
            before = {key: current.get(key) for key in target}
            changed = before != target or p["rotate_certificate"]
            if not changed:
                module.exit_json(changed=False, certificate_info=current)
            material_update = material_changed or p["rotate_certificate"]
            if material_update and source == "native" and (not p.get("private_key") or not (p.get("certificate") or current.get("Crt"))):
                module.fail_json(msg="private_key and certificate are required to rotate a native certificate")
            diff = maybe_diff(module, before, target)
            if not module.check_mode:
                if material_update:
                    module.sdk_call(
                        client.ModifyCloudNativeAPIGatewayCertificate,
                        json_request(models.ModifyCloudNativeAPIGatewayCertificateRequest, modify_payload(p, current)),
                    )
                else:
                    module.sdk_call(client.UpdateCloudNativeAPIGatewayCertificateInfo, metadata_request(models, p, current))
                current = find(module, client, models, p)
            module.exit_json(changed=True, **(diff or {}), certificate_info=current if not module.check_mode else target)
        diff = maybe_diff(module, None, scrub(create_payload(p)))
        if not module.check_mode:
            response = module.sdk_call(
                client.CreateCloudNativeAPIGatewayCertificate, json_request(models.CreateCloudNativeAPIGatewayCertificateRequest, create_payload(p))
            )
            p["certificate_id"] = response.Result.Id
            current = find(module, client, models, p)
        module.exit_json(changed=True, **(diff or {}), certificate_info=current if not module.check_mode else scrub(create_payload(p)))
    except Exception as exc:
        module.fail_json(**sdk_error_payload(exc))


def main():
    run_module()


if __name__ == "__main__":
    main()
