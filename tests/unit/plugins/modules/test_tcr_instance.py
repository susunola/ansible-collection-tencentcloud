"""Unit tests for the tcr_instance write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.tcr_instance import (
    _create,
    _delete,
    _update,
    build_create_request,
    build_describe_request,
    find_instance,
)


class FakeRequest(object):
    pass


class FakePrepaid(object):
    def __init__(self):
        self.Period = None
        self.RenewFlag = None


class FakeTag(object):
    def __init__(self):
        self.Key = None
        self.Value = None


class FakeTagSpecification(object):
    def __init__(self):
        self.ResourceType = None
        self.Tags = None


class FakeModels(object):
    DescribeInstancesRequest = FakeRequest
    CreateInstanceRequest = FakeRequest
    ModifyInstanceRequest = FakeRequest
    DeleteInstanceRequest = FakeRequest
    RegistryChargePrepaid = FakePrepaid
    TagSpecification = FakeTagSpecification
    Tag = FakeTag


class FakeInstance(object):
    def __init__(self, registry_id, name, protection=False):
        self.RegistryId = registry_id
        self.RegistryName = name
        self.DeletionProtection = protection

    def _serialize(self, allow_none=True):
        return {
            "RegistryId": self.RegistryId,
            "RegistryName": self.RegistryName,
            "DeletionProtection": self.DeletionProtection,
        }


class FakeResponse(object):
    def __init__(self, registries):
        self.Registries = registries


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeInstances(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def CreateInstance(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def ModifyInstance(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def DeleteInstance(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, "tcr-123", None)
    assert request.Registryids == ["tcr-123"]
    assert request.Limit == 100


def test_build_describe_request_by_name_has_no_filter():
    request = build_describe_request(FakeModels, None, "prod-registry")
    assert not hasattr(request, "Registryids") or request.Registryids is None


def test_find_instance_by_id_returns_first():
    client = FakeClient(FakeResponse([FakeInstance("tcr-1", "prod-registry")]))
    module = FakeModule()
    instance = find_instance(module, client, FakeModels, "tcr-1", None)
    assert instance["RegistryId"] == "tcr-1"
    assert len(client.calls) == 1


def test_find_instance_by_name_matches_name():
    client = FakeClient(FakeResponse([
        FakeInstance("tcr-1", "other"),
        FakeInstance("tcr-2", "prod-registry"),
    ]))
    module = FakeModule()
    instance = find_instance(module, client, FakeModels, None, "prod-registry")
    assert instance["RegistryId"] == "tcr-2"


def test_find_instance_returns_none_when_absent():
    client = FakeClient(FakeResponse([]))
    module = FakeModule()
    assert find_instance(module, client, FakeModels, "tcr-9", None) is None


def test_build_create_request_sends_core_fields():
    request = build_create_request(FakeModels, {
        "name": "prod-registry",
        "registry_type": "basic",
        "deletion_protection": True,
        "period_months": None,
        "auto_renew": None,
        "sync_tag": None,
        "enable_cos_maz": None,
        "tags": {},
    })
    assert request.RegistryName == "prod-registry"
    assert request.RegistryType == "basic"
    assert request.DeletionProtection is True


def test_build_create_request_sends_prepaid():
    request = build_create_request(FakeModels, {
        "name": "prod-registry",
        "registry_type": "premium",
        "deletion_protection": False,
        "period_months": 12,
        "auto_renew": 1,
        "sync_tag": None,
        "enable_cos_maz": None,
        "tags": {},
    })
    assert request.RegistryChargePrepaid.Period == 12
    assert request.RegistryChargePrepaid.RenewFlag == 1


def test_build_create_request_sends_tags():
    request = build_create_request(FakeModels, {
        "name": "prod-registry",
        "registry_type": "basic",
        "deletion_protection": False,
        "period_months": None,
        "auto_renew": None,
        "sync_tag": True,
        "enable_cos_maz": True,
        "tags": {"env": "prod", "team": "ops"},
    })
    assert request.SyncTag is True
    assert request.EnableCosMAZ is True
    assert request.TagSpecification.ResourceType == "instance"
    assert [(t.Key, t.Value) for t in request.TagSpecification.Tags] == [("env", "prod"), ("team", "ops")]


def test_create_sends_request():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _create(module, client, FakeModels, {
        "name": "prod-registry",
        "registry_type": "basic",
        "deletion_protection": False,
        "period_months": None,
        "auto_renew": None,
        "sync_tag": None,
        "enable_cos_maz": None,
        "tags": {},
    })
    assert len(client.calls) == 1
    assert client.calls[0].RegistryName == "prod-registry"


def test_update_sends_protection():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _update(module, client, FakeModels, "tcr-1", True)
    request = client.calls[-1]
    assert request.RegistryId == "tcr-1"
    assert request.DeletionProtection is True


def test_delete_sends_registry_id_and_bucket():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _delete(module, client, FakeModels, "tcr-1", True)
    request = client.calls[-1]
    assert request.RegistryId == "tcr-1"
    assert request.DeleteBucket is True
