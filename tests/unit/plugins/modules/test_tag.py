"""Unit tests for the tag write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.tag import (
    build_describe_request,
    find_resources,
    _attach,
    _update_value,
    _detach,
)


class FakeRequest(object):
    pass


class FakeTagFilter(object):
    def __init__(self):
        self.TagKey = None
        self.TagValue = None


class FakeTag(object):
    def __init__(self, key, value):
        self.Key = key
        self.Value = value


class FakeModels(object):
    DescribeResourcesByTagsRequest = FakeRequest
    AttachResourcesTagRequest = FakeRequest
    ModifyResourcesTagValueRequest = FakeRequest
    DetachResourcesTagRequest = FakeRequest
    TagFilter = FakeTagFilter


class FakeResourceTag(object):
    def __init__(self, resource_id, tags):
        self.ResourceId = resource_id
        self.Tags = tags


class FakeDescribeResponse(object):
    def __init__(self, resource_tags):
        self.ResourceTags = resource_tags


class FakeClient(object):
    def __init__(self, describe_response=None, exc=None):
        self.describe_response = describe_response
        self.exc = exc
        self.calls = []

    def DescribeResourcesByTags(self, request):
        self.calls.append(("DescribeResourcesByTags", request))
        if self.exc:
            raise self.exc
        return self.describe_response

    def AttachResourcesTag(self, request):
        self.calls.append(("AttachResourcesTag", request))

    def ModifyResourcesTagValue(self, request):
        self.calls.append(("ModifyResourcesTagValue", request))

    def DetachResourcesTag(self, request):
        self.calls.append(("DetachResourcesTag", request))


class FakeModule(object):
    def __init__(self):
        self.params = {"retries": 2, "region": "ap-guangzhou"}

    def sdk_call(self, operation, request):
        return operation(request)


BASE = {
    "tag_key": "env",
    "tag_value": "prod",
    "service_type": "cvm",
    "resource_prefix": "instance",
    "resource_region": "ap-guangzhou",
}


def test_build_describe_request_with_exact_value():
    request = build_describe_request(FakeModels, "env", "prod", "cvm", "instance", "ap-guangzhou")
    assert request.TagFilters[0].TagKey == "env"
    assert request.TagFilters[0].TagValue == ["prod"]
    assert request.ServiceType == "cvm"
    assert request.ResourcePrefix == "instance"
    assert request.ResourceRegion == "ap-guangzhou"


def test_build_describe_request_key_only():
    request = build_describe_request(FakeModels, "env", None, "cvm", "instance", None)
    assert request.TagFilters[0].TagKey == "env"
    assert request.TagFilters[0].TagValue is None
    assert not hasattr(request, "ResourceRegion") or request.ResourceRegion is None


def test_find_resources_returns_matching_values():
    client = FakeClient(FakeDescribeResponse([
        FakeResourceTag("ins-1", [FakeTag("env", "prod"), FakeTag("team", "core")]),
        FakeResourceTag("ins-2", [FakeTag("env", "staging")]),
    ]))
    module = FakeModule()
    result = find_resources(module, client, FakeModels, "env", None, "cvm", "instance", "ap-guangzhou")
    assert result == {"ins-1": "prod", "ins-2": "staging"}
    assert len(client.calls) == 1


def test_find_resources_returns_empty_when_none():
    client = FakeClient(FakeDescribeResponse([]))
    module = FakeModule()
    assert find_resources(module, client, FakeModels, "env", None, "cvm", "instance", "ap-guangzhou") == {}


def test_find_resources_degrades_to_empty_on_exception():
    class Boom(Exception):
        pass

    client = FakeClient(exc=Boom("api error"))
    module = FakeModule()
    assert find_resources(module, client, FakeModels, "env", None, "cvm", "instance", "ap-guangzhou") == {}


def test_attach_sends_all_fields():
    client = FakeClient()
    module = FakeModule()
    _attach(module, client, FakeModels, "env", "prod", "cvm", "instance", "ap-guangzhou", ["ins-1", "ins-2"])
    request = client.calls[-1][1]
    assert request.ServiceType == "cvm"
    assert request.ResourcePrefix == "instance"
    assert request.ResourceIds == ["ins-1", "ins-2"]
    assert request.TagKey == "env"
    assert request.TagValue == "prod"
    assert request.ResourceRegion == "ap-guangzhou"


def test_update_value_sends_tag_value():
    client = FakeClient()
    module = FakeModule()
    _update_value(module, client, FakeModels, "env", "staging", "cvm", "instance", "ap-guangzhou", ["ins-1"])
    request = client.calls[-1][1]
    assert request.TagKey == "env"
    assert request.TagValue == "staging"
    assert request.ResourceIds == ["ins-1"]


def test_detach_omits_value():
    client = FakeClient()
    module = FakeModule()
    _detach(module, client, FakeModels, "env", "cvm", "instance", None, ["ins-1"])
    request = client.calls[-1][1]
    assert request.TagKey == "env"
    assert request.ResourceIds == ["ins-1"]
    assert not hasattr(request, "TagValue")
    assert not hasattr(request, "ResourceRegion")
