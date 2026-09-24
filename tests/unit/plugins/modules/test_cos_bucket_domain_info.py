from __future__ import absolute_import, division, print_function
import sys
import types
basic = types.ModuleType("ansible.module_utils.basic")
basic.AnsibleModule = object
basic.env_fallback = lambda names, default=None: default
sys.modules.setdefault("ansible", types.ModuleType("ansible"))
sys.modules.setdefault("ansible.module_utils", types.ModuleType("ansible.module_utils"))
sys.modules.setdefault("ansible.module_utils.basic", basic)
from ansible_collections.susunola.tencentcloud.plugins.modules.cos_bucket_domain import normalize as normalize_domains
from ansible_collections.susunola.tencentcloud.plugins.module_utils.cos_bucket_read import normalize_certificate


def test_domain_normalize_sorts_rules():
    value = {"DomainRule": [{"Name": "z.example"}, {"Name": "a.example"}]}
    assert [x["Name"] for x in normalize_domains(value)["DomainRule"]] == ["a.example", "z.example"]


def test_certificate_normalize_projects_managed_identity():
    value = {"Status": "Enabled", "CertificateInfo": {"CertType": "CustomCert", "CertID": "cert-1"}}
    assert normalize_certificate(value) == {"Status": "Enabled", "CertType": "CustomCert", "CertificateInfo": {"CertID": "cert-1"}}
