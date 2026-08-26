"""Unit tests for the key_pair write module helpers."""

from __future__ import absolute_import, division, print_function
__metaclass__ = type
from ansible_collections.tencentcloud.cloud.plugins.modules.key_pair import (
    _create,
    _delete,
    _import,
    build_describe_request,
    find_key_pair,
)


class FakeFilter(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeRequest(object):
    pass


class FakeModels(object):
    Filter = FakeFilter
    DescribeKeyPairsRequest = FakeRequest
    CreateKeyPairRequest = FakeRequest
    ImportKeyPairRequest = FakeRequest
    DeleteKeyPairsRequest = FakeRequest


class FakeKeyPair(object):
    def __init__(self, key_id, name, project_id=0, private_key=None):
        self.KeyId = key_id
        self.KeyName = name
        self.ProjectId = project_id
        self.PrivateKey = private_key

    def _serialize(self, allow_none=True):
        result = {
            "KeyId": self.KeyId,
            "KeyName": self.KeyName,
            "ProjectId": self.ProjectId,
        }
        if self.PrivateKey is not None:
            result["PrivateKey"] = self.PrivateKey
        return result


class FakeDescribeResponse(object):
    def __init__(self, key_pairs):
        self.KeyPairSet = key_pairs


class FakeCreateResponse(object):
    def __init__(self, key_pair):
        self.KeyPair = key_pair


class FakeImportResponse(object):
    def __init__(self, key_id):
        self.KeyId = key_id


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeKeyPairs(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def CreateKeyPair(self, request):
        self.calls.append(request)
        return self.response

    def ImportKeyPair(self, request):
        self.calls.append(request)
        return self.response

    def DeleteKeyPairs(self, request):
        self.calls.append(request)
        return self.response


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2}

    def sdk_call(self, operation, request):
        return operation(request)


def test_build_describe_request_by_id():
    request = build_describe_request(FakeModels, None, "skey-123")
    assert request.KeyIds == ["skey-123"]
    assert request.Limit == 100
    assert not hasattr(request, "Filters") or request.Filters is None


def test_build_describe_request_by_name():
    request = build_describe_request(FakeModels, "deploy-key", None)
    assert request.Filters[0].Name == "key-name"
    assert request.Filters[0].Values == ["deploy-key"]
    assert not hasattr(request, "KeyIds") or request.KeyIds is None


def test_build_describe_request_id_wins_over_name():
    # The API rejects requests that carry both KeyIds and Filters.
    request = build_describe_request(FakeModels, "deploy-key", "skey-123")
    assert request.KeyIds == ["skey-123"]
    assert not hasattr(request, "Filters") or request.Filters is None


def test_find_key_pair_returns_first_match():
    client = FakeClient(FakeDescribeResponse([FakeKeyPair("skey-1", "deploy-key")]))
    module = FakeModule()
    key_pair = find_key_pair(module, client, FakeModels, "deploy-key", None)
    assert key_pair["KeyId"] == "skey-1"
    assert len(client.calls) == 1


def test_find_key_pair_returns_none_when_absent():
    client = FakeClient(FakeDescribeResponse([]))
    module = FakeModule()
    assert find_key_pair(module, client, FakeModels, "deploy-key", None) is None


def test_find_key_pair_handles_none_set():
    client = FakeClient(FakeDescribeResponse(None))
    module = FakeModule()
    assert find_key_pair(module, client, FakeModels, "deploy-key", None) is None


def test_find_key_pair_surfaces_sdk_exceptions():
    class Boom(Exception):
        def get_code(self):
            return "InvalidKeyPairId.NotFound"

    client = FakeClient(exc=Boom("gone"))
    module = FakeModule()
    try:
        find_key_pair(module, client, FakeModels, "deploy-key", None)
        raise AssertionError("expected exception")
    except Boom:
        pass


def test_create_returns_key_pair_and_private_key_separately():
    key_pair = FakeKeyPair("skey-9", "deploy-key", private_key="PEM-DATA")
    client = FakeClient(FakeCreateResponse(key_pair))
    module = FakeModule()
    created, private_key = _create(module, client, FakeModels, "deploy-key", 0)
    request = client.calls[0]
    assert request.KeyName == "deploy-key"
    assert request.ProjectId == 0
    assert private_key == "PEM-DATA"
    assert created["KeyId"] == "skey-9"
    assert "PrivateKey" not in created


def test_import_returns_key_id():
    client = FakeClient(FakeImportResponse("skey-7"))
    module = FakeModule()
    key_id = _import(module, client, FakeModels, "deploy-key", 0, "ssh-rsa AAAA")
    request = client.calls[0]
    assert request.KeyName == "deploy-key"
    assert request.ProjectId == 0
    assert request.PublicKey == "ssh-rsa AAAA"
    assert key_id == "skey-7"


def test_delete_uses_key_ids_list():
    client = FakeClient()
    module = FakeModule()
    _delete(module, client, FakeModels, "skey-123")
    assert client.calls[0].KeyIds == ["skey-123"]
