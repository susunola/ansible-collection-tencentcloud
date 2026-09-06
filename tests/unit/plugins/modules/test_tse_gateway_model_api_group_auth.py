from ansible_collections.susunola.tencentcloud.plugins.modules.tse_gateway_model_api_group_auth import group_ids, mutation_request, resolve_ids


class Value(object):
    pass


def test_group_ids_reads_model_api_scopes():
    value = {"ConsumerGroupModelScopes": [{"PrincipalId": "cg2"}, {"PrincipalId": "cg1"}, {"PrincipalId": "cg1"}]}
    assert group_ids(value) == ["cg1", "cg2"]


def test_auth_request_uses_model_api_resource_type():
    p = {"gateway_id": "g1", "model_api_id": "api1"}
    request = mutation_request(Value, p, ["cg1"])
    assert request.ResourceType == "ModelAPI" and request.ResourceId == "api1"


def test_resolve_ids_reports_missing_group_names():
    ids, missing = resolve_ids([{"Name": "trusted", "ConsumerGroupId": "cg1"}], ["trusted", "missing"], "ConsumerGroupId")
    assert ids == ["cg1"] and missing == ["missing"]
