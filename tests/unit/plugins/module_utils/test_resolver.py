"""Unit tests for the shared resource reference resolver."""

from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

from ansible_collections.susunola.tencentcloud.plugins.module_utils import resolver


class FakeModule:
    """Minimal module stand-in: fail_json is the only contract used here."""

    def __init__(self):
        self.params = {}

    def fail_json(self, **kwargs):
        raise AssertionError(kwargs)


class FakeFilter:
    def __init__(self):
        self.Name = None
        self.Values = None


class FakeModels:
    Filter = FakeFilter


class FakeRequest:
    def __init__(self):
        self.Filters = None


class FakeVpc:
    """SDK-shaped object: _serialize is how the SDK exposes plain data."""

    def __init__(self, vpc_id, name, tags=None):
        self.VpcId = vpc_id
        self.VpcName = name
        self.TagSet = tags or []

    def _serialize(self, allow_none=True):
        return {"VpcId": self.VpcId, "VpcName": self.VpcName, "TagSet": list(self.TagSet)}


def describe_of(*records):
    """Build a describe closure returning a fixed result set."""
    calls = []

    def describe(filters=None):
        calls.append(dict(filters) if filters else None)
        return list(records)

    describe.calls = calls
    return describe


def test_serialize_passes_dicts_through():
    assert resolver.serialize({"VpcId": "vpc-1"}) == {"VpcId": "vpc-1"}
    assert resolver.records(None) == []


def test_serialize_uses_sdk_serialize_hook():
    assert resolver.serialize(FakeVpc("vpc-1", "prod"))["VpcName"] == "prod"


def test_value_of_reads_dicts_and_objects():
    assert resolver.value_of({"VpcName": "prod"}, ("VpcName",)) == "prod"
    assert resolver.value_of(FakeVpc("vpc-1", "prod"), ("VpcId",)) == "vpc-1"
    assert resolver.value_of(None, ("VpcId",)) is None


def test_tag_map_supports_both_tag_shapes():
    assert resolver.tag_map({"TagSet": [{"TagKey": "env", "TagValue": "prod"}]}) == {"env": "prod"}
    assert resolver.tag_map({"Tags": [{"Key": "env", "Value": "prod"}]}) == {"env": "prod"}
    assert resolver.tag_map({}) == {}


def test_resolve_by_id_ignores_fuzzy_server_noise():
    # The server-side filter is a substring match, so the response can carry
    # rows that have nothing to do with the requested id.
    describe = describe_of(FakeVpc("vpc-other", "prod"), FakeVpc("vpc-1", "prod-1"))
    found = resolver.resolve_one(
        FakeModule(), describe, resource="VPC", id_value="vpc-1",
        id_keys=("VpcId",), name_keys=("VpcName",), id_filters=("vpc-id",),
    )
    assert found["VpcId"] == "vpc-1"
    assert describe.calls[0] == {"vpc-id": ["vpc-1"]}


def test_resolve_by_name_prefers_exact_match():
    describe = describe_of(FakeVpc("vpc-1", "prod-extra"), FakeVpc("vpc-2", "prod"))
    found = resolver.resolve_one(
        FakeModule(), describe, resource="VPC", name_value="prod",
        id_keys=("VpcId",), name_keys=("VpcName",), name_filters=("vpc-name",),
    )
    assert found["VpcId"] == "vpc-2"


def test_resolve_by_name_accepts_single_fuzzy_candidate():
    # A lone fuzzy hit is not ambiguous, so existing playbooks keep working.
    describe = describe_of(FakeVpc("vpc-1", "prod-extra"))
    found = resolver.resolve_one(
        FakeModule(), describe, resource="VPC", name_value="prod",
        id_keys=("VpcId",), name_keys=("VpcName",), name_filters=("vpc-name",),
    )
    assert found["VpcId"] == "vpc-1"


def test_resolve_by_name_fails_on_multiple_exact_matches():
    describe = describe_of(FakeVpc("vpc-1", "prod"), FakeVpc("vpc-2", "prod"))
    try:
        resolver.resolve_one(
            FakeModule(), describe, resource="VPC", name_value="prod",
            id_keys=("VpcId",), name_keys=("VpcName",), name_filters=("vpc-name",),
        )
    except AssertionError as exc:
        payload = exc.args[0]
        assert payload["ambiguous"] is True
        assert payload["match_count"] == 2
        assert {item["id"] for item in payload["matches"]} == {"vpc-1", "vpc-2"}
    else:
        raise AssertionError("expected an ambiguity failure")


def test_resolve_by_name_fails_on_multiple_fuzzy_matches():
    describe = describe_of(FakeVpc("vpc-1", "prod-a"), FakeVpc("vpc-2", "prod-b"))
    try:
        resolver.resolve_one(
            FakeModule(), describe, resource="VPC", name_value="prod",
            id_keys=("VpcId",), name_keys=("VpcName",), name_filters=("vpc-name",),
        )
    except AssertionError as exc:
        assert exc.args[0]["ambiguous"] is True
    else:
        raise AssertionError("expected an ambiguity failure")


