"""Unit tests for the cos_bucket_domain_certificate_info module.

The module was referenced by no test file at all -- a reader of the tree could
not tell whether it worked. It is thin on purpose: resolve the bucket name,
read the domain certificate through ``module_utils/cos_bucket_read`` and
return it as both a list and a single value. These tests drive ``run_module``
end to end with the reader monkeypatched, so what is pinned is the wiring the
module owns: the bucket it addresses, the domain it asks for, the two return
keys, and the error path.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils import cos
from ansible_collections.susunola.tencentcloud.plugins.modules import (
    cos_bucket_domain_certificate_info as mod,
)
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    module_args,
    run,
)

DOMAIN = "static.example.com"
APPID = "1300000000"
CERTIFICATE = {
    "Status": "Enabled",
    "CertType": "CustomCert",
    "CertificateInfo": {"CertID": "8u9example"},
}


class FakeCosError(Exception):
    """Stand-in for a ``qcloud_cos`` service error."""


@pytest.fixture
def cos_client(monkeypatch):
    """Patch the COS entry points the module reaches through ``cos``."""
    monkeypatch.setattr(cos, "require_cos_sdk", lambda module: None)
    monkeypatch.setattr(cos, "create_cos_client", lambda module: "client")


def _read(monkeypatch, value):
    """Record the arguments the module passes to the reader."""
    calls = []

    def fake(client, bucket, domain_name):
        calls.append((client, bucket, domain_name))
        return value

    monkeypatch.setattr(mod, "get_certificate", fake)
    return calls


def test_run_module_returns_the_certificate_twice(cos_client, monkeypatch):
    calls = _read(monkeypatch, CERTIFICATE)
    module_args(name="public-site", appid=APPID, domain_name=DOMAIN)

    result = run(mod.run_module)

    assert result["changed"] is False
    assert result["domain_certificates"] == [CERTIFICATE]
    assert result["domain_certificate"] == CERTIFICATE
    assert calls == [("client", "public-site-%s" % APPID, DOMAIN)]


def test_run_module_returns_empty_keys_without_a_certificate(cos_client,
                                                             monkeypatch):
    _read(monkeypatch, None)
    module_args(name="public-site", appid=APPID, domain_name=DOMAIN)

    result = run(mod.run_module)

    assert result["changed"] is False
    assert result["domain_certificates"] == []
    assert result["domain_certificate"] is None


def test_run_module_accepts_an_already_suffixed_bucket(cos_client, monkeypatch):
    calls = _read(monkeypatch, CERTIFICATE)
    module_args(name="public-site-%s" % APPID, appid=APPID, domain_name=DOMAIN)

    run(mod.run_module)

    assert calls[0][1] == "public-site-%s" % APPID


def test_run_module_maps_a_cos_error_to_fail_json(cos_client, monkeypatch):
    def boom(client, bucket, domain_name):
        raise FakeCosError("no such domain")

    monkeypatch.setattr(mod, "get_certificate", boom)
    module_args(name="public-site", appid=APPID, domain_name=DOMAIN)

    with pytest.raises(AnsibleFailJson) as failure:
        run(mod.run_module)

    assert "Tencent Cloud COS request failed" in failure.value.args[0]["msg"]
    assert "no such domain" in failure.value.args[0]["error"]
