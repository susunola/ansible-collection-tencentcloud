"""Unit tests for the cvm_image write module helpers."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.susunola.tencentcloud.plugins.modules.cvm_image import (
    _create,
    _delete,
    _update,
    build_describe_request,
    find_image,
)


class FakeFilter(object):
    """Mimics the Tencent SDK Filter model: zero-arg constructor."""

    def __init__(self):
        pass


class FakeRequest(object):
    pass


class FakeModels(object):
    Filter = FakeFilter
    DescribeImagesRequest = FakeRequest
    CreateImageRequest = FakeRequest
    ModifyImageAttributeRequest = FakeRequest
    DeleteImagesRequest = FakeRequest


class FakeImage(object):
    def __init__(self, image_id, name, description=None):
        self.ImageId = image_id
        self.ImageName = name
        self.ImageDescription = description

    def _serialize(self, allow_none=True):
        return {
            "ImageId": self.ImageId,
            "ImageName": self.ImageName,
            "ImageDescription": self.ImageDescription,
        }


class FakeResponse(object):
    def __init__(self, images):
        self.ImageSet = images


class FakeClient(object):
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def DescribeImages(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def CreateImage(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def ModifyImageAttribute(self, request):
        self.calls.append(request)
        if self.exc:
            raise self.exc
        return self.response

    def DeleteImages(self, request):
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
    request = build_describe_request(FakeModels, "img-123", None)
    assert request.ImageIds == ["img-123"]
    assert request.Offset == 0
    assert request.Limit == 100
    assert not hasattr(request, "Filters") or request.Filters is None


def test_build_describe_request_by_name():
    request = build_describe_request(FakeModels, None, "web-prod")
    assert request.Filters[0].Name == "image-name"
    assert request.Filters[0].Values == ["web-prod"]
    assert not hasattr(request, "ImageIds") or request.ImageIds is None


def test_find_image_returns_first_match():
    client = FakeClient(FakeResponse([FakeImage("img-1", "web-prod")]))
    module = FakeModule()
    image = find_image(module, client, FakeModels, None, "web-prod")
    assert image["ImageId"] == "img-1"
    assert len(client.calls) == 1


def test_find_image_returns_none_when_absent():
    client = FakeClient(FakeResponse([]))
    module = FakeModule()
    assert find_image(module, client, FakeModels, "img-9", None) is None


def test_find_image_handles_none_set():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    assert find_image(module, client, FakeModels, "img-9", None) is None


def test_create_sends_all_provided_fields():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _create(module, client, FakeModels, {
        "instance_id": "ins-1",
        "image_name": "web-prod",
        "image_description": "golden",
        "force_poweroff": True,
        "sysprep": False,
    })
    request = client.calls[-1]
    assert request.InstanceId == "ins-1"
    assert request.ImageName == "web-prod"
    assert request.ImageDescription == "golden"
    assert request.ForcePoweroff == "true"
    assert not hasattr(request, "Sysprep")


def test_create_omits_optional_fields():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _create(module, client, FakeModels, {
        "instance_id": "ins-1",
        "image_name": None,
        "image_description": None,
        "force_poweroff": False,
        "sysprep": False,
    })
    request = client.calls[-1]
    assert request.InstanceId == "ins-1"
    assert not hasattr(request, "ImageName")
    assert not hasattr(request, "ImageDescription")
    assert not hasattr(request, "ForcePoweroff")


def test_update_sets_name_and_description():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _update(module, client, FakeModels, "img-1", "web-prod-v2", "renamed")
    request = client.calls[-1]
    assert request.ImageId == "img-1"
    assert request.ImageName == "web-prod-v2"
    assert request.ImageDescription == "renamed"


def test_update_skips_none_fields():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _update(module, client, FakeModels, "img-1", None, None)
    request = client.calls[-1]
    assert request.ImageId == "img-1"
    assert not hasattr(request, "ImageName")
    assert not hasattr(request, "ImageDescription")


def test_delete_sends_image_ids():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _delete(module, client, FakeModels, "img-1", False)
    request = client.calls[-1]
    assert request.ImageIds == ["img-1"]
    assert not hasattr(request, "DeleteBindedSnap")


def test_delete_with_bind_snap():
    client = FakeClient(FakeResponse(None))
    module = FakeModule()
    _delete(module, client, FakeModels, "img-1", True)
    assert client.calls[-1].DeleteBindedSnap is True
