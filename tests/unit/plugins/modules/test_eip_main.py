"""Main-path unit tests for the eip module (run_module level)."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ansible_collections.tencentcloud.cloud.plugins.module_utils.base import TencentCloudModule
from ansible_collections.tencentcloud.cloud.plugins.modules import eip
from ansible_collections.tencentcloud.cloud.tests.unit.plugins.modules.harness import (
    FakeModels,
    FakeResource,
    module_args,
    run,
)

ADDRESS = {
    "AddressId": "eip-existing1",
    "AddressName": "web-eip",
    "AddressIp": "1.2.3.4",
    "InstanceId": "",
    "TagSet": [],
}


class FakeVpcClient(object):
    def __init__(self, addresses=None):
        self.addresses = list(addresses or [])
        self.AllocateAddresses = MagicMock(side_effect=self._allocate)
        self.ReleaseAddresses = MagicMock(side_effect=self._release)
        self.ModifyAddressAttribute = MagicMock()
        self.AssociateAddress = MagicMock()
        self.DisassociateAddress = MagicMock()

    def DescribeAddresses(self, request):
        matched = self.addresses
        ids = getattr(request, "AddressIds", None)
        filters = getattr(request, "Filters", None)
        if ids:
            matched = [a for a in matched if a["AddressId"] in ids]
        elif filters:
            name_filter = filters[0]
            if name_filter.Name == "address-ip":
                matched = [a for a in matched if a.get("AddressIp") in name_filter.Values]
            elif name_filter.Name == "address-name":
                matched = [a for a in matched if a.get("AddressName") in name_filter.Values]
        return SimpleNamespace(AddressSet=[FakeResource(a) for a in matched])

    def _allocate(self, request):
        address = {
            "AddressId": "eip-new000001",
            "AddressName": getattr(request, "AddressName", ""),
            "AddressIp": "203.0.113.10",
            "InstanceId": "",
            "TagSet": [],
        }
        self.addresses.append(address)
        return SimpleNamespace(AddressSet=[address["AddressId"]])

    def _release(self, request):
        self.addresses = [a for a in self.addresses if a["AddressId"] not in request.AddressIds]
        return SimpleNamespace()


@pytest.fixture
def client(monkeypatch):
    fake = FakeVpcClient()
    monkeypatch.setattr(TencentCloudModule, "require_sdk", lambda self: None)
    monkeypatch.setattr(
        eip, "_load_vpc",
        lambda: (FakeModels(), SimpleNamespace(VpcClient=object)),
    )
    monkeypatch.setattr(
        TencentCloudModule, "create_client",
        lambda self, client_class, endpoint: fake,
    )
    return fake


def test_allocate_reports_changed(client):
    module_args(state="present", name="web-eip")
    result = run(eip.run_module)
    assert result["changed"] is True
    assert result["eip"]["AddressName"] == "web-eip"
    client.AllocateAddresses.assert_called_once()
    assert "diff" not in result


def test_second_run_is_idempotent(client):
    client.addresses.append(dict(ADDRESS))
    module_args(state="present", name="web-eip")
    result = run(eip.run_module)
    assert result["changed"] is False
    assert result["eip"]["AddressId"] == "eip-existing1"
    client.AllocateAddresses.assert_not_called()
    client.ModifyAddressAttribute.assert_not_called()


def test_absent_releases_existing_address(client):
    client.addresses.append(dict(ADDRESS))
    module_args(state="absent", eip_id="eip-existing1")
    result = run(eip.run_module)
    assert result["changed"] is True
    client.ReleaseAddresses.assert_called_once()
    client.DisassociateAddress.assert_not_called()
    assert client.addresses == []


def test_absent_on_missing_address_is_unchanged(client):
    module_args(state="absent", eip_id="eip-existing1")
    result = run(eip.run_module)
    assert result["changed"] is False
    client.ReleaseAddresses.assert_not_called()


def test_check_mode_allocate_makes_no_sdk_writes(client):
    module_args(state="present", name="web-eip", _ansible_check_mode=True)
    result = run(eip.run_module)
    assert result["changed"] is True
    assert "diff" in result
    client.AllocateAddresses.assert_not_called()
    client.ReleaseAddresses.assert_not_called()
    client.ModifyAddressAttribute.assert_not_called()
    client.AssociateAddress.assert_not_called()


def test_diff_mode_allocate_includes_diff(client):
    module_args(state="present", name="web-eip", _ansible_diff=True)
    result = run(eip.run_module)
    assert result["changed"] is True
    assert result["diff"]["before"] is None
    assert result["diff"]["after"]["name"] == "web-eip"
    client.AllocateAddresses.assert_called_once()
