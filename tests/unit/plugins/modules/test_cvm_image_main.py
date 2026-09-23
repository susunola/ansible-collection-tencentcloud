"""Unit tests for the cvm_image write module (run_module flows).

Drives ``run_module()`` end to end against an in-memory fake CVM client
whose write operations mutate the image store, so the module's post-write
``find_image`` refetch converges immediately.

Scenario matrix:

* absent on a missing image (idempotent no-op) and the identity guard
* absent with a matching image (check-mode dry run and the real delete)
* creation when missing (instance_id/image_name guards, check mode,
  happy path)
* no-op when nothing drifts
* name/description drift updates (check mode and real update)
* the blanket ``Tencent Cloud API request failed`` failure path
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
from types import SimpleNamespace

import pytest

from ansible_collections.susunola.tencentcloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.susunola.tencentcloud.plugins.modules import cvm_image as mod
from ansible_collections.susunola.tencentcloud.tests.unit.plugins.modules.harness import (
    AnsibleFailJson,
    FakeModels,
    FakeResource,
    module_args,
    run,
)

IMAGE = {
    "ImageId": "img-abcdef01",
    "ImageName": "web-prod-20260827",
    "ImageState": "NORMAL",
    "ImageType": "PRIVATE_IMAGE",
    "ImageDescription": "golden web image",
    "ImageSize": 50,
}


def _image(**overrides):
    item = copy.deepcopy(IMAGE)
    item.update(overrides)
    return item


def _base(**overrides):
    params = {}
    params.update(overrides)
    return module_args(**params)


class FakeCvmClient(object):
    """In-memory CVM image client mutating a small image store."""

    def __init__(self, images=None):
        self.images = [copy.deepcopy(t) for t in (images or [])]
        self.calls = []
        self._next = 0

    def _record(self, name, request=None):
        self.calls.append((name, request))

    def _find_by_name(self, name):
        for item in self.images:
            if item.get("ImageName") == name:
                return item
        return None

    def DescribeImages(self, request):
        self._record("DescribeImages", request)
        matches = []
        image_ids = getattr(request, "ImageIds", None) or []
        if image_ids:
            matches = [dict(t) for t in self.images if t.get("ImageId") in image_ids]
        else:
            filters = getattr(request, "Filters", None) or []
            name = None
            for item in filters:
                if item.Name == "image-name":
                    name = item.Values[0]
            matches = [dict(t) for t in self.images if t.get("ImageName") == name]
        return SimpleNamespace(ImageSet=[FakeResource(t) for t in matches])

    def CreateImage(self, request):
        self._record("CreateImage", request)
        self._next += 1
        item = {
            "ImageId": "img-new-%03d" % self._next,
            "ImageName": getattr(request, "ImageName", None),
            "ImageDescription": getattr(request, "ImageDescription", None),
            "ImageState": "NORMAL",
            "ImageType": "PRIVATE_IMAGE",
            "ImageSize": 50,
        }
        self.images.append(item)
        return SimpleNamespace(RequestId="req-fake")

    def ModifyImageAttribute(self, request):
        self._record("ModifyImageAttribute", request)
        for item in self.images:
            if item.get("ImageId") == getattr(request, "ImageId", None):
                if getattr(request, "ImageName", None) is not None:
                    item["ImageName"] = request.ImageName
                if getattr(request, "ImageDescription", None) is not None:
                    item["ImageDescription"] = request.ImageDescription
        return SimpleNamespace(RequestId="req-fake")

    def DeleteImages(self, request):
        self._record("DeleteImages", request)
        ids = list(getattr(request, "ImageIds", None) or [])
        self.images = [t for t in self.images if t.get("ImageId") not in ids]
        return SimpleNamespace(RequestId="req-fake")


def _make_module(monkeypatch, fake, models=None):
    """Wire the shared monkeypatches; returns the fake client."""
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(mod, "_load_cvm", lambda: (models or FakeModels(), SimpleNamespace(CvmClient=object)))
    monkeypatch.setattr(TencentCloudModule, "create_client", lambda self, client_class, endpoint: fake)
    return fake


def _ops(fake):
    return [c for c, unused in fake.calls]


# ---------------------------------------------------------------------------
# absent flows
# ---------------------------------------------------------------------------


def test_absent_requires_an_identity(monkeypatch):
    fake = FakeCvmClient(images=[])
    _make_module(monkeypatch, fake)
    _base(state="absent")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "image_id or image_name is required when state=absent" in exc.value.args[0]["msg"]


def test_absent_missing_image_is_idempotent(monkeypatch):
    fake = FakeCvmClient(images=[])
    _make_module(monkeypatch, fake)
    _base(state="absent", image_name="ghost-image")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert _ops(fake) == ["DescribeImages"]


def test_absent_check_mode_is_dry_run(monkeypatch):
    fake = FakeCvmClient(images=[_image()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="absent", image_id="img-abcdef01")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert len(fake.images) == 1
    assert "DeleteImages" not in _ops(fake)


def test_absent_deletes_image(monkeypatch):
    fake = FakeCvmClient(images=[_image()])
    _make_module(monkeypatch, fake)
    _base(state="absent", image_id="img-abcdef01", delete_binded_snap=True)
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["image"] is None
    assert fake.images == []
    ops = [c for c, unused in fake.calls]
    assert ops[0] == "DescribeImages"
    assert "DeleteImages" in ops
    delete_request = [r for c, r in fake.calls if c == "DeleteImages"][0]
    assert delete_request.ImageIds == ["img-abcdef01"]


# ---------------------------------------------------------------------------
# creation flows
# ---------------------------------------------------------------------------


def test_create_requires_instance_id(monkeypatch):
    fake = FakeCvmClient(images=[])
    _make_module(monkeypatch, fake)
    _base(state="present", image_name="web-prod")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "instance_id is required when creating an image" in exc.value.args[0]["msg"]


def test_create_requires_image_name(monkeypatch):
    fake = FakeCvmClient(images=[])
    _make_module(monkeypatch, fake)
    _base(state="present", instance_id="ins-1234")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    assert "image_name is required when creating an image" in exc.value.args[0]["msg"]


def test_create_image(monkeypatch):
    fake = FakeCvmClient(images=[])
    _make_module(monkeypatch, fake)
    _base(state="present", image_name="web-prod-20260827", instance_id="ins-1234", image_description="golden web image")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["image"]["ImageName"] == "web-prod-20260827"
    assert result["image"]["ImageId"].startswith("img-")
    assert len(fake.images) == 1
    ops = _ops(fake)
    assert ops[0] == "DescribeImages"
    assert "CreateImage" in ops


def test_create_check_mode_is_dry_run(monkeypatch):
    fake = FakeCvmClient(images=[])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", image_name="web-prod", instance_id="ins-1234")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.images == []
    assert "CreateImage" not in _ops(fake)


# ---------------------------------------------------------------------------
# existing-image flows
# ---------------------------------------------------------------------------


def test_existing_image_no_drift_is_idempotent(monkeypatch):
    fake = FakeCvmClient(images=[_image()])
    _make_module(monkeypatch, fake)
    _base(state="present", image_name="web-prod-20260827", image_description="golden web image")
    result = run(mod.run_module)
    assert result["changed"] is False
    assert result["image"]["ImageId"] == "img-abcdef01"
    assert "ModifyImageAttribute" not in _ops(fake)


def test_existing_image_rename_updates(monkeypatch):
    fake = FakeCvmClient(images=[_image()])
    _make_module(monkeypatch, fake)
    _base(state="present", image_id="img-abcdef01", image_name="web-prod-latest", image_description="golden web image")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["image"]["ImageName"] == "web-prod-latest"
    assert fake.images[0]["ImageName"] == "web-prod-latest"
    assert "ModifyImageAttribute" in _ops(fake)


def test_existing_image_description_only_update(monkeypatch):
    fake = FakeCvmClient(images=[_image()])
    _make_module(monkeypatch, fake)
    _base(state="present", image_name="web-prod-20260827", image_description="renamed description")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert result["image"]["ImageDescription"] == "renamed description"
    assert fake.images[0]["ImageDescription"] == "renamed description"
    assert "ModifyImageAttribute" in _ops(fake)


def test_existing_image_check_mode_dry_run(monkeypatch):
    fake = FakeCvmClient(images=[_image()])
    _make_module(monkeypatch, fake)
    _base(_ansible_check_mode=True, state="present", image_id="img-abcdef01", image_name="web-prod-latest")
    result = run(mod.run_module)
    assert result["changed"] is True
    assert fake.images[0]["ImageName"] == "web-prod-20260827"
    assert "ModifyImageAttribute" not in _ops(fake)


# ---------------------------------------------------------------------------
# failure path
# ---------------------------------------------------------------------------


def test_sdk_failure_maps_to_error_payload(monkeypatch):
    class Boom(Exception):
        pass

    class ExplodingClient(object):
        def DescribeImages(self, request):
            raise Boom("connection dropped")

    fake = ExplodingClient()
    _make_module(monkeypatch, fake)
    _base(state="present", image_name="web-prod", instance_id="ins-1234")
    with pytest.raises(AnsibleFailJson) as exc:
        run(mod.run_module)
    payload = exc.value.args[0]
    assert payload["msg"] == "Tencent Cloud API request failed"
    assert "connection dropped" in payload["error"]
