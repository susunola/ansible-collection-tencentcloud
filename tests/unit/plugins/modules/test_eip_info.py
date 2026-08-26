"""Unit tests for the eip_info module helpers."""

from ansible_collections.tencentcloud.cloud.plugins.modules.eip_info import build_request


class FakeFilter(object):
    pass


class FakeRequest(object):
    pass


class FakeModels(object):
    Filter = FakeFilter
    DescribeAddressesRequest = FakeRequest


def test_build_request_maps_ids_and_pagination():
    request = build_request(FakeModels, ["eip-123"], None, {}, 20, 100)
    assert request.AddressIds == ["eip-123"]
    assert request.Offset == 20
    assert request.Limit == 100
    assert not hasattr(request, "Filters")


def test_build_request_sorts_filters():
    request = build_request(FakeModels, None, None, {"instance-id": ["ins-1"], "address-status": ["BIND"]}, 0, 100)
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("address-status", ["BIND"]), ("instance-id", ["ins-1"]),
    ]
    assert not hasattr(request, "AddressIds")


def test_build_request_merges_address_ips_into_filters():
    request = build_request(FakeModels, None, ["1.2.3.4"], {"address-status": ["BIND"]}, 0, 100)
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("address-ip", ["1.2.3.4"]), ("address-status", ["BIND"]),
    ]


def test_build_request_wraps_scalar_filter_values():
    request = build_request(FakeModels, None, None, {"address-status": "BIND"}, 0, 100)
    assert request.Filters[0].Values == ["BIND"]


def test_build_request_without_selectors_sends_no_filters():
    request = build_request(FakeModels, None, None, {}, 0, 100)
    assert not hasattr(request, "Filters")
    assert not hasattr(request, "AddressIds")
