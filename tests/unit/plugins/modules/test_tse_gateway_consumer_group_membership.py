from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_consumer_group_membership import group_ids, mutation_request


class Value(object): pass


def test_group_ids_reads_consumer_detail_memberships():
    assert group_ids({"ConsumerGroups":[{"ConsumerGroupId":"cg1"},{"ConsumerGroupId":"cg2"}]})=={"cg1","cg2"}


def test_membership_request_maps_only_delta():
    p={"gateway_id":"g1","consumer_group_id":"cg1"}
    request=mutation_request(Value,p,["c2"])
    assert request.ConsumerGroupId=="cg1" and request.ConsumerIds==["c2"]
