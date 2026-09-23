"""Unit tests for the cam_saml_provider write module (run_module flows).

Drives ``run_module()`` against an in-memory fake CAM SAML client whose
create / update / delete operations mutate a SAML-provider store so
post-write describes converge immediately.

Scenario matrix:

* absent on a missing provider (idempotent no-op)
* absent with a matching provider (check-mode dry run, real delete)
* creation when missing (happy path, check mode)
* no-op when the provider already matches (canonical metadata compares equal)
* description/metadata drift updates and rename-by-name-alone creation
* the non-base64 metadata fallback path and the blanket SDK failure paths
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import base64
import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cam_saml_provider as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

METADATA_XML = (
    "<EntityDescriptor xmlns=\"urn:oasis:names:tc:SAML:2.0:metadata\">"
    "<SPSSODescriptor protocolSupportEnumeration=\"urn:oasis:names:tc:SAML:2.0:protocol\"/>"
    "</EntityDescriptor>"
)
METADATA_B64 = base64.b64encode(METADATA_XML.encode("utf-8")).decode("ascii")

PROVIDER = {
    "Name": "corporate-idp",
    "Description": "Corporate identity provider",
    "SAMLMetadata": METADATA_B64,
}


def _provider(**overrides):
    item = copy.deepcopy(PROVIDER)
    item.update(overrides)
    return item


def _present_args(**overrides):
    params = {
        "state": "present",
        "name": "corporate-idp",
        "description": "Corporate identity provider",
        "metadata_document": METADATA_B64,
    }
    params.update(overrides)
    return module_args(**params)


def _not_found():
    class NotFound(Exception):
        def get_code(self):
            return "ResourceNotFound.CamSamlProvider"

        def get_request_id(self):
            return "req-1"

    return NotFound("saml provider not found")


class FakeCamClient(object):
    """In-memory CAM SAML client mutating a small provider store."""

    def __init__(self, providers=None):
        self.providers = [copy.deepcopy(t) for t in (providers or [])]
        self.calls = []

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _by_name(self, name):
        for item in self.providers:
            if item.get("Name") == name:
                return item
        return None

    def GetSAMLProvider(self, request):
        self._record("GetSAMLProvider", request)
        item = self._by_name(getattr(request, "Name", None))
        if item is None:
            raise _not_found()
        return FakeResource(copy.deepcopy(item))

    def CreateSAMLProvider(self, request):
        self._record("CreateSAMLProvider", request)
        item = {
            "Name": getattr(request, "Name", None),
            "Description": getattr(request, "Description", None) or "",
            "SAMLMetadata": getattr(request, "SAMLMetadataDocument", None),
        }
        self.providers.append(item)
        return SimpleNamespace(RequestId="req-fake")

    def UpdateSAMLProvider(self, request):
        self._record("UpdateSAMLProvider", request)
        item = self._by_name(getattr(request, "Name", None))
        if item is not None:
            item["Description"] = getattr(request, "Description", item.get("Description"))
            item["SAMLMetadata"] = getattr(request, "SAMLMetadataDocument", item.get("SAMLMetadata"))
        return SimpleNamespace(RequestId="req-fake")

    def DeleteSAMLProvider(self, request):
        self._record("DeleteSAMLProvider", request)
        name = getattr(request, "Name", None)
        self.providers = [t for t in self.providers if t.get("Name") != name]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load", lambda: (models or FakeModels(), SimpleNamespace(CamClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_missing_provider_is_idempotent(monkeypatch):
    fake = FakeCamClient(providers=[])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="ghost-provider")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["saml_provider"] is None
    assert [c for c, unused in fake.calls] == ["GetSAMLProvider"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCamClient(providers=[_provider()])
    _make_module(monkeypatch, fake)
    module_args(_ansible_check_mode=True, state="absent", name="corporate-idp")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["saml_provider"]["Name"] == "corporate-idp"
    assert len(fake.providers) == 1
    assert "DeleteSAMLProvider" not in [c for c, unused in fake.calls]


def test_absent_deletes_provider(monkeypatch):
    fake = FakeCamClient(providers=[_provider()])
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="corporate-idp")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["saml_provider"] is None
    assert fake.providers == []
    assert "DeleteSAMLProvider" in [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_provider(monkeypatch):
    fake = FakeCamClient(providers=[])
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["saml_provider"]["Name"] == "corporate-idp"
    assert result["saml_provider"]["SAMLMetadata"] == METADATA_B64
    assert len(fake.providers) == 1
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "GetSAMLProvider"
    assert "CreateSAMLProvider" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCamClient(providers=[])
    _make_module(monkeypatch, fake)
    _present_args(_ansible_check_mode=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["saml_provider"] is None
    assert "diff" in result
    assert fake.providers == []
    assert "CreateSAMLProvider" not in [c for c, unused in fake.calls]


def test_create_with_plain_text_metadata_falls_back_to_strip(monkeypatch):
    # A metadata document that is not valid base64 exercises the
    # canonical_metadata fallback (compare on the stripped raw string).
    fake = FakeCamClient(providers=[])
    _make_module(monkeypatch, fake)
    _present_args(metadata_document="  <raw>not-base64</raw>  ")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["saml_provider"]["SAMLMetadata"] == "  <raw>not-base64</raw>  "
    assert fake.providers[0]["SAMLMetadata"] == "  <raw>not-base64</raw>  "


def test_rename_by_name_alone_creates_new_provider(monkeypatch):
    fake = FakeCamClient(providers=[_provider()])
    _make_module(monkeypatch, fake)
    _present_args(name="renamed-idp")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["saml_provider"]["Name"] == "renamed-idp"
    assert [p["Name"] for p in fake.providers] == ["corporate-idp", "renamed-idp"]


# ---------------------------------------------------------------------------
# existing-provider flows
# ---------------------------------------------------------------------------


def test_existing_provider_no_drift_is_idempotent(monkeypatch):
    fake = FakeCamClient(providers=[_provider()])
    _make_module(monkeypatch, fake)
    _present_args()
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["saml_provider"]["Name"] == "corporate-idp"
    assert "UpdateSAMLProvider" not in [c for c, unused in fake.calls]


def test_metadata_whitespace_drift_is_idempotent(monkeypatch):
    # Desired metadata is base64 with the XML padded by whitespace; the
    # canonical decode strips it, so the run stays unchanged.
    padded = base64.b64encode((" \n " + METADATA_XML + "\n ").encode("utf-8")).decode("ascii")
    fake = FakeCamClient(providers=[_provider()])
    _make_module(monkeypatch, fake)
    _present_args(metadata_document=padded)
    result = run(mod.run_module)
    assert result["changed"] is False
    assert "UpdateSAMLProvider" not in [c for c, unused in fake.calls]


def test_description_drift_updates(monkeypatch):
    fake = FakeCamClient(providers=[_provider()])
    _make_module(monkeypatch, fake)
    _present_args(description="Updated identity provider")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["saml_provider"]["Description"] == "Updated identity provider"
    assert "UpdateSAMLProvider" in [c for c, unused in fake.calls]


def test_metadata_drift_updates(monkeypatch):
    new_meta = base64.b64encode((METADATA_XML + "<New/>").encode("utf-8")).decode("ascii")
    fake = FakeCamClient(providers=[_provider()])
    _make_module(monkeypatch, fake)
    _present_args(metadata_document=new_meta)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["saml_provider"]["SAMLMetadata"] == new_meta
    ops = [c for c, unused in fake.calls]
    assert "UpdateSAMLProvider" in ops
    assert ops[-1] == "GetSAMLProvider"


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def GetSAMLProvider(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _present_args()
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]


def test_delete_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def GetSAMLProvider(self, request):
            return FakeResource(copy.deepcopy(_provider()))

        def DeleteSAMLProvider(self, request):
            raise Boom("delete refused")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    module_args(state="absent", name="corporate-idp")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "delete refused" in payload["error"]
