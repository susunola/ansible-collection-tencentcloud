# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Tencent Cloud Ansible Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Unit tests for the shared COS bucket-configuration readers.

Eight ``normalize_*`` functions turn what the COS SDK returns into the shape
the modules compare against, and eight ``get_*`` functions wrap the read calls
with the not-found handling every caller needs.

Two properties are why this file exists rather than leaving it to the module
tests. COS returns a *bare mapping* where you would expect a list when a
configuration holds a single rule, and a *bare string* where you would expect a
list when it holds a single domain -- so ``DomainRule``, ``OriginRule``,
``DomainList.Domain`` and ``ControlParamList.Param`` each have a coercion
branch. The module tests all pass well-formed payloads, so none of those
branches ran: ``cos_bucket_read.py`` was 89% covered with every miss on a
defensive path, which is the path the API reaches on its own.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos_bucket_read


# ---------------------------------------------------------------------------
# empty payloads
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("normalizer, extra", [
    ("normalize_certificate", ()),
    ("normalize_domains", ()),
    ("normalize_tiering", ()),
    ("normalize_object_lock", ()),
    ("normalize_origin", ()),
    ("normalize_referer", ()),
    ("normalize_replication", ()),
    ("normalize_control", ()),
])
def test_an_empty_read_is_none(normalizer, extra):
    """COS answers an unset bucket configuration with nothing at all, and a
    module compares against None to know the feature is off."""
    assert getattr(cos_bucket_read, normalizer)(None, *extra) is None
    assert getattr(cos_bucket_read, normalizer)({}, *extra) is None


# ---------------------------------------------------------------------------
# the root key may or may not be wrapped
# ---------------------------------------------------------------------------

def test_certificate_accepts_the_wrapped_and_bare_shape():
    wrapped = {"DomainCertificate": {"Status": "Enabled", "CertType": "Custom",
                                     "CertificateInfo": {"CertID": "cert-1"}}}
    bare = {"Status": "Enabled", "CertType": "Custom", "CertificateInfo": {"CertID": "cert-1"}}
    assert cos_bucket_read.normalize_certificate(wrapped) == {
        "Status": "Enabled", "CertType": "Custom", "CertificateInfo": {"CertID": "cert-1"}}
    assert cos_bucket_read.normalize_certificate(bare) == cos_bucket_read.normalize_certificate(wrapped)


def test_certificate_falls_back_to_the_certificate_info_type():
    value = {"DomainCertificate": {"Status": "Enabled", "CertificateInfo": {"CertType": "Custom"}}}
    assert cos_bucket_read.normalize_certificate(value)["CertType"] == "Custom"


# ---------------------------------------------------------------------------
# a single element comes back as a mapping, not a list
# ---------------------------------------------------------------------------

def test_a_single_domain_rule_is_wrapped_in_a_list():
    """COS returns DomainRule as a mapping when the bucket has one rule."""
    single = {"DomainConfiguration": {"DomainRule": {"Name": "example.com"}}}
    assert cos_bucket_read.normalize_domains(single) == {"DomainRule": [{"Name": "example.com"}]}


def test_domain_rules_are_sorted_by_name():
    value = {"DomainConfiguration": {"DomainRule": [
        {"Name": "b.example.com"}, {"Name": "a.example.com"}]}}
    assert [rule["Name"] for rule in cos_bucket_read.normalize_domains(value)["DomainRule"]] == [
        "a.example.com", "b.example.com"]


def test_a_single_origin_rule_is_wrapped_in_a_list():
    single = {"OriginConfiguration": {"OriginRule": {"RulePriority": 2}}}
    assert cos_bucket_read.normalize_origin(single) == {"OriginRule": [{"RulePriority": 2}]}


def test_origin_rules_are_sorted_by_priority_as_a_number():
    """RulePriority arrives as a string; a lexical sort would put 10 before 2."""
    value = {"OriginConfiguration": {"OriginRule": [
        {"RulePriority": "10"}, {"RulePriority": "2"}]}}
    assert [rule["RulePriority"] for rule in cos_bucket_read.normalize_origin(value)["OriginRule"]] == ["2", "10"]


def test_an_origin_rule_without_a_priority_sorts_first():
    value = {"OriginConfiguration": {"OriginRule": [{"RulePriority": "1"}, {"Host": "x"}]}}
    assert cos_bucket_read.normalize_origin(value)["OriginRule"][0] == {"Host": "x"}


