from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_consumer_group_membership import group_ids, mutation_request, resolve_ids


class Value(object):
    pass


def test_group_ids_reads_consumer_detail_memberships():
    assert group_ids({"ConsumerGroups": [{"ConsumerGroupId": "cg1"}, {"ConsumerGroupId": "cg2"}]}) == {"cg1", "cg2"}


def test_membership_request_maps_only_delta():
    p = {"gateway_id": "g1", "consumer_group_id": "cg1"}
    request = mutation_request(Value, p, ["c2"])
    assert request.ConsumerGroupId == "cg1" and request.ConsumerIds == ["c2"]


def test_resolve_ids_reports_unknown_names():
    ids, missing = resolve_ids([{"Name": "mobile", "ConsumerId": "c1"}], ["mobile", "missing"], "ConsumerId")
    assert ids == ["c1"] and missing == ["missing"]
