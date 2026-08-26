from ansible_collections.tencentcloud.cloud.plugins.modules.key_pair_info import build_request


class FakeFilter:
    pass


class FakeRequest:
    pass


class FakeModels:
    Filter = FakeFilter
    DescribeKeyPairsRequest = FakeRequest


def test_build_request_maps_ids_and_integer_pagination():
    request = build_request(FakeModels, ["skey-123"], {}, 20, 100)
    assert request.KeyIds == ["skey-123"]
    assert request.Offset == 20
    assert request.Limit == 100


def test_build_request_sorts_filters():
    request = build_request(FakeModels, [], {"key-name": ["deploy-key"], "project-id": [0]}, 0, 100)
    assert [(item.Name, item.Values) for item in request.Filters] == [
        ("key-name", ["deploy-key"]), ("project-id", [0]),
    ]


def test_build_request_wraps_scalar_filter_values():
    request = build_request(FakeModels, [], {"key-name": "deploy-key"}, 0, 100)
    assert request.Filters[0].Values == ["deploy-key"]
    assert not hasattr(request, "KeyIds") or request.KeyIds is None