# ---------------------------------------------------------------------------
# a single element comes back as a string, not a list
# ---------------------------------------------------------------------------

def test_a_single_referer_domain_is_wrapped_in_a_list():
    value = {"RefererConfiguration": {"Status": "Enabled", "RefererType": "White-List",
                                      "DomainList": {"Domain": "example.com"}}}
    normalized = cos_bucket_read.normalize_referer(value)
    assert normalized["DomainList"] == {"Domain": ["example.com"]}


def test_a_single_control_param_is_wrapped_in_a_list():
    value = {"ResponseControlConfiguration": {"ControlParamList": {"Param": "maxAge"}}}
    assert cos_bucket_read.normalize_control(value) == {"ControlParamList": {"Param": ["maxAge"]}}


# ---------------------------------------------------------------------------
# a disabled feature reads as absent
# ---------------------------------------------------------------------------

def test_a_disabled_referer_reads_as_absent():
    """A bucket whose referer configuration exists but is disabled has no
    referer policy to compare against."""
    value = {"RefererConfiguration": {"Status": "Disabled", "DomainList": {"Domain": ["a"]}}}
    assert cos_bucket_read.normalize_referer(value) is None


def test_an_enabled_referer_keeps_its_sorting():
    value = {"RefererConfiguration": {"Status": "Enabled", "RefererType": "White-List",
                                      "DomainList": {"Domain": ["b.com", "a.com"]}}}
    assert cos_bucket_read.normalize_referer(value)["DomainList"]["Domain"] == ["a.com", "b.com"]


# ---------------------------------------------------------------------------
# the shapes that carry numbers as strings
# ---------------------------------------------------------------------------

def test_tiering_days_come_back_as_integers():
    value = {"IntelligentTieringConfiguration": {"Id": "tier", "Status": "Enabled",
                                                 "Tiering": {"AccessTier": "ARCHIVE",
                                                             "Days": "30", "RequestFrequent": "1"}}}
    normalized = cos_bucket_read.normalize_tiering(value)
    assert normalized["Tiering"] == {"AccessTier": "ARCHIVE", "Days": 30, "RequestFrequent": 1}


def test_tiering_defaults_its_id():
    value = {"IntelligentTieringConfiguration": {"Tiering": {"Days": "1", "RequestFrequent": "0"}}}
    assert cos_bucket_read.normalize_tiering(value)["Id"] == "default"


def test_object_lock_retention_days_and_years_are_integers():
    value = {"ObjectLockConfiguration": {"ObjectLockEnabled": "Enabled", "Rule": {
        "DefaultRetention": {"Mode": "COMPLIANCE", "Days": "1", "Years": "2"}}}}
    normalized = cos_bucket_read.normalize_object_lock(value)
    assert normalized["Rule"]["DefaultRetention"] == {"Mode": "COMPLIANCE", "Days": 1, "Years": 2}


def test_object_lock_without_a_retention_rule_has_no_rule_key():
    value = {"ObjectLockConfiguration": {"ObjectLockEnabled": "Enabled"}}
    assert cos_bucket_read.normalize_object_lock(value) == {"ObjectLockEnabled": "Enabled"}


# ---------------------------------------------------------------------------
# the two normalizers that take an argument or copy their input
# ---------------------------------------------------------------------------

def test_inventory_takes_its_id_from_the_caller():
    """The read is addressed by Id, and the response does not echo it."""
    value = {"InventoryConfiguration": {"IsEnabled": "true"}}
    assert cos_bucket_read.normalize_inventory(value, "daily")["Id"] == "daily"


def test_inventory_sorts_its_optional_fields():
    value = {"InventoryConfiguration": {"OptionalFields": {"Field": ["Size", "ETag"]}}}
    assert cos_bucket_read.normalize_inventory(value, "daily")["OptionalFields"]["Field"] == ["ETag", "Size"]


def test_inventory_does_not_modify_the_payload_it_was_given():
    value = {"InventoryConfiguration": {"OptionalFields": {"Field": ["Size", "ETag"]}}}
    before = copy.deepcopy(value)
    cos_bucket_read.normalize_inventory(value, "daily")
    assert value == before


