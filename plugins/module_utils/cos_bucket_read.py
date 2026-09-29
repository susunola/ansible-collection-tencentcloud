# -*- coding: utf-8 -*-
"""Shared COS bucket configuration reads used by resource and info modules.

Every ``normalize_*`` helper follows one rule: absence reads as ``None``. COS
describes an unset feature either as nothing at all or as an empty envelope
(``{"ResponseControlConfiguration": {}}``), so the response and the
configuration unwrapped from it are both checked for falsiness. The modules
pair a plural return key with a singular one built from
``[value] if value else []``, so ``None`` is the only value that keeps the two
agreeing: a present but empty envelope must not survive as ``{}`` or
``{"Rule": []}``. What a helper reads out of a present configuration follows
the same rule -- a missing counter is zero, an absent rule is no rule.
"""

from __future__ import absolute_import, division, print_function

import copy

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos


def _read(method, bucket, normalizer, **kwargs):
    try:
        return normalizer(method(Bucket=bucket, **kwargs))
    except Exception as exc:
        if cos.is_not_found(exc):
            return None
        raise


def normalize_certificate(value):
    if not value:
        return None
    root = value.get("DomainCertificate", value)
    if not root:
        return None
    info = root.get("CertificateInfo") or {}
    return {"Status": root.get("Status"), "CertType": root.get("CertType") or info.get("CertType"), "CertificateInfo": {"CertID": info.get("CertID")}}


def get_certificate(client, bucket, domain_name):
    return _read(client.get_bucket_domain_certificate, bucket, normalize_certificate, DomainName=domain_name)


def normalize_domains(value):
    if not value:
        return None
    root = value.get("DomainConfiguration", value)
    if not root:
        return None
    rules = root.get("DomainRule") or []
    if isinstance(rules, dict):
        rules = [rules]
    return {"DomainRule": sorted(rules, key=lambda item: item.get("Name") or "")}


def get_domains(client, bucket):
    try:
        response = client.get_bucket_domain(Bucket=bucket)
        return normalize_domains(response), response.get("x-cos-domain-txt-verification")
    except Exception as exc:
        if cos.is_not_found(exc):
            return None, None
        raise


def normalize_tiering(value):
    if not value:
        return None
    root = value.get("IntelligentTieringConfiguration", value)
    if not root:
        return None
    tiering = root.get("Tiering") or {}
    return {"Id": root.get("Id") or "default", "Status": root.get("Status"),
            "Tiering": {"AccessTier": tiering.get("AccessTier"), "Days": int(tiering.get("Days") or 0),
                        "RequestFrequent": int(tiering.get("RequestFrequent") or 0)}}


def get_rule(client, bucket):
    return _read(client.get_bucket_intelligenttiering_v2, bucket, normalize_tiering, Id="default")


def normalize_inventory(value, inventory_id):
    if not value:
        return None
    root = value.get("InventoryConfiguration", value)
    if not root:
        return None
    result = copy.deepcopy(root)
    result["Id"] = inventory_id
    optional = result.get("OptionalFields")
    if optional and isinstance(optional.get("Field"), list):
        optional["Field"] = sorted(optional["Field"])
    return result


def get_inventory(client, bucket, inventory_id):
    return _read(client.get_bucket_inventory, bucket,
                 lambda value: normalize_inventory(value, inventory_id), Id=inventory_id)


def normalize_object_lock(value):
    if not value:
        return None
    root = value.get("ObjectLockConfiguration", value)
    if not root:
        return None
    result = {"ObjectLockEnabled": root.get("ObjectLockEnabled")}
    rule = root.get("Rule") or {}
    retention = rule.get("DefaultRetention") or {}
    if retention:
        normalized = {"Mode": retention.get("Mode")}
        if retention.get("Days") is not None:
            normalized["Days"] = int(retention["Days"])
        if retention.get("Years") is not None:
            normalized["Years"] = int(retention["Years"])
        result["Rule"] = {"DefaultRetention": normalized}
    return result


def get_object_lock(client, bucket):
    return _read(client.get_bucket_object_lock, bucket, normalize_object_lock)


def normalize_origin(value):
    if not value:
        return None
    root = value.get("OriginConfiguration", value)
    if not root:
        return None
    rules = root.get("OriginRule") or []
    if isinstance(rules, dict):
        rules = [rules]
    return {"OriginRule": sorted(rules, key=lambda item: int(item.get("RulePriority") or 0))}


def get_origin(client, bucket):
    return _read(client.get_bucket_origin, bucket, normalize_origin)


def normalize_referer(value):
    if not value:
        return None
    root = value.get("RefererConfiguration", value)
    if not root:
        return None
    if root.get("Status") != "Enabled":
        return None
    domains = (root.get("DomainList") or {}).get("Domain") or []
    if isinstance(domains, str):
        domains = [domains]
    return {"Status": "Enabled", "RefererType": root.get("RefererType"),
            "EmptyReferConfiguration": root.get("EmptyReferConfiguration"),
            "DomainList": {"Domain": sorted(domains)}}


def get_referer(client, bucket):
    return _read(client.get_bucket_referer, bucket, normalize_referer)


def normalize_replication(value):
    if not value:
        return None
    root = value.get("ReplicationConfiguration", value)
    if not root:
        return None
    rules = root.get("Rule") or []
    return {"Role": root.get("Role"), "Rule": sorted(rules, key=lambda x: (x.get("ID") or "", x.get("Prefix") or ""))}


def get_replication(client, bucket):
    return _read(client.get_bucket_replication, bucket, normalize_replication)


def normalize_control(value):
    if not value:
        return None
    root = value.get("ResponseControlConfiguration", value)
    if not root:
        return None
    params = (root.get("ControlParamList") or {}).get("Param") or []
    if isinstance(params, str):
        params = [params]
    return {"ControlParamList": {"Param": sorted(params)}}


def get_control(client, bucket):
    return _read(client.get_bucket_response_control, bucket, normalize_control)