def test_resolve_by_tags_requires_every_tag():
    describe = describe_of(
        FakeVpc("vpc-1", "a", [{"TagKey": "env", "TagValue": "prod"}]),
        FakeVpc("vpc-2", "b", [{"TagKey": "env", "TagValue": "dev"}]),
    )
    found = resolver.resolve_one(
        FakeModule(), describe, resource="VPC", tags={"env": "prod"},
        id_keys=("VpcId",), name_keys=("VpcName",),
    )
    assert found["VpcId"] == "vpc-1"


def test_resolve_without_selectors_returns_none():
    # No identity at all must not degrade into "list everything and take one".
    describe = describe_of(FakeVpc("vpc-1", "prod"))
    assert resolver.resolve_one(FakeModule(), describe, resource="VPC") is None
    assert describe.calls == []


def test_resolve_returns_none_when_absent():
    assert resolver.resolve_one(
        FakeModule(), describe_of(), resource="VPC", name_value="prod",
        id_keys=("VpcId",), name_keys=("VpcName",),
    ) is None


def test_resolve_required_fails_when_absent():
    try:
        resolver.resolve_one(
            FakeModule(), describe_of(), resource="VPC", name_value="prod",
            id_keys=("VpcId",), name_keys=("VpcName",), required=True,
        )
    except AssertionError as exc:
        assert exc.args[0]["not_found"] is True
    else:
        raise AssertionError("expected a not-found failure")


def test_reference_accepts_registered_var_dicts_and_strings():
    assert resolver.reference({"VpcId": "vpc-1", "VpcName": "prod"},
                              id_keys=("VpcId",), name_keys=("VpcName",)) == ("vpc-1", "prod")
    assert resolver.reference("vpc-1", default="id") == ("vpc-1", None)
    assert resolver.reference("prod", default="name") == (None, "prod")
    assert resolver.reference(None) == (None, None)


def test_attach_filters_builds_sdk_filter_objects():
    request = resolver.attach_filters(FakeRequest(), FakeModels, {"vpc-name": ["prod"]})
    assert request.Filters[0].Name == "vpc-name"
    assert request.Filters[0].Values == ["prod"]
    assert resolver.attach_filters(FakeRequest(), FakeModels, None).Filters is None


def test_attach_filters_keeps_scope_filters_and_replaces_same_name():
    # A subnet lookup carries a vpc-id scope filter; re-resolving the name
    # must not drop the scope nor duplicate the name filter.
    request = FakeRequest()
    request.Filters = []
    scope = FakeFilter()
    scope.Name = "vpc-id"
    scope.Values = ["vpc-9"]
    request.Filters.append(scope)
    request = resolver.attach_filters(request, FakeModels, {"subnet-name": ["prod"]})
    assert sorted(item.Name for item in request.Filters) == ["subnet-name", "vpc-id"]

    request = resolver.attach_filters(request, FakeModels, {"subnet-name": ["prod-2"]})
    names = [item.Name for item in request.Filters]
    assert names.count("subnet-name") == 1
    assert request.Filters[names.index("subnet-name")].Values == ["prod-2"]


def test_resolve_with_extra_match_as_only_selector():
    describe = describe_of({"AddressId": "eip-1", "AddressIp": "1.2.3.4"},
                           {"AddressId": "eip-2", "AddressIp": "5.6.7.8"})
    found = resolver.resolve_one(
        FakeModule(), describe, resource="EIP",
        extra_match=lambda record: record.get("AddressIp") == "5.6.7.8",
    )
    assert found["AddressId"] == "eip-2"


def test_resolve_with_extra_match_alone_still_fails_on_ambiguity():
    describe = describe_of({"AddressId": "eip-1", "AddressIp": "1.2.3.4"},
                           {"AddressId": "eip-2", "AddressIp": "1.2.3.4"})
    try:
        resolver.resolve_one(
            FakeModule(), describe, resource="EIP",
            extra_match=lambda record: record.get("AddressIp") == "1.2.3.4",
        )
    except AssertionError as exc:
        assert exc.args[0]["ambiguous"] is True
    else:
        raise AssertionError("expected an ambiguity failure")


def test_resolve_all_returns_every_match():
    describe = describe_of(FakeVpc("vpc-1", "prod-a"), FakeVpc("vpc-2", "prod-b"))
    found = resolver.resolve_all(
        describe, name_value="prod", id_keys=("VpcId",), name_keys=("VpcName",),
    )
    assert [item["VpcId"] for item in found] == ["vpc-1", "vpc-2"]