def test_replication_rules_are_sorted_by_id_then_prefix():
    value = {"ReplicationConfiguration": {"Role": "role-1", "Rule": [
        {"ID": "b", "Prefix": "a"}, {"ID": "a", "Prefix": "z"}, {"ID": "a", "Prefix": "a"}]}}
    assert [(rule["ID"], rule["Prefix"])
            for rule in cos_bucket_read.normalize_replication(value)["Rule"]] == [
        ("a", "a"), ("a", "z"), ("b", "a")]


# ---------------------------------------------------------------------------
# the getters: not-found is absence, everything else is an error
# ---------------------------------------------------------------------------

class NotFound(Exception):
    """Stands in for an SDK error whose status code is 404."""

    def get_status_code(self):
        return 404


class FakeClient(object):
    """One read method per getter, each returning a canned payload."""

    def __init__(self, payload=None, error=None, domain_headers=None):
        self.payload = payload
        self.error = error
        self.domain_headers = domain_headers or {}
        self.calls = []

    def _read(self, name, **kwargs):
        self.calls.append((name, kwargs))
        if self.error is not None:
            raise self.error
        return self.payload

    def get_bucket_domain_certificate(self, **kwargs):
        return self._read("get_bucket_domain_certificate", **kwargs)

    def get_bucket_domain(self, **kwargs):
        self.calls.append(("get_bucket_domain", kwargs))
        if self.error is not None:
            raise self.error
        response = dict(self.payload or {})
        response.update(self.domain_headers)
        return response

    def get_bucket_intelligenttiering_v2(self, **kwargs):
        return self._read("get_bucket_intelligenttiering_v2", **kwargs)

    def get_bucket_inventory(self, **kwargs):
        return self._read("get_bucket_inventory", **kwargs)

    def get_bucket_object_lock(self, **kwargs):
        return self._read("get_bucket_object_lock", **kwargs)

    def get_bucket_origin(self, **kwargs):
        return self._read("get_bucket_origin", **kwargs)

    def get_bucket_referer(self, **kwargs):
        return self._read("get_bucket_referer", **kwargs)

    def get_bucket_replication(self, **kwargs):
        return self._read("get_bucket_replication", **kwargs)

    def get_bucket_response_control(self, **kwargs):
        return self._read("get_bucket_response_control", **kwargs)


GETTERS = [
    ("get_certificate", ("bucket", "example.com"), "DomainName"),
    ("get_domains", ("bucket",), None),
    ("get_rule", ("bucket",), "Id"),
    ("get_inventory", ("bucket", "daily"), "Id"),
    ("get_object_lock", ("bucket",), None),
    ("get_origin", ("bucket",), None),
    ("get_referer", ("bucket",), None),
    ("get_replication", ("bucket",), None),
    ("get_control", ("bucket",), None),
]


@pytest.mark.parametrize("getter, args, expected_key", GETTERS)
def test_a_missing_configuration_reads_as_absent(getter, args, expected_key):
    client = FakeClient(error=NotFound("NoSuchConfiguration"))
    result = getattr(cos_bucket_read, getter)(client, *args)
    if getter == "get_domains":
        assert result == (None, None)
    else:
        assert result is None


@pytest.mark.parametrize("getter, args, expected_key", GETTERS)
def test_any_other_error_is_raised(getter, args, expected_key):
    client = FakeClient(error=RuntimeError("AccessDenied"))
    with pytest.raises(RuntimeError, match="AccessDenied"):
        getattr(cos_bucket_read, getter)(client, *args)


def test_the_read_is_addressed_by_the_bucket():
    client = FakeClient(payload={"DomainCertificate": {"Status": "Enabled"}})
    cos_bucket_read.get_certificate(client, "my-bucket", "example.com")
    assert client.calls == [("get_bucket_domain_certificate",
                             {"Bucket": "my-bucket", "DomainName": "example.com"})]


def test_the_domains_reader_also_returns_the_verification_token():
    client = FakeClient(payload={"DomainConfiguration": {"DomainRule": []}},
                        domain_headers={"x-cos-domain-txt-verification": "token-1"})
    domains, verification = cos_bucket_read.get_domains(client, "my-bucket")
    assert domains == {"DomainRule": []}
    assert verification == "token-1"


def test_the_domains_verification_token_is_absent_when_the_api_omits_it():
    client = FakeClient(payload={"DomainConfiguration": {"DomainRule": []}})
    assert cos_bucket_read.get_domains(client, "my-bucket")[1] is None
